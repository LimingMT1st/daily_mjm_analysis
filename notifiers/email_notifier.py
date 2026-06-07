from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        email_from: str | None = None,
        email_to: str | None = None,
    ) -> None:
        self.smtp_host = smtp_host if smtp_host is not None else os.getenv("SMTP_HOST", "")
        self.smtp_port = (
            smtp_port if smtp_port is not None else self._parse_port(os.getenv("SMTP_PORT", "587"))
        )
        self.smtp_username = (
            smtp_username if smtp_username is not None else os.getenv("SMTP_USERNAME", "")
        )
        self.smtp_password = (
            smtp_password if smtp_password is not None else os.getenv("SMTP_PASSWORD", "")
        )
        self.email_from = email_from if email_from is not None else os.getenv("EMAIL_FROM", "")
        self.email_to = email_to if email_to is not None else os.getenv("EMAIL_TO", "")

    def send(self, title: str, content: str, html: str | None = None) -> bool:
        if not self._is_configured():
            print("Warning: email notifier skipped because SMTP config is incomplete.")
            return False

        message = EmailMessage()
        message["Subject"] = title
        message["From"] = self.email_from
        message["To"] = self.email_to
        message.set_content(content)
        if html:
            message.add_alternative(html, subtype="html")

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if self.smtp_username:
                smtp.login(self.smtp_username, self.smtp_password)
            smtp.send_message(message)
        return True

    def _is_configured(self) -> bool:
        return all(
            [
                self.smtp_host,
                self.smtp_port,
                self.email_from,
                self.email_to,
            ]
        )

    def _parse_port(self, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return 587

