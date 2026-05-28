from __future__ import annotations

import html
import os
from pathlib import Path

import requests

from .models import Alert


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
    lines = ["<b>Market anomaly alerts</b>"]
    for alert in shown:
        direction = "up" if alert.direction == "up" else "down"
        symbol = html.escape(alert.symbol)
        market = html.escape(alert.market_class.value)
        explanation = html.escape(alert.explanation)
        lines.append(
            f"<b>{symbol}</b> ({market}) {direction}, score {alert.score:.2f}\n"
            f"{explanation}"
        )
    if len(alerts) > limit:
        lines.append(f"{len(alerts) - limit} older alerts omitted.")
    message = "\n\n".join(lines)
    return message[:4000]


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
