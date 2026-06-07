from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from models import Match


SUPPORTED_WINDOWS = {"today", "tomorrow", "next_3_days"}


class FixtureCollector:
    def __init__(
        self,
        sample_path: str | Path = "config/fixtures.sample.json",
        timezone: str = "Asia/Tokyo",
    ) -> None:
        self.sample_path = Path(sample_path)
        self.timezone = ZoneInfo(timezone)

    def load_matches(self) -> list[Match]:
        with self.sample_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        return [Match.model_validate(item) for item in payload]

    def collect(
        self,
        window: str = "today",
        run_date: str | None = None,
    ) -> list[Match]:
        if window not in SUPPORTED_WINDOWS:
            raise ValueError(f"Unsupported fixture window: {window}")

        matches = self.load_matches()
        base_date = self._resolve_base_date(run_date)
        return [
            match
            for match in matches
            if self._match_in_window(match=match, base_date=base_date, window=window)
        ]

    def _resolve_base_date(self, run_date: str | None) -> datetime.date:
        if run_date:
            return datetime.strptime(run_date, "%Y-%m-%d").date()
        return datetime.now(self.timezone).date()

    def _match_in_window(self, match: Match, base_date: datetime.date, window: str) -> bool:
        local_date = match.kickoff_at.astimezone(self.timezone).date()
        if window == "today":
            return local_date == base_date
        if window == "tomorrow":
            return local_date == base_date + timedelta(days=1)
        return base_date <= local_date <= base_date + timedelta(days=2)

