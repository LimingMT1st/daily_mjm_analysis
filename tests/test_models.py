from __future__ import annotations

from datetime import UTC, datetime

import pytest

from models import (
    DailyReportData,
    InjuryItem,
    Match,
    MatchAnalysis,
    MatchResult,
    NewsItem,
    Standing,
    Team,
    TeamForm,
)


def test_models_can_be_created_and_serialized() -> None:
    now = datetime(2026, 6, 7, 19, 30, tzinfo=UTC)
    home_team = Team(
        id="jpn",
        name="Japan",
        short_name="Japan",
        fifa_code="JPN",
        confederation="AFC",
        group_name="Group A",
        coach="Hajime Moriyasu",
        ranking=15,
    )
    away_team = Team(
        id="usa",
        name="United States",
        short_name="USA",
        fifa_code="USA",
        confederation="CONCACAF",
        group_name="Group A",
        coach="Mauricio Pochettino",
        ranking=12,
    )
    result = MatchResult(
        home_score=2,
        away_score=1,
        status="finished",
        winner_team_id="jpn",
        decided_by="regular_time",
    )
    match = Match(
        id="match-001",
        competition="FIFA World Cup 2026",
        stage="Group Stage",
        venue="National Stadium",
        city="Tokyo",
        kickoff_at=now,
        home_team=home_team,
        away_team=away_team,
        result=result,
        importance="high",
    )
    standing = Standing(
        team=home_team,
        stage="Group A",
        position=1,
        played=3,
        won=2,
        drawn=1,
        lost=0,
        goals_for=6,
        goals_against=2,
        goal_difference=4,
        points=7,
        updated_at=now,
    )
    news_item = NewsItem(
        id="news-001",
        team_id="jpn",
        title="Japan squad remains fully fit",
        summary="Training intensity is high and morale looks strong.",
        source="Example News",
        url="https://example.com/news/japan",
        published_at=now,
        sentiment="positive",
    )
    injury_item = InjuryItem(
        id="injury-001",
        team_id="usa",
        player_name="Player A",
        status="doubtful",
        issue="Minor muscle tightness",
        expected_return_at=now,
        updated_at=now,
        source="Team report",
    )
    team_form = TeamForm(
        team_id="jpn",
        recent_results=["W", "W", "D", "W", "L"],
        unbeaten_streak=4,
        wins_in_last_five=3,
        goals_scored_last_five=9,
        goals_conceded_last_five=4,
        updated_at=now,
    )
    analysis = MatchAnalysis(
        match_id="match-001",
        importance_score=88,
        upset_risk="medium",
        attention_level="S",
        qualification_impact=82,
        news_heat=74,
        explanation="Japan and the United States are both in focus and news heat is high.",
        form_summary="Japan are in better recent form than the United States.",
        generated_at=now,
    )

    report_data = DailyReportData(
        report_date=now,
        timezone="Asia/Tokyo",
        language="zh-CN",
        focus_teams=[home_team, away_team],
        matches=[match],
        standings=[standing],
        news_items=[news_item],
        injury_items=[injury_item],
        team_forms=[team_form],
        match_analyses=[analysis],
        generated_markdown="# Test Report",
    )

    dumped = report_data.model_dump(mode="json")
    dumped_json = report_data.model_dump_json()

    assert dumped["timezone"] == "Asia/Tokyo"
    assert dumped["matches"][0]["kickoff_at"] == "2026-06-07T19:30:00Z"
    assert dumped["match_analyses"][0]["attention_level"] == "S"
    assert dumped["match_analyses"][0]["importance_score"] == 88
    assert "\"language\":\"zh-CN\"" in dumped_json


def test_timezone_aware_datetime_is_required() -> None:
    naive_time = datetime(2026, 6, 7, 19, 30)

    with pytest.raises(ValueError):
        Match(
            id="match-002",
            competition="FIFA World Cup 2026",
            stage="Group Stage",
            kickoff_at=naive_time,
            home_team=Team(id="can", name="Canada"),
            away_team=Team(id="mex", name="Mexico"),
        )
