from __future__ import annotations

import statistics

import pandas as pd

from .models import (
    Alert,
    BacktestResult,
    ClassCalibrationResult,
    FollowThroughResult,
    MarketClass,
    OptimizationResult,
    SignalWeights,
    Thresholds,
)
from .signals import detect_anomalies


def evaluate_follow_through(
    *,
    candles: pd.DataFrame,
    alert: Alert,
    thresholds: Thresholds,
) -> FollowThroughResult:
    frame = candles.sort_index()
    timestamp = pd.Timestamp(alert.timestamp)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")

    indexer = frame.index.get_indexer([timestamp], method="nearest")
    if len(indexer) == 0 or indexer[0] < 0:
        raise ValueError("alert timestamp is outside candle history")

    start = int(indexer[0])
    future = frame.iloc[start + 1 : start + 1 + thresholds.lookahead_bars]
    if future.empty:
        return FollowThroughResult(
            symbol=alert.symbol,
            timestamp=alert.timestamp,
            direction=alert.direction,
            meaningful=False,
            max_move_pct=0.0,
            bars_elapsed=0,
        )

    if alert.direction == "up":
        moves = (future["high"] / alert.price - 1.0) * 100
    else:
        moves = (1.0 - future["low"] / alert.price) * 100

    moves = moves.clip(lower=0)
    max_move = float(moves.max())
    reset_moves = moves.reset_index(drop=True)
    first_meaningful = reset_moves[reset_moves >= thresholds.follow_through_pct]
    if first_meaningful.empty:
        bars_elapsed = int(reset_moves.idxmax()) + 1
    else:
        bars_elapsed = int(first_meaningful.index[0]) + 2
    return FollowThroughResult(
        symbol=alert.symbol,
        timestamp=alert.timestamp,
        direction=alert.direction,
        meaningful=max_move >= thresholds.follow_through_pct,
        max_move_pct=round(max_move, 4),
        bars_elapsed=bars_elapsed,
    )


def run_backtest(
    *,
    symbol: str,
    market_class: MarketClass,
    candles: pd.DataFrame,
    thresholds: Thresholds,
    weights: SignalWeights,
    cadence: str = "1d",
    asset_name: str | None = None,
) -> BacktestResult:
    alerts = detect_anomalies(
        symbol=symbol,
        market_class=market_class,
        candles=candles,
        thresholds=thresholds,
        weights=weights,
        cadence=cadence,
        asset_name=asset_name,
    )
    evaluations = [
        evaluate_follow_through(candles=candles, alert=alert, thresholds=thresholds)
        for alert in alerts
    ]
    meaningful_count = sum(1 for result in evaluations if result.meaningful)
    alert_count = len(alerts)
    precision = meaningful_count / alert_count if alert_count else 0.0
    noise_ratio = 1.0 - precision if alert_count else 0.0
    average_move = statistics.fmean([result.max_move_pct for result in evaluations]) if evaluations else 0.0
    reaction_bars = [result.bars_elapsed for result in evaluations if result.meaningful]
    average_reaction_bars = statistics.fmean(reaction_bars) if reaction_bars else 0.0
    return BacktestResult(
        symbol=symbol,
        market_class=market_class,
        alert_count=alert_count,
        meaningful_count=meaningful_count,
        precision=round(precision, 4),
        noise_ratio=round(noise_ratio, 4),
        average_max_move_pct=round(average_move, 4),
        average_reaction_bars=round(average_reaction_bars, 2),
        thresholds=thresholds,
        weights=weights,
    )


def optimize_parameters(
    *,
    symbol: str,
    market_class: MarketClass,
    candles: pd.DataFrame,
    candidate_thresholds: list[Thresholds],
    candidate_weights: list[SignalWeights],
    min_alerts: int = 3,
    cadence: str = "1d",
) -> OptimizationResult:
    best: OptimizationResult | None = None
    for thresholds in candidate_thresholds:
        for weights in candidate_weights:
            result = run_backtest(
                symbol=symbol,
                market_class=market_class,
                candles=candles,
                thresholds=thresholds,
                weights=weights,
                cadence=cadence,
            )
            if result.alert_count < min_alerts:
                continue

            coverage = min(result.alert_count / 20, 1.0)
            noise_penalty = max(0, (result.alert_count - result.meaningful_count) / max(result.alert_count, 1))
            move_quality = min(result.average_max_move_pct / thresholds.follow_through_pct, 3.0) / 3.0
            objective = (
                result.precision * 0.62
                + move_quality * 0.2
                + coverage * 0.08
                + min(thresholds.score / 4.0, 1.0) * 0.1
                - noise_penalty * 0.25
            )
            candidate = OptimizationResult(
                **result.model_dump(),
                objective=round(objective, 4),
            )
            if best is None or _is_better(candidate, best):
                best = candidate

    if best is None:
        fallback_thresholds = candidate_thresholds[0]
        fallback_weights = candidate_weights[0]
        result = run_backtest(
            symbol=symbol,
            market_class=market_class,
            candles=candles,
            thresholds=fallback_thresholds,
            weights=fallback_weights,
        )
        best = OptimizationResult(**result.model_dump(), objective=0.0)
    return best


def calibrate_market_class(
    *,
    market_class: MarketClass,
    histories: dict[str, pd.DataFrame],
    candidate_thresholds: list[Thresholds],
    candidate_weights: list[SignalWeights],
    min_alerts: int = 3,
    cadence: str = "1d",
) -> ClassCalibrationResult:
    best: ClassCalibrationResult | None = None
    for thresholds in candidate_thresholds:
        for weights in candidate_weights:
            results = [
                run_backtest(
                    symbol=symbol,
                    market_class=market_class,
                    candles=candles,
                    thresholds=thresholds,
                    weights=weights,
                    cadence=cadence,
                )
                for symbol, candles in histories.items()
            ]
            alert_count = sum(result.alert_count for result in results)
            if alert_count < min_alerts:
                continue

            meaningful_count = sum(result.meaningful_count for result in results)
            precision = meaningful_count / alert_count if alert_count else 0.0
            noise_ratio = 1.0 - precision if alert_count else 0.0
            average_move = _weighted_average(
                [(result.average_max_move_pct, result.alert_count) for result in results]
            )
            average_reaction_bars = _weighted_average(
                [
                    (result.average_reaction_bars, result.meaningful_count)
                    for result in results
                    if result.meaningful_count
                ]
            )
            target_alerts = max(len(histories) * 36, min_alerts)
            coverage = min(alert_count / max(len(histories) * min_alerts, 1), 1.0)
            excess_alert_penalty = max(0.0, (alert_count - target_alerts) / max(target_alerts, 1))
            low_follow_penalty = max(0.0, (2.0 - thresholds.follow_through_pct) / 2.0)
            move_quality = min(average_move / thresholds.follow_through_pct, 3.0) / 3.0
            speed_quality = 1.0 / (1.0 + average_reaction_bars / max(thresholds.lookahead_bars, 1))
            objective = (
                precision * 0.62
                + move_quality * 0.18
                + speed_quality * 0.09
                + coverage * 0.05
                + min(thresholds.score / 4.0, 1.0) * 0.1
                - noise_ratio * 0.32
                - min(excess_alert_penalty, 3.0) * 0.12
                - low_follow_penalty * 0.08
            )
            candidate = ClassCalibrationResult(
                market_class=market_class,
                asset_count=len(histories),
                alert_count=alert_count,
                meaningful_count=meaningful_count,
                precision=round(precision, 4),
                noise_ratio=round(noise_ratio, 4),
                average_max_move_pct=round(average_move, 4),
                average_reaction_bars=round(average_reaction_bars, 2),
                thresholds=thresholds,
                weights=weights,
                objective=round(objective, 4),
            )
            if best is None or _is_better_class(candidate, best):
                best = candidate

    if best is not None:
        return best

    fallback_thresholds = candidate_thresholds[0]
    fallback_weights = candidate_weights[0]
    fallback_results = [
        run_backtest(
            symbol=symbol,
            market_class=market_class,
            candles=candles,
            thresholds=fallback_thresholds,
            weights=fallback_weights,
            cadence=cadence,
        )
        for symbol, candles in histories.items()
    ]
    alert_count = sum(result.alert_count for result in fallback_results)
    meaningful_count = sum(result.meaningful_count for result in fallback_results)
    precision = meaningful_count / alert_count if alert_count else 0.0
    return ClassCalibrationResult(
        market_class=market_class,
        asset_count=len(histories),
        alert_count=alert_count,
        meaningful_count=meaningful_count,
        precision=round(precision, 4),
        noise_ratio=round(1.0 - precision, 4) if alert_count else 0.0,
        average_max_move_pct=_weighted_average(
            [(result.average_max_move_pct, result.alert_count) for result in fallback_results]
        ),
        average_reaction_bars=_weighted_average(
            [
                (result.average_reaction_bars, result.meaningful_count)
                for result in fallback_results
                if result.meaningful_count
            ]
        ),
        thresholds=fallback_thresholds,
        weights=fallback_weights,
        objective=0.0,
    )


def _is_better(candidate: OptimizationResult, current: OptimizationResult) -> bool:
    return (
        candidate.objective,
        candidate.precision,
        candidate.meaningful_count,
        candidate.thresholds.score,
        -candidate.alert_count,
    ) > (
        current.objective,
        current.precision,
        current.meaningful_count,
        current.thresholds.score,
        -current.alert_count,
    )


def _is_better_class(candidate: ClassCalibrationResult, current: ClassCalibrationResult) -> bool:
    return (
        candidate.objective,
        candidate.precision,
        candidate.meaningful_count,
        candidate.thresholds.score,
        -candidate.alert_count,
    ) > (
        current.objective,
        current.precision,
        current.meaningful_count,
        current.thresholds.score,
        -current.alert_count,
    )


def _weighted_average(values: list[tuple[float, int]]) -> float:
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0:
        return 0.0
    return round(sum(value * weight for value, weight in values) / total_weight, 4)
