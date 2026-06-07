from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from models import DailyReportData, Match, MatchAnalysis, NewsItem, Standing


@dataclass(slots=True)
class ReportChanges:
    new_news_count: int
    match_status_changes: list[str]
    standings_changes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "new_news_count": self.new_news_count,
            "match_status_changes": self.match_status_changes,
            "standings_changes": self.standings_changes,
        }


class SQLiteStore:
    def __init__(self, db_path: str | Path = "storage/worldcup_cache.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    match_id TEXT PRIMARY KEY,
                    competition TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    venue TEXT,
                    city TEXT,
                    kickoff_at TEXT NOT NULL,
                    home_team_json TEXT NOT NULL,
                    away_team_json TEXT NOT NULL,
                    result_json TEXT,
                    importance TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS news_items (
                    url TEXT PRIMARY KEY,
                    news_id TEXT NOT NULL,
                    team_id TEXT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    report_date TEXT NOT NULL,
                    match_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (report_date, match_id)
                );

                CREATE TABLE IF NOT EXISTS report_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT NOT NULL,
                    run_at TEXT NOT NULL,
                    matches_json TEXT NOT NULL,
                    news_items_json TEXT NOT NULL,
                    standings_json TEXT NOT NULL,
                    analyses_json TEXT NOT NULL,
                    ai_summary TEXT NOT NULL,
                    markdown_path TEXT NOT NULL,
                    html_path TEXT NOT NULL,
                    send_results_json TEXT NOT NULL,
                    changes_json TEXT NOT NULL
                );
                """
            )

    def save_matches(self, matches: list[Match]) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            for match in matches:
                result_json = (
                    json.dumps(match.result.model_dump(mode="json"), ensure_ascii=False)
                    if match.result is not None
                    else None
                )
                conn.execute(
                    """
                    INSERT INTO matches (
                        match_id, competition, stage, venue, city, kickoff_at,
                        home_team_json, away_team_json, result_json, importance, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(match_id) DO UPDATE SET
                        competition=excluded.competition,
                        stage=excluded.stage,
                        venue=excluded.venue,
                        city=excluded.city,
                        kickoff_at=excluded.kickoff_at,
                        home_team_json=excluded.home_team_json,
                        away_team_json=excluded.away_team_json,
                        result_json=excluded.result_json,
                        importance=excluded.importance,
                        updated_at=excluded.updated_at
                    """,
                    (
                        match.id,
                        match.competition,
                        match.stage,
                        match.venue,
                        match.city,
                        match.kickoff_at.isoformat(),
                        json.dumps(match.home_team.model_dump(mode="json"), ensure_ascii=False),
                        json.dumps(match.away_team.model_dump(mode="json"), ensure_ascii=False),
                        result_json,
                        match.importance,
                        now,
                    ),
                )

    def save_news_items(self, news_items: list[NewsItem]) -> int:
        inserted = 0
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            for item in news_items:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO news_items (
                        url, news_id, team_id, title, summary, source,
                        published_at, payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.url,
                        item.id,
                        item.team_id,
                        item.title,
                        item.summary,
                        item.source,
                        item.published_at.isoformat(),
                        json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
                        now,
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def save_analyses(
        self,
        report_date: date,
        analyses: list[MatchAnalysis],
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            for analysis in analyses:
                conn.execute(
                    """
                    INSERT INTO analyses (report_date, match_id, payload_json, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_date, match_id) DO UPDATE SET
                        payload_json=excluded.payload_json,
                        created_at=excluded.created_at
                    """,
                    (
                        report_date.isoformat(),
                        analysis.match_id,
                        json.dumps(analysis.model_dump(mode="json"), ensure_ascii=False),
                        created_at,
                    ),
                )

    def load_previous_run(self, current_report_date: date) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM report_runs
                WHERE report_date < ?
                ORDER BY report_date DESC, run_id DESC
                LIMIT 1
                """,
                (current_report_date.isoformat(),),
            ).fetchone()

        if row is None:
            return None

        return {
            "report_date": row["report_date"],
            "run_at": row["run_at"],
            "matches": json.loads(row["matches_json"]),
            "news_items": json.loads(row["news_items_json"]),
            "standings": json.loads(row["standings_json"]),
            "analyses": json.loads(row["analyses_json"]),
            "ai_summary": row["ai_summary"],
            "markdown_path": row["markdown_path"],
            "html_path": row["html_path"],
            "send_results": json.loads(row["send_results_json"]),
            "changes": json.loads(row["changes_json"]),
        }

    def compute_changes(
        self,
        report_data: DailyReportData,
        previous_run: dict[str, Any] | None,
    ) -> ReportChanges:
        if previous_run is None:
            return ReportChanges(
                new_news_count=len(report_data.news_items),
                match_status_changes=[],
                standings_changes=[],
            )

        previous_news_urls = {
            item.get("url", "") for item in previous_run.get("news_items", [])
        }
        new_news_count = sum(
            1 for item in report_data.news_items if item.url not in previous_news_urls
        )

        previous_matches = {
            item.get("id"): item for item in previous_run.get("matches", [])
        }
        match_status_changes: list[str] = []
        for match in report_data.matches:
            previous = previous_matches.get(match.id)
            if previous is None:
                continue
            previous_result = previous.get("result") or {}
            current_result = (
                match.result.model_dump(mode="json") if match.result is not None else {}
            )
            previous_status = previous_result.get("status")
            current_status = current_result.get("status")
            previous_score = (
                previous_result.get("home_score"),
                previous_result.get("away_score"),
            )
            current_score = (
                current_result.get("home_score"),
                current_result.get("away_score"),
            )
            if previous_status != current_status or previous_score != current_score:
                match_status_changes.append(
                    f"{match.home_team.name} vs {match.away_team.name}: "
                    f"{previous_status or 'unknown'} {previous_score[0]}-{previous_score[1]} "
                    f"-> {current_status or 'unknown'} {current_score[0]}-{current_score[1]}"
                )

        previous_standings = {
            item.get("team", {}).get("id"): item
            for item in previous_run.get("standings", [])
        }
        standings_changes: list[str] = []
        for standing in report_data.standings:
            previous = previous_standings.get(standing.team.id)
            if previous is None:
                continue
            if (
                previous.get("position") != standing.position
                or previous.get("points") != standing.points
                or previous.get("goal_difference") != standing.goal_difference
            ):
                standings_changes.append(
                    f"{standing.team.name}: 排名 {previous.get('position')} -> {standing.position}，"
                    f"积分 {previous.get('points')} -> {standing.points}，"
                    f"净胜球 {previous.get('goal_difference')} -> {standing.goal_difference}"
                )

        return ReportChanges(
            new_news_count=new_news_count,
            match_status_changes=match_status_changes,
            standings_changes=standings_changes,
        )

    def save_report_run(
        self,
        report_data: DailyReportData,
        artifacts: Any,
        ai_summary: str,
        send_results: dict[str, bool],
        changes: ReportChanges,
    ) -> None:
        report_date = report_data.report_date.date().isoformat()
        run_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_runs (
                    report_date, run_at, matches_json, news_items_json,
                    standings_json, analyses_json, ai_summary, markdown_path,
                    html_path, send_results_json, changes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_date,
                    run_at,
                    json.dumps(
                        [item.model_dump(mode="json") for item in report_data.matches],
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        [item.model_dump(mode="json") for item in report_data.news_items],
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        [item.model_dump(mode="json") for item in report_data.standings],
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        [item.model_dump(mode="json") for item in report_data.match_analyses],
                        ensure_ascii=False,
                    ),
                    ai_summary,
                    str(artifacts.markdown_path),
                    str(artifacts.html_path),
                    json.dumps(send_results, ensure_ascii=False),
                    json.dumps(changes.to_dict(), ensure_ascii=False),
                ),
            )
