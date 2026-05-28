from __future__ import annotations

from .models import Asset, MarketClass, SignalWeights, Thresholds

DEFAULT_ASSETS = [
    Asset(symbol="BTCUSDT", name="Bitcoin / Tether", market_class=MarketClass.CRYPTO, source="binance", cadence="1h"),
    Asset(symbol="ETHUSDT", name="Ethereum / Tether", market_class=MarketClass.CRYPTO, source="binance", cadence="1h"),
    Asset(symbol="AAPL", name="Apple", market_class=MarketClass.STOCK, source="yahoo", cadence="1d", exchange="NASDAQ", timezone="America/New_York"),
    Asset(symbol="MSFT", name="Microsoft", market_class=MarketClass.STOCK, source="yahoo", cadence="1d", exchange="NASDAQ", timezone="America/New_York"),
    Asset(symbol="^GSPC", name="S&P 500", market_class=MarketClass.INDEX, source="yahoo", cadence="1d", exchange="US", timezone="America/New_York"),
    Asset(symbol="GC=F", name="Gold Futures", market_class=MarketClass.COMMODITY, source="yahoo", cadence="1d", exchange="COMEX", timezone="America/New_York"),
    Asset(symbol="EURUSD=X", name="EUR/USD", market_class=MarketClass.FOREX, source="yahoo", cadence="1d", exchange="FX", timezone="UTC"),
    Asset(symbol="THYAO.IS", name="Turkish Airlines", market_class=MarketClass.BIST, source="yahoo", cadence="1d", exchange="XIST", timezone="Europe/Istanbul"),
    Asset(symbol="ASELS.IS", name="Aselsan", market_class=MarketClass.BIST, source="yahoo", cadence="1d", exchange="XIST", timezone="Europe/Istanbul"),
    Asset(symbol="BIMAS.IS", name="BIM", market_class=MarketClass.BIST, source="yahoo", cadence="1d", exchange="XIST", timezone="Europe/Istanbul"),
    Asset(symbol="TUPRS.IS", name="Tupras", market_class=MarketClass.BIST, source="yahoo", cadence="1d", exchange="XIST", timezone="Europe/Istanbul"),
]

DEFAULT_THRESHOLDS = {
    MarketClass.CRYPTO: Thresholds(score=2.4, follow_through_pct=2.0, lookahead_bars=8),
    MarketClass.STOCK: Thresholds(score=2.2, follow_through_pct=2.5, lookahead_bars=5),
    MarketClass.INDEX: Thresholds(score=2.0, follow_through_pct=1.2, lookahead_bars=5),
    MarketClass.FOREX: Thresholds(score=1.9, follow_through_pct=0.7, lookahead_bars=5),
    MarketClass.COMMODITY: Thresholds(score=2.1, follow_through_pct=1.5, lookahead_bars=5),
    MarketClass.BIST: Thresholds(score=2.4, follow_through_pct=3.0, lookahead_bars=5),
}

DEFAULT_WEIGHTS = {
    MarketClass.CRYPTO: SignalWeights(price=0.35, volume=0.25, volatility=0.2, short_move=0.2),
    MarketClass.STOCK: SignalWeights(price=0.4, volume=0.2, volatility=0.2, short_move=0.2),
    MarketClass.INDEX: SignalWeights(price=0.45, volume=0.1, volatility=0.25, short_move=0.2),
    MarketClass.FOREX: SignalWeights(price=0.45, volume=0.05, volatility=0.25, short_move=0.25),
    MarketClass.COMMODITY: SignalWeights(price=0.4, volume=0.15, volatility=0.25, short_move=0.2),
    MarketClass.BIST: SignalWeights(price=0.42, volume=0.22, volatility=0.18, short_move=0.18),
}
