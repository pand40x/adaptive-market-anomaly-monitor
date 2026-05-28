from __future__ import annotations

from datetime import date, timedelta, time
from zoneinfo import ZoneInfo

import holidays
import pandas as pd
from holidays.financial import NYSE

from .models import MarketClass


SESSION_RULES = {
    MarketClass.STOCK: ("America/New_York", time(9, 30), time(16, 0)),
    MarketClass.INDEX: ("America/New_York", time(9, 30), time(16, 0)),
    MarketClass.BIST: ("Europe/Istanbul", time(9, 40), time(18, 10)),
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
        return is_trading_day(market_class, ts.date())

    if market_class is MarketClass.FOREX:
        return _is_forex_time(ts)

    if market_class is MarketClass.COMMODITY:
        return _is_cme_globex_time(ts)

    timezone_name, start, end = SESSION_RULES.get(
        market_class,
        ("UTC", time(0, 0), time(23, 59)),
    )
    local = ts.tz_convert(ZoneInfo(timezone_name))
    if not is_trading_day(market_class, local.date()):
        return False
    end = _session_close_for(market_class, local.date(), end)
    current = local.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def is_trading_day(market_class: MarketClass, day: date) -> bool:
    if market_class is MarketClass.CRYPTO:
        return True
    if market_class is MarketClass.FOREX:
        return day.weekday() < 5
    if day.weekday() >= 5:
        return False
    if market_class in (MarketClass.STOCK, MarketClass.INDEX):
        return day not in NYSE(years=[day.year])
    if market_class is MarketClass.BIST:
        return day not in holidays.country_holidays("TR", years=[day.year])
    if market_class is MarketClass.COMMODITY:
        return day.weekday() < 5
    return day.weekday() < 5


def _timezone_for(market_class: MarketClass) -> ZoneInfo:
    if market_class is MarketClass.FOREX:
        return ZoneInfo("UTC")
    timezone_name = SESSION_RULES.get(market_class, ("UTC", time(0, 0), time(23, 59)))[0]
    return ZoneInfo(timezone_name)


def _session_close_for(market_class: MarketClass, day: date, default_close: time) -> time:
    if market_class in (MarketClass.STOCK, MarketClass.INDEX) and _is_us_half_day(day):
        return time(13, 0)
    if market_class is MarketClass.BIST and _is_bist_half_day(day):
        return time(12, 40)
    return default_close


def _is_bist_half_day(day: date) -> bool:
    tr_holidays = holidays.country_holidays("TR", years=[day.year])
    if day == date(day.year, 10, 28):
        return True
    tomorrow_name = tr_holidays.get(day + timedelta(days=1), "")
    return "Bayramı" in tomorrow_name


def _is_us_half_day(day: date) -> bool:
    if day.month == 12 and day.day == 24 and day.weekday() < 5:
        return True
    thanksgiving = _nth_weekday(day.year, 11, weekday=3, n=4)
    return day == thanksgiving + timedelta(days=1)


def _nth_weekday(year: int, month: int, *, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (n - 1))


def _is_forex_time(timestamp: pd.Timestamp) -> bool:
    utc = timestamp.tz_convert("UTC")
    weekday = utc.weekday()
    if weekday < 4:
        return True
    if weekday == 4 and utc.time() < time(22, 0):
        return True
    if weekday == 6 and utc.time() >= time(22, 0):
        return True
    return False


def _is_cme_globex_time(timestamp: pd.Timestamp) -> bool:
    eastern = timestamp.tz_convert(ZoneInfo("America/New_York"))
    weekday = eastern.weekday()
    current = eastern.time()
    if weekday == 5:
        return False
    if weekday == 6:
        return current >= time(18, 0)
    if weekday == 4:
        return current < time(17, 0)
    return not (time(17, 0) <= current < time(18, 0))
