from __future__ import annotations

from market_anomaly.cli import _calibration_grid, _weights_for_market
from market_anomaly.models import MarketClass, SignalWeights


def test_forex_calibration_ignores_yahoo_volume() -> None:
    _thresholds, weights = _calibration_grid(MarketClass.FOREX)

    assert weights
    assert all(weight.volume == 0 for weight in weights)


def test_calibration_grid_uses_market_specific_follow_through_ranges() -> None:
    crypto_thresholds, _crypto_weights = _calibration_grid(MarketClass.CRYPTO)
    bist_thresholds, _bist_weights = _calibration_grid(MarketClass.BIST)
    forex_thresholds, _forex_weights = _calibration_grid(MarketClass.FOREX)

    assert max(threshold.lookahead_bars for threshold in crypto_thresholds) > max(
        threshold.lookahead_bars for threshold in bist_thresholds
    )
    assert max(threshold.follow_through_pct for threshold in bist_thresholds) > max(
        threshold.follow_through_pct for threshold in forex_thresholds
    )


def test_loaded_forex_weights_are_sanitized_even_if_old_calibration_has_volume() -> None:
    weights = _weights_for_market(
        MarketClass.FOREX,
        SignalWeights(price=0.45, volume=0.20, volatility=0.20, short_move=0.15),
    )

    assert weights.volume == 0
    assert weights.price == 0.45
