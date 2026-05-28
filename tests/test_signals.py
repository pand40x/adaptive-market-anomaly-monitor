from __future__ import annotations

import pandas as pd

from market_anomaly.models import MarketClass, SignalWeights, Thresholds
from market_anomaly.signals import detect_anomalies


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
    assert "price deviation" in alert.explanation.lower()
    assert "volume" in alert.explanation.lower()
    assert "volatility" in alert.explanation.lower()
    assert "short-term move" in alert.explanation.lower()


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
