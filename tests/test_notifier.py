from __future__ import annotations

from datetime import datetime, timezone

from market_anomaly.models import Alert, MarketClass, SignalBreakdown
from market_anomaly.notifier import TelegramNotifier, format_alerts_for_telegram


def _alert() -> Alert:
    return Alert(
        symbol="BTCUSDT",
        asset_name="Bitcoin / Tether",
        market_class=MarketClass.CRYPTO,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price=100_000,
        score=3.2,
        direction="up",
        breakdown=SignalBreakdown(
            price_deviation=3.1,
            volume_expansion=2.4,
            volatility_breakout=1.8,
            short_move=2.2,
        ),
        explanation="BTCUSDT shows an unusual upward move.",
    )


def test_format_alerts_for_telegram_is_short_clear_and_secret_free() -> None:
    message = format_alerts_for_telegram([_alert()])

    assert "<b>Anomali Uyarıları</b>" in message
    assert "Bitcoin / Tether" in message
    assert "BTCUSDT" in message
    assert "Yön: Yukarı" in message
    assert "Neden:" in message
    assert "Takip:" in message
    assert "price deviation" not in message.lower()
    assert "volatility breakout" not in message.lower()
    assert "100000" not in message
    assert "token" not in message.lower()


def test_telegram_notifier_skips_when_chat_id_is_missing(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("market_anomaly.notifier.requests.post", lambda *args, **kwargs: calls.append((args, kwargs)))

    notifier = TelegramNotifier(token="test-token", chat_id="")
    sent = notifier.send("hello")

    assert sent is False
    assert calls == []


def test_telegram_notifier_posts_html_message(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> FakeResponse:
        calls.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr("market_anomaly.notifier.requests.post", fake_post)

    notifier = TelegramNotifier(token="test-token", chat_id="123")
    sent = notifier.send("<b>hello</b>")

    assert sent is True
    assert calls[0][0] == "https://api.telegram.org/bottest-token/sendMessage"
    assert calls[0][1]["chat_id"] == "123"
    assert calls[0][1]["parse_mode"] == "HTML"
