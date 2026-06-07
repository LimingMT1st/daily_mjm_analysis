from __future__ import annotations

from .football_data_collector import FootballDataCollector
from .fixture_collector import FixtureCollector
from .news_collector import NewsCollector


class CollectorManager:
    def __init__(self, timezone: str = "Asia/Tokyo") -> None:
        self.fixture_collector = FixtureCollector(timezone=timezone)
        self.football_data_collector = FootballDataCollector(
            timezone=timezone,
            sample_collector=self.fixture_collector,
        )
        self.news_collector = NewsCollector(timezone=timezone)

    def collect(self, run_date: str | None = None) -> dict:
        return {
            "run_date": run_date,
            "matches": [],
            "standings": [],
            "news": [],
            "injuries": [],
        }

    def collect_fixtures(
        self, window: str = "today", run_date: str | None = None
    ) -> list:
        return self.football_data_collector.collect_matches(
            window=window,
            run_date=run_date,
        )

    def collect_standings(self) -> list:
        return self.football_data_collector.collect_standings()

    def collect_news(self, now=None) -> list:
        return self.news_collector.collect(now=now)
