from __future__ import annotations

import pandas as pd

from market_anomaly.models import MarketClass
from market_anomaly.sessions import is_natural_market_time


def test_bist_intraday_timestamp_is_only_active_during_istanbul_session() -> None:
    assert not is_natural_market_time(
        MarketClass.BIST,
        pd.Timestamp("2026-05-25 09:00:00", tz="Europe/Istanbul"),
        cadence="1h",
    )
    assert is_natural_market_time(
        MarketClass.BIST,
        pd.Timestamp("2026-05-25 10:00:00", tz="Europe/Istanbul"),
        cadence="1h",
    )
    assert is_natural_market_time(
        MarketClass.BIST,
        pd.Timestamp("2026-05-25 18:09:00", tz="Europe/Istanbul"),
        cadence="1h",
    )
    assert not is_natural_market_time(
        MarketClass.BIST,
        pd.Timestamp("2026-05-25 18:11:00", tz="Europe/Istanbul"),
        cadence="1h",
    )


def test_daily_yahoo_bars_are_accepted_on_weekdays_for_session_markets() -> None:
    assert is_natural_market_time(MarketClass.STOCK, pd.Timestamp("2026-05-28", tz="UTC"), cadence="1d")
    assert not is_natural_market_time(MarketClass.STOCK, pd.Timestamp("2026-05-30", tz="UTC"), cadence="1d")
    assert not is_natural_market_time(MarketClass.STOCK, pd.Timestamp("2026-01-01", tz="UTC"), cadence="1d")
    assert not is_natural_market_time(MarketClass.BIST, pd.Timestamp("2026-01-01", tz="UTC"), cadence="1d")


def test_crypto_is_active_all_the_time() -> None:
    assert is_natural_market_time(
        MarketClass.CRYPTO,
        pd.Timestamp("2026-05-30 03:00:00", tz="UTC"),
        cadence="1h",
    )


def test_gold_futures_respects_weekly_close_and_daily_maintenance_break() -> None:
    assert is_natural_market_time(
        MarketClass.COMMODITY,
        pd.Timestamp("2026-05-28 16:30:00", tz="America/New_York"),
        cadence="1h",
    )
    assert not is_natural_market_time(
        MarketClass.COMMODITY,
        pd.Timestamp("2026-05-28 17:30:00", tz="America/New_York"),
        cadence="1h",
    )
    assert not is_natural_market_time(
        MarketClass.COMMODITY,
        pd.Timestamp("2026-05-30 12:00:00", tz="America/New_York"),
        cadence="1h",
    )


def test_forex_respects_weekend_close() -> None:
    assert is_natural_market_time(MarketClass.FOREX, pd.Timestamp("2026-05-29 21:00:00", tz="UTC"), cadence="1h")
    assert not is_natural_market_time(MarketClass.FOREX, pd.Timestamp("2026-05-29 22:30:00", tz="UTC"), cadence="1h")
    assert not is_natural_market_time(MarketClass.FOREX, pd.Timestamp("2026-05-31 21:30:00", tz="UTC"), cadence="1h")
    assert is_natural_market_time(MarketClass.FOREX, pd.Timestamp("2026-05-31 22:30:00", tz="UTC"), cadence="1h")
