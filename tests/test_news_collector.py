from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from collectors.news_collector import NewsCollector


def test_news_collector_filters_keywords_deduplicates_and_limits_to_48_hours(
    monkeypatch, tmp_path
) -> None:
    sources_path = tmp_path / "sources.yaml"
    teams_path = tmp_path / "teams.yaml"
    sources_path.write_text(
        "rss_sources:\n"
        "  - name: Mock Feed\n"
        "    url: https://example.com/rss.xml\n",
        encoding="utf-8",
    )
    teams_path.write_text(
        "focus_teams:\n"
        "  - Japan\n"
        "  - Mexico\n",
        encoding="utf-8",
    )

    entries = [
        {
            "title": "World Cup preview: Japan ready for opener",
            "summary": "Japan are preparing well for the FIFA event.",
            "link": "https://example.com/news/1",
            "published": "Sun, 07 Jun 2026 08:00:00 GMT",
        },
        {
            "title": "World Cup preview: Japan ready for opener",
            "summary": "Duplicate title should be removed.",
            "link": "https://example.com/news/duplicate",
            "published": "Sun, 07 Jun 2026 07:00:00 GMT",
        },
        {
            "title": "Mexico camp update ahead of FIFA match",
            "summary": "Squad morale is improving.",
            "link": "https://example.com/news/2",
            "published": "Sat, 06 Jun 2026 09:00:00 GMT",
        },
        {
            "title": "League transfer rumor roundup",
            "summary": "This should be filtered out.",
            "link": "https://example.com/news/3",
            "published": "Sun, 07 Jun 2026 06:00:00 GMT",
        },
        {
            "title": "Old FIFA feature story",
            "summary": "Too old for the 48-hour window.",
            "link": "https://example.com/news/4",
            "published": "Thu, 04 Jun 2026 08:00:00 GMT",
        },
    ]

    monkeypatch.setattr(
        "collectors.news_collector.feedparser.parse",
        lambda url: SimpleNamespace(entries=entries),
    )

    collector = NewsCollector(
        sources_path=sources_path,
        teams_path=teams_path,
        timezone="Asia/Tokyo",
    )

    news_items = collector.collect(now=datetime(2026, 6, 7, 21, 0, tzinfo=UTC))

    assert [item.title for item in news_items] == [
        "World Cup preview: Japan ready for opener",
        "Mexico camp update ahead of FIFA match",
    ]
    assert news_items[0].source == "Mock Feed"
    assert news_items[0].team_id == "Japan"
    assert news_items[1].team_id == "Mexico"


def test_news_collector_returns_newsitem_objects(monkeypatch, tmp_path) -> None:
    sources_path = tmp_path / "sources.yaml"
    teams_path = tmp_path / "teams.yaml"
    sources_path.write_text(
        "rss_sources:\n"
        "  - name: Mock Feed\n"
        "    url: https://example.com/rss.xml\n",
        encoding="utf-8",
    )
    teams_path.write_text("focus_teams:\n  - Canada\n", encoding="utf-8")

    monkeypatch.setattr(
        "collectors.news_collector.feedparser.parse",
        lambda url: SimpleNamespace(
            entries=[
                {
                    "title": "Canada World Cup training report",
                    "summary": "Canada completed a strong session.",
                    "link": "https://example.com/canada",
                    "published": "Sun, 07 Jun 2026 05:00:00 GMT",
                }
            ]
        ),
    )

    collector = NewsCollector(
        sources_path=sources_path,
        teams_path=teams_path,
        timezone="Asia/Tokyo",
    )

    news_items = collector.collect(now=datetime(2026, 6, 7, 12, 0, tzinfo=UTC))

    assert len(news_items) == 1
    assert news_items[0].title == "Canada World Cup training report"
    assert news_items[0].url == "https://example.com/canada"
