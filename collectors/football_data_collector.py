from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from typing import Any
from urllib import error, parse, request
from zoneinfo import ZoneInfo

from models import Match, MatchResult, Standing, Team

from .fixture_collector import FixtureCollector, SUPPORTED_WINDOWS


class FootballDataCollector:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.football-data.org/v4",
        competition_code: str | None = None,
        timezone: str = "Asia/Tokyo",
        timeout: int = 15,
        retries: int = 2,
        sample_collector: FixtureCollector | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("FOOTBALL_DATA_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.competition_code = competition_code or os.getenv("FOOTBALL_DATA_COMPETITION_CODE", "WC")
        self.timezone = ZoneInfo(timezone)
        self.timeout = timeout
        self.retries = retries
        self.sample_collector = sample_collector or FixtureCollector(timezone=timezone)

    def collect_matches(
        self,
        window: str = "today",
        run_date: str | None = None,
    ) -> list[Match]:
        if window not in SUPPORTED_WINDOWS:
            raise ValueError(f"Unsupported fixture window: {window}")
        if not self.api_key:
            print("Warning: FOOTBALL_DATA_API_KEY missing, using local sample fixtures.")
            return self.sample_collector.collect(window=window, run_date=run_date)

        try:
            base_date = self.sample_collector._resolve_base_date(run_date)
            date_from, date_to = self._window_range(base_date=base_date, window=window)
            payload = self._fetch_json(
                f"/competitions/{self.competition_code}/matches",
                {
                    "dateFrom": date_from.isoformat(),
                    "dateTo": date_to.isoformat(),
                },
            )
            return [self._to_match(item) for item in payload.get("matches", [])]
        except Exception as exc:
            print(f"Warning: football-data.org matches failed, falling back to sample fixtures: {exc}")
            return self.sample_collector.collect(window=window, run_date=run_date)

    def collect_standings(self) -> list[Standing]:
        if not self.api_key:
            print("Warning: FOOTBALL_DATA_API_KEY missing, standings collection skipped.")
            return []

        try:
            payload = self._fetch_json(f"/competitions/{self.competition_code}/standings")
            standings: list[Standing] = []
            updated_at = datetime.now(UTC)
            for table in payload.get("standings", []):
                stage = self._normalize_stage(
                    table.get("stage"),
                    table.get("group"),
                )
                for row in table.get("table", []):
                    standings.append(self._to_standing(row=row, stage=stage, updated_at=updated_at))
            return standings
        except Exception as exc:
            print(f"Warning: football-data.org standings failed, continuing with empty standings: {exc}")
            return []

    def _fetch_json(self, path: str, query: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"

        headers = {
            "X-Auth-Token": self.api_key,
            "Accept": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            req = request.Request(url, headers=headers, method="GET")
            try:
                with request.urlopen(req, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8")
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("Unexpected football-data.org response shape")
                return data
            except (
                OSError,
                error.URLError,
                error.HTTPError,
                TimeoutError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def _window_range(self, base_date: datetime.date, window: str) -> tuple[datetime.date, datetime.date]:
        if window == "today":
            return base_date, base_date
        if window == "tomorrow":
            next_day = base_date.fromordinal(base_date.toordinal() + 1)
            return next_day, next_day
        end_day = base_date.fromordinal(base_date.toordinal() + 2)
        return base_date, end_day

    def _to_match(self, item: dict[str, Any]) -> Match:
        kickoff_at = self._parse_datetime(item.get("utcDate"))
        home_team = self._to_team(item.get("homeTeam", {}))
        away_team = self._to_team(item.get("awayTeam", {}))
        result = self._to_match_result(item.get("score", {}), item.get("status"))
        stage = self._normalize_stage(item.get("stage"), item.get("group"))
        area = item.get("area") or {}
        host_country = area.get("name")
        return Match(
            id=str(item.get("id", "")),
            competition=str(((item.get("competition") or {}).get("name")) or "FIFA World Cup"),
            stage=stage,
            venue=None,
            city=host_country,
            kickoff_at=kickoff_at,
            home_team=home_team,
            away_team=away_team,
            result=result,
            importance=None,
        )

    def _to_match_result(self, score: dict[str, Any], status: Any) -> MatchResult:
        full_time = score.get("fullTime") or {}
        winner = score.get("winner")
        winner_team_id: str | None = None
        if winner == "HOME_TEAM":
            winner_team_id = "home"
        elif winner == "AWAY_TEAM":
            winner_team_id = "away"
        return MatchResult(
            home_score=full_time.get("home"),
            away_score=full_time.get("away"),
            status=str(status or "scheduled").lower(),
            winner_team_id=winner_team_id,
            decided_by=str(score.get("duration")) if score.get("duration") else None,
        )

    def _to_standing(
        self,
        row: dict[str, Any],
        stage: str,
        updated_at: datetime,
    ) -> Standing:
        team = self._to_team(row.get("team", {}))
        return Standing(
            team=team,
            stage=stage,
            position=int(row.get("position", 0)),
            played=int(row.get("playedGames", 0)),
            won=int(row.get("won", 0)),
            drawn=int(row.get("draw", 0)),
            lost=int(row.get("lost", 0)),
            goals_for=int(row.get("goalsFor", 0)),
            goals_against=int(row.get("goalsAgainst", 0)),
            goal_difference=int(row.get("goalDifference", 0)),
            points=int(row.get("points", 0)),
            updated_at=updated_at,
        )

    def _to_team(self, item: dict[str, Any]) -> Team:
        return Team(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            short_name=item.get("shortName"),
            fifa_code=item.get("tla"),
            confederation=None,
            group_name=None,
            coach=None,
            ranking=None,
        )

    def _normalize_stage(self, stage: Any, group: Any) -> str:
        stage_text = str(stage or "").replace("_", " ").title().strip()
        if stage_text == "Group Stage" and group:
            return str(group)
        if stage_text:
            return stage_text
        if group:
            return str(group)
        return "Unknown Stage"

    def _parse_datetime(self, value: Any) -> datetime:
        if not value:
            return datetime.now(UTC)
        text = str(value)
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(self.timezone)
