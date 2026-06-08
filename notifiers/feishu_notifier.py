from __future__ import annotations

import json
import os
from urllib import request


class FeishuNotifier:
    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = (
            webhook_url if webhook_url is not None else os.getenv("FEISHU_WEBHOOK_URL", "")
        )

    def send(self, title: str, content: str, html: str | None = None) -> bool:
        if not self.webhook_url:
            print("Warning: feishu notifier skipped because webhook is missing.")
            return False

        # Feishu custom bots reliably accept simple text payloads.
        text = f"{title}\n\n{content}"
        payload = {
            "msg_type": "text",
            "content": {
                "text": text[:4000],
            },
        }
        req = request.Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            response.read()
        return True
