from __future__ import annotations

import pandas as pd

from market_anomaly.backtest import (
    calibrate_market_class,
    evaluate_follow_through,
    optimize_parameters,
    run_backtest,
)
from market_anomaly.models import Alert, MarketClass, SignalBreakdown, SignalWeights, Thresholds


def _candles_after_alert() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=8, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 105, 106, 107, 108],
            "high": [101, 102, 103, 106, 108, 109, 110, 111],
            "low": [99, 100, 101, 102, 104, 105, 106, 107],
            "close": [100, 101, 102, 105, 107, 108, 109, 110],
            "volume": [1000] * 8,
        },
        index=index,
    )


def test_evaluate_follow_through_marks_meaningful_move_after_alert() -> None:
    candles = _candles_after_alert()
    alert = Alert(
        symbol="AAPL",
        market_class=MarketClass.STOCK,
        timestamp=candles.index[1],
        price=101,
        score=2.7,
        direction="up",
        breakdown=SignalBreakdown(
            price_deviation=2.0,
            volume_expansion=1.2,
            volatility_breakout=1.5,
            short_move=1.7,
        ),
        explanation="test",
    )

    result = evaluate_follow_through(
        candles=candles,
        alert=alert,
        thresholds=Thresholds(score=2.0, follow_through_pct=3.0, lookahead_bars=4),
    )

    assert result.meaningful is True
    assert result.max_move_pct >= 3.0
    assert result.bars_elapsed == 3


def test_evaluate_follow_through_clamps_unfavorable_move_to_zero() -> None:
    index = pd.date_range("2026-01-01", periods=5, freq="1h", tz="UTC")
    candles = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [101, 102, 103, 104, 105],
            "low": [100, 101, 102, 103, 104],
            "close": [101, 102, 103, 104, 105],
            "volume": [1000] * 5,
        },
        index=index,
    )
    alert = Alert(
        symbol="AAPL",
        market_class=MarketClass.STOCK,
        timestamp=candles.index[1],
        price=101,
        score=2.7,
        direction="down",
        breakdown=SignalBreakdown(
            price_deviation=2.0,
            volume_expansion=1.2,
            volatility_breakout=1.5,
            short_move=1.7,
        ),
        explanation="test",
    )

    result = evaluate_follow_through(
        candles=candles,
        alert=alert,
        thresholds=Thresholds(score=2.0, follow_through_pct=3.0, lookahead_bars=4),
    )

    assert result.meaningful is False
    assert result.max_move_pct == 0.0


def test_optimizer_prefers_parameter_set_with_higher_precision_and_enough_alerts() -> None:
    index = pd.date_range("2026-01-01", periods=160, freq="1h", tz="UTC")
    close = []
    volume = []
    price = 100.0
    for i in range(160):
        if i in (60, 110):
            price *= 1.08
            volume.append(6000)
        elif i in (61, 62, 111, 112):
            price *= 1.025
            volume.append(3000)
        else:
            price *= 1.0005
            volume.append(1000)
        close.append(price)
    candles = pd.DataFrame(
        {
            "open": close,
            "high": [value * 1.01 for value in close],
            "low": [value * 0.99 for value in close],
            "close": close,
            "volume": volume,
        },
        index=index,
    )

    result = optimize_parameters(
        symbol="ETHUSDT",
        market_class=MarketClass.CRYPTO,
        candles=candles,
        candidate_thresholds=[
            Thresholds(score=1.0, follow_through_pct=2.0, lookahead_bars=4),
            Thresholds(score=2.4, follow_through_pct=2.0, lookahead_bars=4),
        ],
        candidate_weights=[
            SignalWeights(price=0.25, volume=0.25, volatility=0.25, short_move=0.25),
            SignalWeights(price=0.45, volume=0.25, volatility=0.15, short_move=0.15),
        ],
        min_alerts=1,
    )

    assert result.alert_count >= 1
    assert result.precision >= 0.5
    assert result.thresholds.score == 2.4


def test_backtest_reports_reaction_speed_and_noise_ratio() -> None:
    index = pd.date_range("2026-01-01", periods=90, freq="1h", tz="UTC")
    close = [100 + i * 0.02 for i in range(86)] + [108, 111, 113, 114]
    volume = [1000 for _ in range(86)] + [5000, 3000, 2500, 2000]
    candles = pd.DataFrame(
        {
            "open": close,
            "high": [value * 1.01 for value in close],
            "low": [value * 0.99 for value in close],
            "close": close,
            "volume": volume,
        },
        index=index,
    )

    result = run_backtest(
        symbol="AAPL",
        market_class=MarketClass.STOCK,
        candles=candles,
        thresholds=Thresholds(score=0.1, follow_through_pct=3.0, lookahead_bars=4),
        weights=SignalWeights(price=1.0, volume=0.0, volatility=0.0, short_move=0.0),
    )

    assert result.alert_count >= 1
    assert result.noise_ratio <= 1.0
    assert result.average_reaction_bars >= 0


def test_calibrate_market_class_selects_shared_settings_across_assets() -> None:
    index = pd.date_range("2026-01-01", periods=180, freq="1h", tz="UTC")

    def candles_with_moves(multiplier: float) -> pd.DataFrame:
        close = []
        volume = []
        price = 100.0
        for i in range(180):
            if i in (60, 120):
                price *= 1.07 * multiplier
                volume.append(6500)
            elif i in (61, 62, 121, 122):
                price *= 1.02
                volume.append(3500)
            else:
                price *= 1.0004
                volume.append(1000)
            close.append(price)
        return pd.DataFrame(
            {
                "open": close,
                "high": [value * 1.01 for value in close],
                "low": [value * 0.99 for value in close],
                "close": close,
                "volume": volume,
            },
            index=index,
        )

    result = calibrate_market_class(
        market_class=MarketClass.CRYPTO,
        histories={
            "BTCUSDT": candles_with_moves(1.0),
            "ETHUSDT": candles_with_moves(0.98),
        },
        candidate_thresholds=[
            Thresholds(score=1.0, follow_through_pct=2.0, lookahead_bars=4),
            Thresholds(score=2.4, follow_through_pct=2.0, lookahead_bars=4),
        ],
        candidate_weights=[
            SignalWeights(price=0.25, volume=0.25, volatility=0.25, short_move=0.25),
            SignalWeights(price=0.45, volume=0.25, volatility=0.15, short_move=0.15),
        ],
        min_alerts=2,
    )

    assert result.market_class is MarketClass.CRYPTO
    assert result.asset_count == 2
    assert result.alert_count >= 2
    assert result.thresholds.score == 2.4
    assert result.precision >= 0.5
