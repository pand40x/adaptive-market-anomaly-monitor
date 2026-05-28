from __future__ import annotations

from .models import Asset, MarketClass

DISPLAY_NAMES = {
    "BTCUSDT": "Bitcoin / Tether",
    "ETHUSDT": "Ethereum / Tether",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "^GSPC": "S&P 500",
    "GC=F": "Gold Futures",
    "EURUSD=X": "EUR/USD",
    "THYAO.IS": "Turkish Airlines",
    "ASELS.IS": "Aselsan",
    "BIMAS.IS": "BIM",
    "TUPRS.IS": "Tupras",
}

MARKET_LABELS = {
    MarketClass.CRYPTO: "Kripto",
    MarketClass.STOCK: "Hisse",
    MarketClass.INDEX: "Endeks",
    MarketClass.FOREX: "Forex",
    MarketClass.COMMODITY: "Emtia",
    MarketClass.BIST: "BIST",
}


def display_name_for(symbol: str, fallback: str | None = None) -> str:
    return DISPLAY_NAMES.get(symbol, fallback or symbol)


def market_label_for(market_class: MarketClass) -> str:
    return MARKET_LABELS[market_class]


def enrich_asset(asset: Asset) -> Asset:
    if asset.name:
        return asset
    return asset.model_copy(update={"name": display_name_for(asset.symbol)})
