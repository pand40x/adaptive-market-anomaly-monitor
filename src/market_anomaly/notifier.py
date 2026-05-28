from __future__ import annotations

import html
import os
from pathlib import Path

import requests

from .models import Alert
from .assets import display_name_for, market_label_for


def load_local_env(path: Path = Path(".env.local")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip().replace("-", "_")
        os.environ.setdefault(normalized_key, value.strip().strip('"').strip("'"))


def telegram_from_env() -> "TelegramNotifier":
    load_local_env()
    return TelegramNotifier(
        token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
    )


def format_alerts_for_telegram(alerts: list[Alert], limit: int = 8) -> str:
    shown = alerts[-limit:]
    lines = ["<b>Anomali Uyarıları</b>"]
    for alert in shown:
        asset_name = html.escape(alert.asset_name or display_name_for(alert.symbol))
        symbol = html.escape(alert.symbol)
        market = html.escape(market_label_for(alert.market_class))
        direction = "yükseliş" if alert.direction == "up" else "düşüş"
        summary = html.escape(_plain_summary(alert))
        lines.append(
            f"<b>{asset_name}</b> <code>{symbol}</code>\n"
            f"{market} piyasasında olağan dışı {direction} sinyali.\n"
            f"{summary}. Hareketin devamı izleniyor."
        )
    if len(alerts) > limit:
        lines.append(f"{len(alerts) - limit} eski alarm gizlendi.")
    message = "\n\n".join(lines)
    return message[:4000]


def _plain_summary(alert: Alert) -> str:
    price = alert.breakdown.price_deviation >= 3
    volume = alert.breakdown.volume_expansion >= 2
    volatility = alert.breakdown.volatility_breakout >= 2
    short_move = alert.breakdown.short_move >= 2

    if price and volume and (short_move or volatility):
        return "Fiyat ve hacim birlikte hızlandı"
    if price and volume:
        return "Fiyat hareketi hacimle desteklendi"
    if short_move and volatility:
        return "Kısa vadeli hareket güç kazandı"
    if price:
        return "Fiyat normal davranışından belirgin ayrıştı"
    if volume:
        return "Hacim olağanın üstüne çıktı"
    return "Birden fazla sinyal aynı anda güçlendi"


class TelegramNotifier:
    def __init__(self, *, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    def send(self, message: str) -> bool:
        if not self.token or not self.chat_id or not message:
            return False
        response = requests.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        response.raise_for_status()
        return True

    def discover_chat_ids(self) -> list[str]:
        if not self.token:
            return []
        response = requests.get(
            f"https://api.telegram.org/bot{self.token}/getUpdates",
            params={"limit": 10},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        chat_ids: list[str] = []
        for update in data.get("result", []):
            message = update.get("message") or update.get("edited_message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is not None:
                value = str(chat_id)
                if value not in chat_ids:
                    chat_ids.append(value)
        return chat_ids
