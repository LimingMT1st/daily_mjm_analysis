from __future__ import annotations

import json
import os
from urllib import request


class WeComNotifier:
    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = (
            webhook_url if webhook_url is not None else os.getenv("WECOM_WEBHOOK_URL", "")
        )

    def send(self, title: str, content: str, html: str | None = None) -> bool:
        if not self.webhook_url:
            print("Warning: wecom notifier skipped because webhook is missing.")
            return False

        text = f"{title}\n\n{content}"
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": text[:4000],
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

