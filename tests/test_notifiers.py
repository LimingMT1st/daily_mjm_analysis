from __future__ import annotations

from email.message import EmailMessage

from notifiers import EmailNotifier, FeishuNotifier, TelegramNotifier, WeComNotifier


def test_email_notifier_skips_when_config_missing(capsys) -> None:
    notifier = EmailNotifier(
        smtp_host="",
        smtp_port=587,
        smtp_username="",
        smtp_password="",
        email_from="",
        email_to="",
    )

    result = notifier.send(title="Test", content="Hello")

    captured = capsys.readouterr()
    assert result is False
    assert "skipped" in captured.out


def test_email_notifier_sends_via_smtp(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockSMTP:
        def __init__(self, host, port, timeout=30):
            captured["host"] = host
            captured["port"] = port
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            captured["starttls"] = True

        def login(self, username, password):
            captured["username"] = username
            captured["password"] = password

        def send_message(self, message: EmailMessage):
            captured["subject"] = message["Subject"]
            captured["to"] = message["To"]

    monkeypatch.setattr("notifiers.email_notifier.smtplib.SMTP", MockSMTP)

    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="pass",
        email_from="from@example.com",
        email_to="to@example.com",
    )

    result = notifier.send(title="Daily Report", content="Hello", html="<p>Hello</p>")

    assert result is True
    assert captured["host"] == "smtp.example.com"
    assert captured["subject"] == "Daily Report"
    assert captured["to"] == "to@example.com"


def test_telegram_notifier_posts_message(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def mock_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        captured["body"] = req.data.decode("utf-8")
        return MockResponse()

    monkeypatch.setattr("notifiers.telegram_notifier.request.urlopen", mock_urlopen)

    notifier = TelegramNotifier(bot_token="bot-token", chat_id="12345")
    result = notifier.send(title="Daily Report", content="Hello Telegram")

    assert result is True
    assert "api.telegram.org" in captured["url"]
    assert "Daily Report" in captured["body"]


def test_feishu_notifier_skips_when_webhook_missing(capsys) -> None:
    notifier = FeishuNotifier(webhook_url="")

    result = notifier.send(title="Daily Report", content="Hello Feishu")

    captured = capsys.readouterr()
    assert result is False
    assert "skipped" in captured.out


def test_feishu_notifier_posts_text(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"StatusCode":0}'

    def mock_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        captured["body"] = req.data.decode("utf-8")
        return MockResponse()

    monkeypatch.setattr("notifiers.feishu_notifier.request.urlopen", mock_urlopen)

    notifier = FeishuNotifier(
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/example"
    )
    result = notifier.send(title="Daily Report", content="Hello Feishu")

    assert result is True
    assert "open.feishu.cn" in captured["url"]
    assert "interactive" in captured["body"]
    assert "Daily Report" in captured["body"]


def test_wecom_notifier_posts_markdown(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"errcode": 0}'

    def mock_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        captured["body"] = req.data.decode("utf-8")
        return MockResponse()

    monkeypatch.setattr("notifiers.wecom_notifier.request.urlopen", mock_urlopen)

    notifier = WeComNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc")
    result = notifier.send(title="Daily Report", content="Hello WeCom")

    assert result is True
    assert "webhook" in captured["url"]
    assert "Hello WeCom" in captured["body"]
