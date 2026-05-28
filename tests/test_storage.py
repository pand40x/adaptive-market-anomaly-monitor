from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

import pymongo

from market_anomaly.models import (
    ActiveAnomaly,
    ClassCalibrationResult,
    MarketClass,
    OptimizationResult,
    SignalWeights,
    Thresholds,
)
from market_anomaly.storage import MarketStore


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def create_index(self, *_args, **_kwargs) -> None:
        return None

    def update_one(self, selector: dict[str, object], update: dict[str, object], upsert: bool = False) -> None:
        document = next(
            (
                item
                for item in self.documents
                if all(item.get(key) == value for key, value in selector.items())
            ),
            None,
        )
        if document is None:
            if not upsert:
                return None
            document = dict(selector)
            self.documents.append(document)
        document.update(update["$set"])
        return None

    def find_one(self, selector: dict[str, object]) -> dict[str, object] | None:
        return next(
            (
                item
                for item in self.documents
                if all(item.get(key) == value for key, value in selector.items())
            ),
            None,
        )

    def find(self, selector: dict[str, object]) -> "FakeCursor":
        matches = [
            item
            for item in self.documents
            if all(item.get(key) == value for key, value in selector.items())
        ]
        return FakeCursor(matches)

    def delete_many(self, _selector: dict[str, object]) -> None:
        self.documents.clear()


class FakeCursor:
    def __init__(self, documents: Iterable[dict[str, object]]) -> None:
        self.documents = list(documents)

    def sort(self, key: str, direction: int) -> list[dict[str, object]]:
        reverse = direction == pymongo.DESCENDING
        return sorted(self.documents, key=lambda item: item[key], reverse=reverse)


class FakeDatabase(dict):
    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self:
            self[name] = FakeCollection()
        return dict.__getitem__(self, name)


class FakeClient(dict):
    def __getitem__(self, name: str) -> FakeDatabase:
        if name not in self:
            self[name] = FakeDatabase()
        return dict.__getitem__(self, name)

    def close(self) -> None:
        return None


def test_store_loads_saved_optimized_parameters(tmp_path) -> None:
    store = MarketStore(client=FakeClient(), db_name="test")
    result = OptimizationResult(
        symbol="BTCUSDT",
        market_class=MarketClass.CRYPTO,
        alert_count=5,
        meaningful_count=4,
        precision=0.8,
        average_max_move_pct=3.2,
        thresholds=Thresholds(score=2.6, follow_through_pct=2.1, lookahead_bars=8),
        weights=SignalWeights(price=0.5, volume=0.2, volatility=0.15, short_move=0.15),
        objective=0.77,
    )

    store.save_optimization(result)
    loaded = store.load_optimization("BTCUSDT")
    store.close()

    assert loaded is not None
    thresholds, weights = loaded
    assert thresholds.score == 2.6
    assert weights.price == 0.5


def test_store_loads_saved_class_calibration(tmp_path) -> None:
    store = MarketStore(client=FakeClient(), db_name="test")
    result = ClassCalibrationResult(
        market_class=MarketClass.CRYPTO,
        asset_count=2,
        alert_count=20,
        meaningful_count=14,
        precision=0.7,
        noise_ratio=0.3,
        average_max_move_pct=3.6,
        average_reaction_bars=2.4,
        thresholds=Thresholds(score=2.5, follow_through_pct=2.0, lookahead_bars=8),
        weights=SignalWeights(price=0.45, volume=0.25, volatility=0.15, short_move=0.15),
        objective=0.61,
    )

    store.save_class_calibration(result)
    loaded = store.load_class_calibration(MarketClass.CRYPTO)
    store.close()

    assert loaded is not None
    thresholds, weights = loaded
    assert thresholds.score == 2.5
    assert weights.volume == 0.25


def test_store_filters_active_anomalies_by_status(tmp_path) -> None:
    store = MarketStore(client=FakeClient(), db_name="test")
    pending = ActiveAnomaly(
        symbol="BTCUSDT",
        market_class=MarketClass.CRYPTO,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        direction="up",
        status="pending",
        score=3.1,
        threshold_score=2.4,
        follow_through_pct=2.0,
        lookahead_bars=8,
        observed_bars=2,
        max_move_pct=1.2,
        explanation="pending",
    )
    confirmed = pending.model_copy(
        update={
            "symbol": "ETHUSDT",
            "timestamp": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "status": "confirmed",
        }
    )

    store.save_active_anomalies([pending, confirmed])
    loaded = store.load_active_anomalies(status="pending")
    store.close()

    assert [anomaly.symbol for anomaly in loaded] == ["BTCUSDT"]


def test_saving_active_anomalies_replaces_stale_followups(tmp_path) -> None:
    store = MarketStore(client=FakeClient(), db_name="test")
    stale = ActiveAnomaly(
        symbol="BTCUSDT",
        market_class=MarketClass.CRYPTO,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        direction="up",
        status="expired",
        score=3.1,
        threshold_score=2.4,
        follow_through_pct=2.0,
        lookahead_bars=8,
        observed_bars=8,
        max_move_pct=0.4,
        explanation="stale",
    )
    current = stale.model_copy(
        update={
            "symbol": "ETHUSDT",
            "timestamp": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "status": "pending",
            "explanation": "current",
        }
    )

    store.save_active_anomalies([stale])
    store.save_active_anomalies([current])
    loaded = store.load_active_anomalies(status=None)
    store.close()

    assert [anomaly.symbol for anomaly in loaded] == ["ETHUSDT"]
