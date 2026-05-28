from __future__ import annotations

import pandas as pd

from datetime import datetime, timezone

from market_anomaly.models import Alert, MarketClass, SignalBreakdown, SignalWeights, Thresholds
from market_anomaly.signals import _dedupe_adjacent_alerts, detect_anomalies


def _sample_candles() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=90, freq="1h", tz="UTC")
    close = [100 + i * 0.02 for i in range(89)] + [114]
    volume = [1000 for _ in range(89)] + [4500]
    high = [value * 1.005 for value in close]
    low = [value * 0.995 for value in close]
    return pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=index,
    )


def test_detect_anomalies_combines_price_volume_volatility_and_short_move() -> None:
    alerts = detect_anomalies(
        symbol="BTCUSDT",
        market_class=MarketClass.CRYPTO,
        candles=_sample_candles(),
        thresholds=Thresholds(score=2.0, follow_through_pct=1.5, lookahead_bars=6),
        weights=SignalWeights(price=0.35, volume=0.25, volatility=0.2, short_move=0.2),
    )

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.symbol == "BTCUSDT"
    assert alert.market_class is MarketClass.CRYPTO
    assert alert.score >= 2.0
    assert "fiyat" in alert.explanation.lower()
    assert "hacim" in alert.explanation.lower()
    assert "oynaklık" in alert.explanation.lower()
    assert "kısa vadeli" in alert.explanation.lower()


def test_detect_anomalies_stays_quiet_when_score_is_below_threshold() -> None:
    alerts = detect_anomalies(
        symbol="BTCUSDT",
        market_class=MarketClass.CRYPTO,
        candles=_sample_candles(),
        thresholds=Thresholds(score=10.0, follow_through_pct=1.5, lookahead_bars=6),
        weights=SignalWeights(price=0.35, volume=0.25, volatility=0.2, short_move=0.2),
    )

    assert alerts == []


def test_detect_anomalies_skips_alerts_outside_natural_market_time() -> None:
    alerts = detect_anomalies(
        symbol="THYAO.IS",
        market_class=MarketClass.BIST,
        candles=_sample_candles(),
        thresholds=Thresholds(score=2.0, follow_through_pct=1.5, lookahead_bars=6),
        weights=SignalWeights(price=0.35, volume=0.25, volatility=0.2, short_move=0.2),
        cadence="1h",
    )

    assert alerts == []


def test_dedupe_keeps_same_direction_alert_after_follow_window_passes() -> None:
    first = Alert(
        symbol="BTCUSDT",
        market_class=MarketClass.CRYPTO,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price=100,
        score=3.0,
        direction="up",
        breakdown=SignalBreakdown(
            price_deviation=3,
            volume_expansion=2,
            volatility_breakout=1,
            short_move=2,
        ),
        explanation="first",
    )
    stronger_nearby = first.model_copy(
        update={
            "timestamp": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            "score": 4.0,
            "explanation": "nearby",
        }
    )
    later = first.model_copy(
        update={
            "timestamp": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "score": 3.5,
            "explanation": "later",
        }
    )

    alerts = _dedupe_adjacent_alerts(
        [(10, first), (11, stronger_nearby), (40, later)],
        max_bar_gap=6,
    )

    assert [alert.explanation for alert in alerts] == ["nearby", "later"]
