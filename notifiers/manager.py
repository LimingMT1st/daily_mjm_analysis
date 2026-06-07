from __future__ import annotations

from .email_notifier import EmailNotifier
from .telegram_notifier import TelegramNotifier
from .wecom_notifier import WeComNotifier


class NotifierManager:
    def __init__(self) -> None:
        self.email_notifier = EmailNotifier()
        self.telegram_notifier = TelegramNotifier()
        self.wecom_notifier = WeComNotifier()

    def notify(self, report: dict, dry_run: bool = False) -> None:
        if dry_run:
            print("Dry run enabled: notification step skipped.")
            return

        print("Notifier skeleton: no channels configured yet.")

    def send(self, title: str, content: str, html: str | None = None, dry_run: bool = False) -> dict[str, bool]:
        if dry_run:
            print("Dry run enabled: send step skipped.")
            return {"email": False, "telegram": False, "wecom": False}

        return {
            "email": self.email_notifier.send(title=title, content=content, html=html),
            "telegram": self.telegram_notifier.send(title=title, content=content, html=html),
            "wecom": self.wecom_notifier.send(title=title, content=content, html=html),
        }
