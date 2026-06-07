from __future__ import annotations

import json
import os
from urllib import request


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        self.bot_token = (
            bot_token if bot_token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")
        )
        self.chat_id = chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID", "")

    def send(self, title: str, content: str, html: str | None = None) -> bool:
        if not self._is_configured():
            print("Warning: telegram notifier skipped because bot config is incomplete.")
            return False

        text = f"{title}\n\n{content}"
        payload = {
            "chat_id": self.chat_id,
            "text": text[:4000],
        }
        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            response.read()
        return True

    def _is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

