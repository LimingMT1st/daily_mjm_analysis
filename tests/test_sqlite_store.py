from __future__ import annotations

from datetime import UTC, datetime

from models import DailyReportData, Match, MatchAnalysis, MatchResult, NewsItem, Standing, Team
from reports.manager import ReportArtifacts
from storage import ReportChanges, SQLiteStore


def build_store_report_data(now: datetime, status: str = "scheduled", news_url: str = "https://example.com/news-1", points: int = 6) -> DailyReportData:
    team_a = Team(id="jpn", name="Japan")
    team_b = Team(id="usa", name="United States")
    match = Match(
        id="fixture-001",
        competition="FIFA World Cup 2026",
        stage="Group A",
        city="Tokyo",
        kickoff_at=now,
        home_team=team_a,
        away_team=team_b,
        result=MatchResult(status=status, home_score=1 if status == "finished" else None, away_score=0 if status == "finished" else None),
    )
    standing = Standing(
        team=team_a,
        stage="Group A",
        position=1,
        played=2,
        won=2,
        drawn=0,
        lost=0,
        goals_for=4,
        goals_against=1,
        goal_difference=3,
        points=points,
        updated_at=now,
    )
    news_item = NewsItem(
        id="news-001",
        team_id="jpn",
        title="World Cup preview: Japan ready",
        summary="Japan enter the FIFA event with stable preparation.",
        source="Mock Feed",
        url=news_url,
        published_at=now,
    )
    analysis = MatchAnalysis(
        match_id="fixture-001",
        importance_score=88,
        upset_risk="medium",
        attention_level="A",
        qualification_impact=72,
        news_heat=66,
        explanation="这是一场高关注度比赛。",
        form_summary="双方近期状态接近。",
        generated_at=now,
    )
    return DailyReportData(
        report_date=now,
        timezone="Asia/Tokyo",
        language="zh-CN",
        focus_teams=[team_a],
        matches=[match],
        standings=[standing],
        news_items=[news_item],
        injury_items=[],
        team_forms=[],
        match_analyses=[analysis],
    )


def test_sqlite_store_deduplicates_news_and_overwrites_match(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "cache.db")
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    report_data = build_store_report_data(now=now)

    store.save_matches(report_data.matches)
    inserted_first = store.save_news_items(report_data.news_items)
    inserted_second = store.save_news_items(report_data.news_items)

    finished_report = build_store_report_data(now=now, status="finished")
    store.save_matches(finished_report.matches)

    with store._connect() as conn:
        news_count = conn.execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
        result_json = conn.execute(
            "SELECT result_json FROM matches WHERE match_id = ?",
            ("fixture-001",),
        ).fetchone()[0]

    assert inserted_first == 1
    assert inserted_second == 0
    assert news_count == 1
    assert '"status": "finished"' in result_json


def test_sqlite_store_saves_runs_and_computes_changes(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "cache.db")
    yesterday = datetime(2026, 6, 6, 12, 0, tzinfo=UTC)
    today = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)

    previous_data = build_store_report_data(now=yesterday, status="scheduled", news_url="https://example.com/news-old", points=4)
    previous_artifacts = ReportArtifacts(
        markdown_path=tmp_path / "old.md",
        html_path=tmp_path / "old.html",
        markdown_content="old",
        html_content="old",
    )
    store.save_report_run(
        report_data=previous_data,
        artifacts=previous_artifacts,
        ai_summary="old",
        send_results={"email": False, "feishu": False, "telegram": False, "wecom": False},
        changes=ReportChanges(1, [], []),
    )

    current_data = build_store_report_data(now=today, status="finished", news_url="https://example.com/news-new", points=6)
    previous_run = store.load_previous_run(current_data.report_date.date())
    changes = store.compute_changes(current_data, previous_run)

    assert changes.new_news_count == 1
    assert len(changes.match_status_changes) == 1
    assert len(changes.standings_changes) == 1
