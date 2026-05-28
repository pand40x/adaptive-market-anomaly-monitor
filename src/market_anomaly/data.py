from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf

from .models import Asset

BINANCE_URL = "https://api.binance.com/api/v3/klines"


def fetch_history(asset: Asset, years: int | None = None) -> pd.DataFrame:
    if asset.source == "binance":
        return fetch_binance_klines(asset.symbol, interval=asset.cadence, years=years or asset.lookback_years)
    if asset.source == "yahoo":
        return fetch_yahoo_history(asset.symbol, interval=asset.cadence, years=years or asset.lookback_years)
    raise ValueError(f"unsupported source: {asset.source}")


def fetch_binance_klines(
    symbol: str,
    *,
    interval: str = "1h",
    years: int = 3,
    end_time_ms: int | None = None,
) -> pd.DataFrame:
    interval_ms = _interval_to_ms(interval)
    end_ms = end_time_ms or int(utc_now().timestamp() * 1000)
    start_ms = end_ms - years * 365 * 24 * 60 * 60 * 1000
    rows: list[list[object]] = []

    while start_ms < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000,
            "startTime": start_ms,
            "endTime": end_ms,
        }
        response = requests.get(BINANCE_URL, params=params, timeout=20)
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        rows.extend(page)
        if len(page) < 1000:
            break
        last_close_time = int(page[-1][6])
        next_start = last_close_time + 1
        if next_start <= start_ms:
            next_start = start_ms + interval_ms
        start_ms = next_start

    frame = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    frame.index = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    return frame[["open", "high", "low", "close", "volume"]].astype(float)


def fetch_yahoo_history(symbol: str, *, interval: str = "1d", years: int = 3) -> pd.DataFrame:
    period = f"{years}y"
    frame = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if frame.empty:
        raise ValueError(f"no Yahoo Finance data returned for {symbol}")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [column[0] for column in frame.columns]
    frame = frame.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    if "volume" not in frame:
        frame["volume"] = 0.0
    frame.index = pd.to_datetime(frame.index, utc=True)
    return frame[["open", "high", "low", "close", "volume"]].astype(float)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _interval_to_ms(interval: str) -> int:
    unit = interval[-1]
    value = int(interval[:-1])
    multipliers = {
        "m": 60 * 1000,
        "h": 60 * 60 * 1000,
        "d": 24 * 60 * 60 * 1000,
        "w": 7 * 24 * 60 * 60 * 1000,
    }
    if unit not in multipliers:
        raise ValueError(f"unsupported Binance interval: {interval}")
    return value * multipliers[unit]
