from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class MarketClass(str, Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    INDEX = "index"
    FOREX = "forex"
    COMMODITY = "commodity"
    BIST = "bist"


class Asset(BaseModel):
    symbol: str
    market_class: MarketClass
    source: str
    cadence: str
    name: str | None = None
    exchange: str | None = None
    timezone: str = "UTC"
    lookback_years: int = 3


class SignalWeights(BaseModel):
    price: float = Field(ge=0)
    volume: float = Field(ge=0)
    volatility: float = Field(ge=0)
    short_move: float = Field(ge=0)

    @field_validator("short_move")
    @classmethod
    def _validate_sum(cls, value: float, info) -> float:
        values = info.data
        total = value + sum(float(values.get(name, 0.0)) for name in ("price", "volume", "volatility"))
        if total <= 0:
            raise ValueError("at least one weight must be positive")
        return value

    def normalized(self) -> "SignalWeights":
        total = self.price + self.volume + self.volatility + self.short_move
        return SignalWeights(
            price=self.price / total,
            volume=self.volume / total,
            volatility=self.volatility / total,
            short_move=self.short_move / total,
        )


class Thresholds(BaseModel):
    score: float = Field(gt=0)
    follow_through_pct: float = Field(gt=0)
    lookahead_bars: int = Field(gt=0)


class SignalBreakdown(BaseModel):
    price_deviation: float
    volume_expansion: float
    volatility_breakout: float
    short_move: float


class Alert(BaseModel):
    symbol: str
    asset_name: str | None = None
    market_class: MarketClass
    timestamp: datetime
    price: float
    score: float
    direction: str
    breakdown: SignalBreakdown
    explanation: str


class FollowThroughResult(BaseModel):
    symbol: str
    timestamp: datetime
    direction: str
    meaningful: bool
    max_move_pct: float
    bars_elapsed: int


class BacktestResult(BaseModel):
    symbol: str
    market_class: MarketClass
    alert_count: int
    meaningful_count: int
    precision: float
    noise_ratio: float = 0.0
    average_max_move_pct: float
    average_reaction_bars: float = 0.0
    thresholds: Thresholds
    weights: SignalWeights


class OptimizationResult(BacktestResult):
    objective: float


class ClassCalibrationResult(BaseModel):
    market_class: MarketClass
    asset_count: int
    alert_count: int
    meaningful_count: int
    precision: float
    noise_ratio: float
    average_max_move_pct: float
    average_reaction_bars: float
    thresholds: Thresholds
    weights: SignalWeights
    objective: float


class ActiveAnomaly(BaseModel):
    symbol: str
    asset_name: str | None = None
    market_class: MarketClass
    timestamp: datetime
    direction: str
    status: str
    score: float
    threshold_score: float
    follow_through_pct: float
    lookahead_bars: int
    observed_bars: int
    max_move_pct: float
    explanation: str
