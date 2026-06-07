from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


load_dotenv()


DEFAULT_TIMEZONE = "Asia/Tokyo"
DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_SECTIONS = {
    "overview": True,
    "matches": True,
    "standings": True,
    "injuries": True,
    "news": True,
    "analysis": True,
    "alerts": True,
}
DEFAULT_ENABLED_SOURCES = {
    "schedule": True,
    "standings": True,
    "news": True,
    "injuries": True,
    "squad": True,
}
DEFAULT_SOURCE_NAMES = {
    "schedule": "football_data",
    "standings": "football_data",
    "news": "news_api",
    "injuries": "manual_placeholder",
    "squad": "manual_placeholder",
}
DEFAULT_PUSH_CHANNELS = {
    "email": False,
    "telegram": False,
    "wecom": False,
}
DEFAULT_FOCUS_TEAMS = ["Japan", "United States", "Mexico", "Canada"]
DEFAULT_RSS_SOURCES: list[dict[str, str]] = []


@dataclass(slots=True)
class SecretsConfig:
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    football_data_api_key: str = ""
    news_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wecom_webhook_url: str = ""


@dataclass(slots=True)
class AppConfig:
    timezone: str = DEFAULT_TIMEZONE
    language: str = DEFAULT_LANGUAGE
    focus_teams: list[str] = field(default_factory=lambda: list(DEFAULT_FOCUS_TEAMS))
    report_sections: dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_SECTIONS)
    )
    enabled_sources: dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_ENABLED_SOURCES)
    )
    source_names: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_SOURCE_NAMES)
    )
    push_channels: dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_PUSH_CHANNELS)
    )
    rss_sources: list[dict[str, str]] = field(
        default_factory=lambda: list(DEFAULT_RSS_SOURCES)
    )
    report_output_dir: str = "output"
    secrets: SecretsConfig = field(default_factory=SecretsConfig)

    def summary(self) -> dict[str, Any]:
        return {
            "timezone": self.timezone,
            "language": self.language,
            "focus_teams": self.focus_teams,
            "enabled_sections": [
                name for name, enabled in self.report_sections.items() if enabled
            ],
            "enabled_sources": [
                name for name, enabled in self.enabled_sources.items() if enabled
            ],
            "push_channels": [
                name for name, enabled in self.push_channels.items() if enabled
            ],
            "rss_source_count": len(self.rss_sources),
            "report_output_dir": self.report_output_dir,
            "secrets_configured": {
                "openai": bool(self.secrets.openai_api_key),
                "football_data": bool(self.secrets.football_data_api_key),
                "news_api": bool(self.secrets.news_api_key),
                "email": bool(self.secrets.smtp_host and self.secrets.smtp_username),
                "telegram": bool(
                    self.secrets.telegram_bot_token and self.secrets.telegram_chat_id
                ),
                "wecom": bool(self.secrets.wecom_webhook_url),
            },
        }


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _merge_bool_map(defaults: dict[str, bool], value: Any) -> dict[str, bool]:
    merged = dict(defaults)
    if isinstance(value, dict):
        for key, default_value in defaults.items():
            merged[key] = bool(value.get(key, default_value))
    return merged


def _merge_str_map(defaults: dict[str, str], value: Any) -> dict[str, str]:
    merged = dict(defaults)
    if isinstance(value, dict):
        for key, default_value in defaults.items():
            raw_value = value.get(key, default_value)
            merged[key] = str(raw_value)
    return merged


def _read_secrets_from_env() -> SecretsConfig:
    smtp_port_raw = os.getenv("SMTP_PORT", "587")
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587

    return SecretsConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        openai_model=os.getenv("OPENAI_MODEL", ""),
        football_data_api_key=os.getenv("FOOTBALL_DATA_API_KEY", ""),
        news_api_key=os.getenv("NEWS_API_KEY", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=smtp_port,
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        email_to=os.getenv("EMAIL_TO", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        wecom_webhook_url=os.getenv("WECOM_WEBHOOK_URL", ""),
    )


def _read_rss_sources(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return list(DEFAULT_RSS_SOURCES)

    sources: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        sources.append({"name": name or url, "url": url})
    return sources


def load_config(config_dir: str | Path = "config") -> AppConfig:
    base_dir = Path(config_dir)
    report_config = _read_yaml(base_dir / "report.yaml")
    sources_config = _read_yaml(base_dir / "sources.yaml")
    teams_config = _read_yaml(base_dir / "teams.yaml")

    focus_teams = teams_config.get("focus_teams", DEFAULT_FOCUS_TEAMS)
    if not isinstance(focus_teams, list):
        focus_teams = list(DEFAULT_FOCUS_TEAMS)

    timezone = str(report_config.get("timezone", DEFAULT_TIMEZONE))
    language = str(report_config.get("language", DEFAULT_LANGUAGE))
    report_output_dir = str(os.getenv("REPORT_OUTPUT_DIR", "output"))

    return AppConfig(
        timezone=timezone,
        language=language,
        focus_teams=[str(team) for team in focus_teams],
        report_sections=_merge_bool_map(
            DEFAULT_SECTIONS, report_config.get("sections", {})
        ),
        enabled_sources=_merge_bool_map(
            DEFAULT_ENABLED_SOURCES, sources_config.get("enabled_sources", {})
        ),
        source_names=_merge_str_map(
            DEFAULT_SOURCE_NAMES, sources_config.get("source_names", {})
        ),
        push_channels=_merge_bool_map(
            DEFAULT_PUSH_CHANNELS, report_config.get("push_channels", {})
        ),
        rss_sources=_read_rss_sources(sources_config.get("rss_sources", [])),
        report_output_dir=report_output_dir,
        secrets=_read_secrets_from_env(),
    )


def config_as_dict(config: AppConfig) -> dict[str, Any]:
    return asdict(config)
