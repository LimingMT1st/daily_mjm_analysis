from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import yaml

from models import NewsItem


DEFAULT_KEYWORDS = ["World Cup", "FIFA"]


class NewsCollector:
    def __init__(
        self,
        sources_path: str | Path = "config/sources.yaml",
        teams_path: str | Path = "config/teams.yaml",
        timezone: str = "Asia/Tokyo",
    ) -> None:
        self.sources_path = Path(sources_path)
        self.teams_path = Path(teams_path)
        self.timezone = ZoneInfo(timezone)

    def collect(self, now: datetime | None = None) -> list[NewsItem]:
        rss_sources = self._load_rss_sources()
        focus_teams = self._load_focus_teams()
        effective_now = now.astimezone(self.timezone) if now else datetime.now(self.timezone)
        cutoff = effective_now - timedelta(hours=48)

        results: list[NewsItem] = []
        seen_titles: set[str] = set()
        seen_urls: set[str] = set()
        keywords = [keyword.casefold() for keyword in DEFAULT_KEYWORDS + focus_teams]

        for source in rss_sources:
            parsed_feed = feedparser.parse(source["url"])
            for entry in parsed_feed.entries:
                title = self._as_text(entry.get("title"))
                summary = self._as_text(entry.get("summary") or entry.get("description"))
                url = self._as_text(entry.get("link"))
                normalized_title = title.strip().casefold()
                normalized_url = url.strip().casefold()

                if (
                    not title
                    or normalized_title in seen_titles
                    or (normalized_url and normalized_url in seen_urls)
                ):
                    continue
                if not self._matches_keywords(title=title, summary=summary, keywords=keywords):
                    continue

                published_at = self._parse_entry_datetime(entry, effective_now)
                if published_at < cutoff:
                    continue

                results.append(
                    NewsItem(
                        id=self._as_text(entry.get("id") or entry.get("link") or title),
                        team_id=self._match_team_id(title=title, summary=summary, focus_teams=focus_teams),
                        title=title,
                        summary=summary,
                        source=self._as_text(source.get("name")) or "RSS",
                        url=url,
                        published_at=published_at,
                        sentiment=None,
                    )
                )
                seen_titles.add(normalized_title)
                if normalized_url:
                    seen_urls.add(normalized_url)

        results.sort(key=lambda item: item.published_at, reverse=True)
        return results

    def _load_rss_sources(self) -> list[dict[str, str]]:
        data = self._read_yaml(self.sources_path)
        items = data.get("rss_sources", [])
        if not isinstance(items, list):
            return []

        sources: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = self._as_text(item.get("name")) or self._as_text(item.get("url"))
            url = self._as_text(item.get("url"))
            if url:
                sources.append({"name": name, "url": url})
        return sources

    def _load_focus_teams(self) -> list[str]:
        data = self._read_yaml(self.teams_path)
        items = data.get("focus_teams", [])
        if not isinstance(items, list):
            return []
        return [self._as_text(item) for item in items if self._as_text(item)]

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return data if isinstance(data, dict) else {}

    def _matches_keywords(self, title: str, summary: str, keywords: list[str]) -> bool:
        text = f"{title} {summary}".casefold()
        return any(keyword in text for keyword in keywords)

    def _parse_entry_datetime(self, entry: Any, fallback_now: datetime) -> datetime:
        if entry.get("published_parsed"):
            parsed = datetime(*entry.published_parsed[:6], tzinfo=UTC)
            return parsed.astimezone(self.timezone)
        if entry.get("updated_parsed"):
            parsed = datetime(*entry.updated_parsed[:6], tzinfo=UTC)
            return parsed.astimezone(self.timezone)

        for field_name in ("published", "updated"):
            raw_value = self._as_text(entry.get(field_name))
            if not raw_value:
                continue
            try:
                parsed = parsedate_to_datetime(raw_value)
            except (TypeError, ValueError, IndexError):
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(self.timezone)

        return fallback_now

    def _match_team_id(self, title: str, summary: str, focus_teams: list[str]) -> str | None:
        text = f"{title} {summary}".casefold()
        for team_name in focus_teams:
            if team_name.casefold() in text:
                return team_name
        return None

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
