from __future__ import annotations

import os
import time

import typer
from rich.console import Console
from rich.table import Table

from .active import evaluate_active_anomaly
from .assets import display_name_for, market_label_for
from .backtest import (
    calibrate_market_class,
    evaluate_follow_through,
    optimize_parameters,
    run_backtest,
)
from .config import DEFAULT_ASSETS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from .data import fetch_history
from .models import MarketClass, SignalWeights, Thresholds
from .notifier import format_alerts_for_telegram, load_local_env, telegram_from_env
from .signals import detect_anomalies
from .storage import MarketStore

load_local_env()

app = typer.Typer(help="Adaptive market anomaly monitor.")
console = Console()


def _store() -> MarketStore:
    return MarketStore(
        uri=os.environ.get("MONGO_URI"),
        db_name=os.environ.get("MONGO_DATABASE"),
    )


def _parameters_for(store: MarketStore, symbol: str, market_class):
    class_calibration = store.load_class_calibration(market_class)
    if class_calibration is not None:
        thresholds, weights = class_calibration
        return thresholds, _weights_for_market(market_class, weights)
    optimized = store.load_optimization(symbol)
    if optimized is not None:
        thresholds, weights = optimized
        return thresholds, _weights_for_market(market_class, weights)
    return DEFAULT_THRESHOLDS[market_class], _weights_for_market(market_class, DEFAULT_WEIGHTS[market_class])


@app.command()
def backfill(years: int = typer.Option(3, min=1, max=5)) -> None:
    """Fetch historical candles into MongoDB."""
    store = _store()
    try:
        for asset in DEFAULT_ASSETS:
            candles = fetch_history(asset, years=years)
            store.save_candles(asset.symbol, asset.market_class, candles)
            console.print(f"{asset.name or display_name_for(asset.symbol)}: saved {len(candles)} candles")
    finally:
        store.close()


@app.command()
def scan() -> None:
    """Scan stored candles and save current anomaly alerts."""
    store = _store()
    table = Table("Asset", "Symbol", "Class", "Alerts", "Latest explanation")
    latest_alerts = []
    active_anomalies = []
    try:
        for asset in DEFAULT_ASSETS:
            candles = store.load_candles(asset.symbol)
            if candles.empty:
                continue
            thresholds, weights = _parameters_for(store, asset.symbol, asset.market_class)
            alerts = detect_anomalies(
                symbol=asset.symbol,
                market_class=asset.market_class,
                candles=candles,
                thresholds=thresholds,
                weights=weights,
                cadence=asset.cadence,
                asset_name=asset.name or display_name_for(asset.symbol),
            )
            store.save_alerts(alerts[-20:])
            active_anomalies.extend(
                evaluate_active_anomaly(candles=candles, alert=alert, thresholds=thresholds)
                for alert in alerts[-1:]
            )
            latest_alerts.extend(alerts[-1:])
            latest = alerts[-1].explanation if alerts else "-"
            table.add_row(
                asset.name or display_name_for(asset.symbol),
                asset.symbol,
                market_label_for(asset.market_class),
                str(len(alerts)),
                latest,
            )
        store.save_active_anomalies(active_anomalies)
        console.print(table)
        notifier = telegram_from_env()
        if latest_alerts and notifier.send(format_alerts_for_telegram(latest_alerts)):
            console.print("Telegram alert summary sent")
    finally:
        store.close()


@app.command()
def backtest(years: int = typer.Option(3, min=1, max=5)) -> None:
    """Fetch history and report default parameter performance."""
    table = Table("Asset", "Symbol", "Class", "Alerts", "Meaningful", "Precision", "Noise", "Avg move", "React bars")
    for asset in DEFAULT_ASSETS:
        candles = fetch_history(asset, years=years)
        result = run_backtest(
            symbol=asset.symbol,
            market_class=asset.market_class,
            candles=candles,
            thresholds=DEFAULT_THRESHOLDS[asset.market_class],
            weights=DEFAULT_WEIGHTS[asset.market_class],
            cadence=asset.cadence,
            asset_name=asset.name or display_name_for(asset.symbol),
        )
        table.add_row(
            asset.name or display_name_for(asset.symbol),
            result.symbol,
            market_label_for(result.market_class),
            str(result.alert_count),
            str(result.meaningful_count),
            f"{result.precision:.2%}",
            f"{result.noise_ratio:.2%}",
            f"{result.average_max_move_pct:.2f}%",
            f"{result.average_reaction_bars:.2f}",
        )
    console.print(table)


@app.command()
def optimize(years: int = typer.Option(3, min=1, max=5)) -> None:
    """Optimize thresholds and weights per asset class, then save best settings."""
    store = _store()
    table = Table("Symbol", "Class", "Score", "Precision", "Noise", "Alerts", "React", "Objective")
    try:
        for asset in DEFAULT_ASSETS:
            threshold_grid, weight_grid = _calibration_grid(asset.market_class)
            candles = fetch_history(asset, years=years)
            store.save_candles(asset.symbol, asset.market_class, candles)
            result = optimize_parameters(
                symbol=asset.symbol,
                market_class=asset.market_class,
                candles=candles,
                candidate_thresholds=threshold_grid,
                candidate_weights=weight_grid,
                min_alerts=2,
                cadence=asset.cadence,
            )
            store.save_optimization(result)
            table.add_row(
                result.symbol,
                result.market_class.value,
                f"{result.thresholds.score:.1f}",
                f"{result.precision:.2%}",
                f"{result.noise_ratio:.2%}",
                str(result.alert_count),
                f"{result.average_reaction_bars:.2f}",
                f"{result.objective:.3f}",
            )
        console.print(table)
    finally:
        store.close()


@app.command("calibrate-classes")
def calibrate_classes(years: int = typer.Option(3, min=1, max=5)) -> None:
    """Calibrate one shared parameter set per market class and save it to MongoDB."""
    store = _store()
    table = Table("Class", "Assets", "Score", "Follow", "Alerts", "Precision", "Noise", "React", "Objective")
    try:
        for market_class in MarketClass:
            assets = [asset for asset in DEFAULT_ASSETS if asset.market_class is market_class]
            if not assets:
                continue
            threshold_grid, weight_grid = _calibration_grid(market_class)
            histories = {}
            for asset in assets:
                candles = fetch_history(asset, years=years)
                store.save_candles(asset.symbol, asset.market_class, candles)
                histories[asset.symbol] = candles
            result = calibrate_market_class(
                market_class=market_class,
                histories=histories,
                candidate_thresholds=threshold_grid,
                candidate_weights=weight_grid,
                min_alerts=max(2, len(histories) * 2),
                cadence=assets[0].cadence,
            )
            store.save_class_calibration(result)
            table.add_row(
                market_label_for(result.market_class),
                str(result.asset_count),
                f"{result.thresholds.score:.1f}",
                f"{result.thresholds.follow_through_pct:.1f}%",
                str(result.alert_count),
                f"{result.precision:.2%}",
                f"{result.noise_ratio:.2%}",
                f"{result.average_reaction_bars:.2f}",
                f"{result.objective:.3f}",
            )
        console.print(table)
    finally:
        store.close()


@app.command("anomaly-benchmark")
def anomaly_benchmark(years: int = typer.Option(3, min=1, max=5)) -> None:
    """Measure historical alert quality using the active calibrated settings."""
    store = _store()
    table = Table("Asset", "Symbol", "Class", "Alerts", "Meaningful", "Precision", "Noise", "Avg move", "React bars")
    try:
        for asset in DEFAULT_ASSETS:
            candles = store.load_candles(asset.symbol)
            if candles.empty:
                candles = fetch_history(asset, years=years)
                store.save_candles(asset.symbol, asset.market_class, candles)
            thresholds, weights = _parameters_for(store, asset.symbol, asset.market_class)
            result = run_backtest(
                symbol=asset.symbol,
                market_class=asset.market_class,
                candles=candles,
                thresholds=thresholds,
                weights=weights,
                cadence=asset.cadence,
                asset_name=asset.name or display_name_for(asset.symbol),
            )
            table.add_row(
                asset.name or display_name_for(asset.symbol),
                result.symbol,
                market_label_for(result.market_class),
                str(result.alert_count),
                str(result.meaningful_count),
                f"{result.precision:.2%}",
                f"{result.noise_ratio:.2%}",
                f"{result.average_max_move_pct:.2f}%",
                f"{result.average_reaction_bars:.2f}",
            )
        console.print(table)
    finally:
        store.close()


@app.command()
def cycle(
    years: int = typer.Option(3, min=1, max=5),
    tune: bool = typer.Option(False, help="Run optimization before scanning."),
) -> None:
    """Run one full collection, optional tuning, scan, and evaluation cycle."""
    backfill(years=years)
    if tune:
        calibrate_classes(years=years)
    scan()
    evaluate_alerts()


@app.command()
def worker(
    years: int = typer.Option(3, min=1, max=5),
    cycle_minutes: int = typer.Option(60, min=5),
    optimize_every_cycles: int = typer.Option(24, min=1),
) -> None:
    """Run the monitor continuously on a simple schedule."""
    cycle_number = 0
    while True:
        cycle_number += 1
        tune = cycle_number == 1 or cycle_number % optimize_every_cycles == 0
        console.print(f"Starting cycle {cycle_number}; tune={tune}")
        cycle(years=years, tune=tune)
        time.sleep(cycle_minutes * 60)


@app.command("telegram-chat-ids")
def telegram_chat_ids() -> None:
    """Show chat IDs seen by the configured Telegram bot."""
    chat_ids = telegram_from_env().discover_chat_ids()
    if not chat_ids:
        console.print("No chat IDs found. Send the bot a message first, then run this again.")
        raise typer.Exit(code=1)
    for chat_id in chat_ids:
        console.print(chat_id)


@app.command("active-anomalies")
def active_anomalies(
    status: str = typer.Option("pending", help="Use pending, confirmed, expired, or all."),
) -> None:
    """Show active anomaly follow-up status from MongoDB."""
    store = _store()
    normalized_status = None if status.lower() == "all" else status.lower()
    table = Table("Asset", "Symbol", "Class", "Status", "Direction", "Score", "Progress", "Max move", "Target")
    try:
        for anomaly in store.load_active_anomalies(status=normalized_status, limit=100):
            table.add_row(
                anomaly.asset_name or display_name_for(anomaly.symbol),
                anomaly.symbol,
                market_label_for(anomaly.market_class),
                anomaly.status,
                "Yukarı" if anomaly.direction == "up" else "Aşağı",
                f"{anomaly.score:.2f}/{anomaly.threshold_score:.1f}",
                f"{anomaly.observed_bars}/{anomaly.lookahead_bars} bar",
                f"{anomaly.max_move_pct:.2f}%",
                f"{anomaly.follow_through_pct:.1f}% hareket",
            )
        console.print(table)
    finally:
        store.close()


@app.command("evaluate-alerts")
def evaluate_alerts() -> None:
    """Evaluate the latest stored scan alerts against subsequent candles."""
    store = _store()
    evaluations = []
    try:
        for asset in DEFAULT_ASSETS:
            candles = store.load_candles(asset.symbol)
            if candles.empty:
                continue
            thresholds, weights = _parameters_for(store, asset.symbol, asset.market_class)
            alerts = detect_anomalies(
                symbol=asset.symbol,
                market_class=asset.market_class,
                candles=candles,
                thresholds=thresholds,
                weights=weights,
                cadence=asset.cadence,
                asset_name=asset.name or display_name_for(asset.symbol),
            )
            evaluations.extend(
                evaluate_follow_through(
                    candles=candles,
                    alert=alert,
                    thresholds=thresholds,
                )
                for alert in alerts[-20:]
            )
        store.save_evaluations(evaluations)
        console.print(f"Saved {len(evaluations)} alert evaluations")
    finally:
        store.close()


def _weights_for_market(market_class: MarketClass, weights: SignalWeights) -> SignalWeights:
    if market_class is MarketClass.FOREX:
        return SignalWeights(
            price=weights.price,
            volume=0.0,
            volatility=weights.volatility,
            short_move=weights.short_move,
        )
    return weights


def _calibration_grid(market_class: MarketClass) -> tuple[list[Thresholds], list[SignalWeights]]:
    thresholds_by_class = {
        MarketClass.CRYPTO: [
            Thresholds(score=2.2, follow_through_pct=2.0, lookahead_bars=8),
            Thresholds(score=2.6, follow_through_pct=2.5, lookahead_bars=12),
            Thresholds(score=3.0, follow_through_pct=3.0, lookahead_bars=12),
            Thresholds(score=3.6, follow_through_pct=4.0, lookahead_bars=24),
            Thresholds(score=4.0, follow_through_pct=4.0, lookahead_bars=24),
            Thresholds(score=4.4, follow_through_pct=4.0, lookahead_bars=24),
            Thresholds(score=4.8, follow_through_pct=4.0, lookahead_bars=24),
            Thresholds(score=5.0, follow_through_pct=4.0, lookahead_bars=24),
        ],
        MarketClass.STOCK: [
            Thresholds(score=2.2, follow_through_pct=2.5, lookahead_bars=5),
            Thresholds(score=2.6, follow_through_pct=3.0, lookahead_bars=5),
            Thresholds(score=3.0, follow_through_pct=4.0, lookahead_bars=10),
            Thresholds(score=3.4, follow_through_pct=5.0, lookahead_bars=10),
        ],
        MarketClass.INDEX: [
            Thresholds(score=1.8, follow_through_pct=1.0, lookahead_bars=5),
            Thresholds(score=2.1, follow_through_pct=1.5, lookahead_bars=5),
            Thresholds(score=2.5, follow_through_pct=2.0, lookahead_bars=10),
            Thresholds(score=2.9, follow_through_pct=2.5, lookahead_bars=10),
        ],
        MarketClass.FOREX: [
            Thresholds(score=1.8, follow_through_pct=0.5, lookahead_bars=5),
            Thresholds(score=2.1, follow_through_pct=0.8, lookahead_bars=5),
            Thresholds(score=2.5, follow_through_pct=1.0, lookahead_bars=10),
            Thresholds(score=2.9, follow_through_pct=1.2, lookahead_bars=10),
        ],
        MarketClass.COMMODITY: [
            Thresholds(score=2.0, follow_through_pct=1.2, lookahead_bars=5),
            Thresholds(score=2.4, follow_through_pct=1.8, lookahead_bars=5),
            Thresholds(score=2.8, follow_through_pct=2.5, lookahead_bars=10),
            Thresholds(score=3.2, follow_through_pct=3.0, lookahead_bars=10),
        ],
        MarketClass.BIST: [
            Thresholds(score=2.4, follow_through_pct=3.0, lookahead_bars=5),
            Thresholds(score=2.8, follow_through_pct=4.0, lookahead_bars=5),
            Thresholds(score=3.2, follow_through_pct=5.0, lookahead_bars=10),
            Thresholds(score=3.6, follow_through_pct=7.0, lookahead_bars=10),
        ],
    }
    weights_by_class = {
        MarketClass.FOREX: [
            SignalWeights(price=0.50, volume=0.0, volatility=0.25, short_move=0.25),
            SignalWeights(price=0.40, volume=0.0, volatility=0.35, short_move=0.25),
            SignalWeights(price=0.35, volume=0.0, volatility=0.25, short_move=0.40),
        ],
        MarketClass.INDEX: [
            SignalWeights(price=0.50, volume=0.05, volatility=0.25, short_move=0.20),
            SignalWeights(price=0.40, volume=0.05, volatility=0.35, short_move=0.20),
            SignalWeights(price=0.45, volume=0.0, volatility=0.30, short_move=0.25),
        ],
    }
    default_weights = [
        SignalWeights(price=0.35, volume=0.25, volatility=0.20, short_move=0.20),
        SignalWeights(price=0.45, volume=0.20, volatility=0.20, short_move=0.15),
        SignalWeights(price=0.30, volume=0.20, volatility=0.30, short_move=0.20),
        SignalWeights(price=0.45, volume=0.25, volatility=0.15, short_move=0.15),
    ]
    threshold_grid = thresholds_by_class[market_class]
    weight_grid = weights_by_class.get(market_class, default_weights)
    return threshold_grid, weight_grid


if __name__ == "__main__":
    app()
