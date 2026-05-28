from __future__ import annotations

from market_anomaly.assets import display_name_for, market_label_for
from market_anomaly.config import DEFAULT_ASSETS
from market_anomaly.models import MarketClass


def test_display_name_normalizes_yahoo_and_binance_symbols() -> None:
    assert display_name_for("GC=F") == "Gold Futures"
    assert display_name_for("EURUSD=X") == "EUR/USD"
    assert display_name_for("^GSPC") == "S&P 500"
    assert display_name_for("BTCUSDT") == "Bitcoin / Tether"
    assert display_name_for("THYAO.IS") == "Turkish Airlines"


def test_bist_assets_are_configured_as_their_own_market_class() -> None:
    bist_assets = [asset for asset in DEFAULT_ASSETS if asset.market_class is MarketClass.BIST]

    assert {asset.symbol for asset in bist_assets} >= {"THYAO.IS", "ASELS.IS", "BIMAS.IS", "TUPRS.IS"}
    assert all(asset.exchange == "XIST" for asset in bist_assets)
    assert all(asset.timezone == "Europe/Istanbul" for asset in bist_assets)


def test_market_label_uses_clear_turkish_names() -> None:
    assert market_label_for(MarketClass.BIST) == "BIST"
    assert market_label_for(MarketClass.COMMODITY) == "Emtia"
