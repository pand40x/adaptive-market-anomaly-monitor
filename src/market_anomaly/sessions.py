from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

import pandas as pd

from .models import MarketClass


SESSION_RULES = {
    MarketClass.STOCK: ("America/New_York", time(9, 30), time(16, 0)),
    MarketClass.INDEX: ("America/New_York", time(9, 30), time(16, 0)),
    MarketClass.BIST: ("Europe/Istanbul", time(9, 0), time(18, 15)),
    MarketClass.COMMODITY: ("America/New_York", time(18, 0), time(17, 0)),
}


def is_natural_market_time(
    market_class: MarketClass,
    timestamp: pd.Timestamp,
    *,
    cadence: str = "1d",
) -> bool:
    if market_class is MarketClass.CRYPTO:
        return True

    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")

    if cadence.endswith("d"):
        return ts.weekday() < 5

    if market_class is MarketClass.FOREX:
        utc = ts.tz_convert("UTC")
        weekday = utc.weekday()
        if weekday < 4:
            return True
        if weekday == 4 and utc.time() < time(22, 0):
            return True
        if weekday == 6 and utc.time() >= time(22, 0):
            return True
        return False

    timezone_name, start, end = SESSION_RULES.get(
        market_class,
        ("UTC", time(0, 0), time(23, 59)),
    )
    local = ts.tz_convert(ZoneInfo(timezone_name))
    if local.weekday() >= 5:
        return False
    current = local.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _timezone_for(market_class: MarketClass) -> ZoneInfo:
    if market_class is MarketClass.FOREX:
        return ZoneInfo("UTC")
    timezone_name = SESSION_RULES.get(market_class, ("UTC", time(0, 0), time(23, 59)))[0]
    return ZoneInfo(timezone_name)
