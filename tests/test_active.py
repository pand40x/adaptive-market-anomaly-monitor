from __future__ import annotations

import pandas as pd

from market_anomaly.active import evaluate_active_anomaly
from market_anomaly.models import Alert, MarketClass, SignalBreakdown, Thresholds


def _alert(timestamp: pd.Timestamp) -> Alert:
    return Alert(
        symbol="THYAO.IS",
        asset_name="Turkish Airlines",
        market_class=MarketClass.BIST,
        timestamp=timestamp,
        price=100,
        score=3.4,
        direction="up",
        breakdown=SignalBreakdown(
            price_deviation=3.0,
            volume_expansion=2.0,
            volatility_breakout=1.2,
            short_move=2.4,
        ),
        explanation="test",
    )


def test_active_anomaly_is_pending_until_enough_future_bars_exist() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="1D", tz="UTC")
    candles = pd.DataFrame(
        {
            "open": [100, 101, 102],
            "high": [101, 102, 103],
            "low": [99, 100, 101],
            "close": [100, 101, 102],
            "volume": [1000, 1000, 1000],
        },
        index=index,
    )

    active = evaluate_active_anomaly(
        candles=candles,
        alert=_alert(index[1]),
        thresholds=Thresholds(score=3.0, follow_through_pct=5.0, lookahead_bars=5),
    )

    assert active.status == "pending"
    assert active.asset_name == "Turkish Airlines"


def test_active_anomaly_confirms_when_follow_through_happens() -> None:
    index = pd.date_range("2026-01-01", periods=6, freq="1D", tz="UTC")
    candles = pd.DataFrame(
        {
            "open": [100, 101, 102, 108, 109, 110],
            "high": [101, 102, 103, 109, 110, 111],
            "low": [99, 100, 101, 107, 108, 109],
            "close": [100, 101, 102, 108, 109, 110],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000],
        },
        index=index,
    )

    active = evaluate_active_anomaly(
        candles=candles,
        alert=_alert(index[1]),
        thresholds=Thresholds(score=3.0, follow_through_pct=5.0, lookahead_bars=4),
    )

    assert active.status == "confirmed"
    assert active.max_move_pct >= 5
