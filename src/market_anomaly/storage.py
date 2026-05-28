from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pandas as pd
import pymongo
from pymongo import MongoClient

from .models import (
    Alert,
    ActiveAnomaly,
    ClassCalibrationResult,
    FollowThroughResult,
    MarketClass,
    OptimizationResult,
    SignalBreakdown,
    SignalWeights,
    Thresholds,
)

DEFAULT_MONGO_URI = "mongodb://localhost:27018/market_anomaly"
DEFAULT_MONGO_DATABASE = "market_anomaly"


class MarketStore:
    def __init__(
        self,
        *,
        uri: str | None = None,
        db_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.client = client or MongoClient(uri or os.environ.get("MONGO_URI", DEFAULT_MONGO_URI))
        self.db = self.client[db_name or os.environ.get("MONGO_DATABASE", DEFAULT_MONGO_DATABASE)]
        self._create_indexes()

    def close(self) -> None:
        self.client.close()

    def save_candles(self, symbol: str, market_class: MarketClass, candles: pd.DataFrame) -> None:
        collection = self.db["candles"]
        for timestamp, row in candles.iterrows():
            ts = _to_datetime(timestamp)
            collection.update_one(
                {"symbol": symbol, "timestamp": ts},
                {
                    "$set": {
                        "symbol": symbol,
                        "market_class": market_class.value,
                        "timestamp": ts,
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": float(row.volume),
                    }
                },
                upsert=True,
            )

    def load_candles(self, symbol: str) -> pd.DataFrame:
        rows = list(self.db["candles"].find({"symbol": symbol}).sort("timestamp", pymongo.ASCENDING))
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        frame = pd.DataFrame(
            [
                {
                    "timestamp": row["timestamp"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
                for row in rows
            ]
        )
        frame.index = pd.to_datetime(frame.pop("timestamp"), utc=True)
        return frame.astype(float)

    def save_alerts(self, alerts: list[Alert]) -> None:
        collection = self.db["alerts"]
        for alert in alerts:
            timestamp = _to_datetime(alert.timestamp)
            collection.update_one(
                {"symbol": alert.symbol, "timestamp": timestamp},
                {
                    "$set": {
                        "symbol": alert.symbol,
                        "asset_name": alert.asset_name,
                        "market_class": alert.market_class.value,
                        "timestamp": timestamp,
                        "price": alert.price,
                        "score": alert.score,
                        "direction": alert.direction,
                        "explanation": alert.explanation,
                        "breakdown": alert.breakdown.model_dump(),
                    }
                },
                upsert=True,
            )

    def load_alerts(self, symbol: str, limit: int = 100) -> list[Alert]:
        rows = list(
            self.db["alerts"].find({"symbol": symbol}).sort("timestamp", pymongo.DESCENDING)
        )[:limit]
        alerts = [
            Alert(
                symbol=row["symbol"],
                asset_name=row.get("asset_name"),
                market_class=MarketClass(row["market_class"]),
                timestamp=row["timestamp"],
                price=row["price"],
                score=row["score"],
                direction=row["direction"],
                explanation=row["explanation"],
                breakdown=SignalBreakdown.model_validate(row["breakdown"]),
            )
            for row in rows
        ]
        return list(reversed(alerts))

    def save_active_anomalies(self, active_anomalies: list[ActiveAnomaly]) -> None:
        collection = self.db["active_anomalies"]
        collection.delete_many({})
        for anomaly in active_anomalies:
            timestamp = _to_datetime(anomaly.timestamp)
            collection.update_one(
                {"symbol": anomaly.symbol, "timestamp": timestamp},
                {
                    "$set": {
                        **anomaly.model_dump(mode="json"),
                        "timestamp": timestamp,
                    }
                },
                upsert=True,
            )

    def load_active_anomalies(self, status: str | None = None, limit: int = 100) -> list[ActiveAnomaly]:
        query = {"status": status} if status else {}
        rows = list(
            self.db["active_anomalies"].find(query).sort("timestamp", pymongo.DESCENDING)
        )[:limit]
        return [ActiveAnomaly.model_validate(row) for row in rows]

    def save_evaluations(self, evaluations: list[FollowThroughResult]) -> None:
        collection = self.db["alert_evaluations"]
        for result in evaluations:
            timestamp = _to_datetime(result.timestamp)
            collection.update_one(
                {"symbol": result.symbol, "timestamp": timestamp},
                {
                    "$set": {
                        "symbol": result.symbol,
                        "timestamp": timestamp,
                        "direction": result.direction,
                        "meaningful": result.meaningful,
                        "max_move_pct": result.max_move_pct,
                        "bars_elapsed": result.bars_elapsed,
                    }
                },
                upsert=True,
            )

    def save_optimization(self, result: OptimizationResult) -> None:
        self.db["optimized_parameters"].update_one(
            {"symbol": result.symbol},
            {
                "$set": {
                    "symbol": result.symbol,
                    "market_class": result.market_class.value,
                    "thresholds": result.thresholds.model_dump(),
                    "weights": result.weights.model_dump(),
                    "metrics": {
                        "alert_count": result.alert_count,
                        "meaningful_count": result.meaningful_count,
                        "precision": result.precision,
                        "noise_ratio": result.noise_ratio,
                        "average_max_move_pct": result.average_max_move_pct,
                        "average_reaction_bars": result.average_reaction_bars,
                        "objective": result.objective,
                    },
                }
            },
            upsert=True,
        )

    def load_optimization(self, symbol: str) -> tuple[Thresholds, SignalWeights] | None:
        row = self.db["optimized_parameters"].find_one({"symbol": symbol})
        if row is None:
            return None
        return Thresholds.model_validate(row["thresholds"]), SignalWeights.model_validate(row["weights"])

    def save_class_calibration(self, result: ClassCalibrationResult) -> None:
        self.db["class_calibrations"].update_one(
            {"market_class": result.market_class.value},
            {
                "$set": {
                    "market_class": result.market_class.value,
                    "thresholds": result.thresholds.model_dump(),
                    "weights": result.weights.model_dump(),
                    "metrics": {
                        "asset_count": result.asset_count,
                        "alert_count": result.alert_count,
                        "meaningful_count": result.meaningful_count,
                        "precision": result.precision,
                        "noise_ratio": result.noise_ratio,
                        "average_max_move_pct": result.average_max_move_pct,
                        "average_reaction_bars": result.average_reaction_bars,
                        "objective": result.objective,
                    },
                }
            },
            upsert=True,
        )

    def load_class_calibration(self, market_class: MarketClass) -> tuple[Thresholds, SignalWeights] | None:
        row = self.db["class_calibrations"].find_one({"market_class": market_class.value})
        if row is None:
            return None
        return Thresholds.model_validate(row["thresholds"]), SignalWeights.model_validate(row["weights"])

    def _create_indexes(self) -> None:
        self.db["candles"].create_index([("symbol", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)], unique=True)
        self.db["alerts"].create_index([("symbol", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)], unique=True)
        self.db["active_anomalies"].create_index([("symbol", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)], unique=True)
        self.db["alert_evaluations"].create_index(
            [("symbol", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)],
            unique=True,
        )
        self.db["optimized_parameters"].create_index("symbol", unique=True)
        self.db["class_calibrations"].create_index("market_class", unique=True)


def _to_datetime(value: object) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.to_pydatetime()
