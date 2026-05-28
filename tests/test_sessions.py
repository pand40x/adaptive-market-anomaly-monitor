from __future__ import annotations

import pandas as pd

from market_anomaly.models import MarketClass
from market_anomaly.sessions import is_natural_market_time


def test_bist_intraday_timestamp_is_only_active_during_istanbul_session() -> None:
    assert is_natural_market_time(
        MarketClass.BIST,
        pd.Timestamp("2026-05-28 09:00:00", tz="Europe/Istanbul"),
        cadence="1h",
    )
    assert not is_natural_market_time(
        MarketClass.BIST,
        pd.Timestamp("2026-05-28 20:00:00", tz="Europe/Istanbul"),
        cadence="1h",
    )


def test_daily_yahoo_bars_are_accepted_on_weekdays_for_session_markets() -> None:
    assert is_natural_market_time(MarketClass.STOCK, pd.Timestamp("2026-05-28", tz="UTC"), cadence="1d")
    assert not is_natural_market_time(MarketClass.STOCK, pd.Timestamp("2026-05-30", tz="UTC"), cadence="1d")


def test_crypto_is_active_all_the_time() -> None:
    assert is_natural_market_time(
        MarketClass.CRYPTO,
        pd.Timestamp("2026-05-30 03:00:00", tz="UTC"),
        cadence="1h",
    )
