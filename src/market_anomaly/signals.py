from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .models import Alert, MarketClass, SignalBreakdown, SignalWeights, Thresholds
from .sessions import is_natural_market_time

MIN_HISTORY = 40


def detect_anomalies(
    *,
    symbol: str,
    market_class: MarketClass,
    candles: pd.DataFrame,
    thresholds: Thresholds,
    weights: SignalWeights,
    cadence: str = "1d",
    asset_name: str | None = None,
) -> list[Alert]:
    frame = _prepare_candles(candles)
    if len(frame) < MIN_HISTORY:
        return []

    scored = score_candles(frame, weights)
    candidates: list[tuple[int, Alert]] = []
    for bar_index, (timestamp, row) in enumerate(scored.iterrows()):
        if not is_natural_market_time(market_class, timestamp, cadence=cadence):
            continue
        score = float(row["score"])
        if not math.isfinite(score) or score < thresholds.score:
            continue

        direction = "up" if float(row["return"]) >= 0 else "down"
        breakdown = SignalBreakdown(
            price_deviation=float(row["price_deviation"]),
            volume_expansion=float(row["volume_expansion"]),
            volatility_breakout=float(row["volatility_breakout"]),
            short_move=float(row["short_move"]),
        )
        candidates.append(
            (
                bar_index,
                Alert(
                    symbol=symbol,
                    asset_name=asset_name,
                    market_class=market_class,
                    timestamp=timestamp.to_pydatetime(),
                    price=float(row["close"]),
                    score=round(score, 4),
                    direction=direction,
                    breakdown=breakdown,
                    explanation=explain_alert(symbol, direction, score, breakdown),
                ),
            )
        )
    return _dedupe_adjacent_alerts(candidates, max_bar_gap=thresholds.lookahead_bars)


def score_candles(candles: pd.DataFrame, weights: SignalWeights) -> pd.DataFrame:
    frame = _prepare_candles(candles)
    normalized = weights.normalized()

    returns = frame["close"].pct_change()
    return_mean = returns.rolling(48, min_periods=24).mean()
    return_std = returns.rolling(48, min_periods=24).std(ddof=0).replace(0, np.nan)
    price_deviation = ((returns - return_mean) / return_std).abs().clip(upper=8)

    volume_base = frame["volume"].rolling(48, min_periods=24).median().replace(0, np.nan)
    volume_expansion = (frame["volume"] / volume_base).replace([np.inf, -np.inf], np.nan).clip(upper=8)

    short_vol = returns.rolling(8, min_periods=4).std(ddof=0)
    long_vol = returns.rolling(48, min_periods=24).std(ddof=0).replace(0, np.nan)
    volatility_breakout = (short_vol / long_vol).replace([np.inf, -np.inf], np.nan).clip(upper=8)

    short_move = (frame["close"].pct_change(6).abs() * 100 / 1.5).clip(upper=8)

    scored = frame.copy()
    scored["return"] = returns.fillna(0)
    scored["price_deviation"] = price_deviation.fillna(0)
    scored["volume_expansion"] = volume_expansion.fillna(0)
    scored["volatility_breakout"] = volatility_breakout.fillna(0)
    scored["short_move"] = short_move.fillna(0)
    scored["score"] = (
        scored["price_deviation"] * normalized.price
        + scored["volume_expansion"] * normalized.volume
        + scored["volatility_breakout"] * normalized.volatility
        + scored["short_move"] * normalized.short_move
    )
    return scored.iloc[MIN_HISTORY:]


def explain_alert(
    symbol: str,
    direction: str,
    score: float,
    breakdown: SignalBreakdown,
) -> str:
    move_word = "yukarı" if direction == "up" else "aşağı"
    drivers: list[str] = []
    if breakdown.price_deviation >= 2.5:
        drivers.append("fiyat normalinden ayrıştı")
    if breakdown.volume_expansion >= 2:
        drivers.append("hacim arttı")
    if breakdown.volatility_breakout >= 2:
        drivers.append("oynaklık yükseldi")
    if breakdown.short_move >= 2:
        drivers.append("kısa vadeli hareket hızlandı")
    if not drivers:
        drivers.append("birkaç sinyal aynı anda güçlendi")

    reason = ", ".join(drivers)
    return f"{symbol} için olağan dışı {move_word} hareket sinyali var. Özet: {reason}. Skor {score:.2f}."


def _prepare_candles(candles: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(candles.columns)
    if missing:
        raise ValueError(f"candles missing required columns: {', '.join(sorted(missing))}")

    frame = candles.copy()
    frame = frame.sort_index()
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("candles index must be a DatetimeIndex")
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("UTC")
    else:
        frame.index = frame.index.tz_convert("UTC")
    return frame[["open", "high", "low", "close", "volume"]].dropna()


def _dedupe_adjacent_alerts(alerts: list[tuple[int, Alert]], *, max_bar_gap: int) -> list[Alert]:
    deduped: list[tuple[int, Alert]] = []
    for bar_index, alert in alerts:
        if (
            deduped
            and alert.direction == deduped[-1][1].direction
            and bar_index - deduped[-1][0] <= max_bar_gap
        ):
            if alert.score > deduped[-1][1].score:
                deduped[-1] = (bar_index, alert)
            continue
        deduped.append((bar_index, alert))
    return [alert for _, alert in deduped]
