from __future__ import annotations

import pandas as pd

from .backtest import evaluate_follow_through
from .models import ActiveAnomaly, Alert, Thresholds


def evaluate_active_anomaly(
    *,
    candles: pd.DataFrame,
    alert: Alert,
    thresholds: Thresholds,
) -> ActiveAnomaly:
    frame = candles.sort_index()
    timestamp = pd.Timestamp(alert.timestamp)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")

    indexer = frame.index.get_indexer([timestamp], method="nearest")
    start = int(indexer[0]) if len(indexer) and indexer[0] >= 0 else len(frame) - 1
    observed_bars = max(0, min(len(frame.iloc[start + 1 :]), thresholds.lookahead_bars))
    result = evaluate_follow_through(candles=frame, alert=alert, thresholds=thresholds)
    if result.meaningful:
        status = "confirmed"
    elif observed_bars < thresholds.lookahead_bars:
        status = "pending"
    else:
        status = "expired"

    return ActiveAnomaly(
        symbol=alert.symbol,
        asset_name=alert.asset_name,
        market_class=alert.market_class,
        timestamp=alert.timestamp,
        direction=alert.direction,
        status=status,
        score=alert.score,
        threshold_score=thresholds.score,
        follow_through_pct=thresholds.follow_through_pct,
        lookahead_bars=thresholds.lookahead_bars,
        observed_bars=observed_bars,
        max_move_pct=result.max_move_pct,
        explanation=alert.explanation,
    )
