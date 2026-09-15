from __future__ import annotations

from typing import Optional

import requests

from . import Notifier


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, subject: str, message: str, html: Optional[str] = None) -> None:
        text = f"*{subject}*\n{message}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=15,
        )
        response.raise_for_status()
