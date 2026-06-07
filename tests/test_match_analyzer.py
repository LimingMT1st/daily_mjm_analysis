from __future__ import annotations

from datetime import UTC, datetime

from analyzers.match_analyzer import MatchAnalyzer
from models import Match, MatchResult, NewsItem, Standing, Team, TeamForm


def test_match_analyzer_boosts_focus_knockout_and_host_matches() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    match = Match(
        id="match-100",
        competition="FIFA World Cup 2026",
        stage="Quarter-final",
        kickoff_at=now,
        home_team=Team(id="usa", name="United States", ranking=12),
        away_team=Team(id="jpn", name="Japan", ranking=18),
        result=MatchResult(status="scheduled"),
    )
    standings = [
        Standing(
            team=Team(id="usa", name="United States", ranking=12),
            stage="Quarter-final",
            position=1,
            played=4,
            won=3,
            drawn=1,
            lost=0,
            goals_for=7,
            goals_against=2,
            goal_difference=5,
            points=10,
            updated_at=now,
        ),
        Standing(
            team=Team(id="jpn", name="Japan", ranking=18),
            stage="Quarter-final",
            position=2,
            played=4,
            won=3,
            drawn=0,
            lost=1,
            goals_for=6,
            goals_against=4,
            goal_difference=2,
            points=9,
            updated_at=now,
        ),
    ]
    news_items = [
        NewsItem(
            id="news-1",
            team_id="usa",
            title="World Cup focus grows around United States quarter-final",
            summary="FIFA spotlight is intensifying before kickoff.",
            source="Mock A",
            url="https://example.com/1",
            published_at=now,
        ),
        NewsItem(
            id="news-2",
            team_id="jpn",
            title="Japan confident before knockout clash",
            summary="World Cup pressure remains high.",
            source="Mock B",
            url="https://example.com/2",
            published_at=now,
        ),
    ]
    team_forms = [
        TeamForm(
            team_id="usa",
            recent_results=["W", "D", "W", "W", "L"],
            unbeaten_streak=3,
            wins_in_last_five=3,
            goals_scored_last_five=8,
            goals_conceded_last_five=4,
            updated_at=now,
        ),
        TeamForm(
            team_id="jpn",
            recent_results=["W", "W", "W", "D", "W"],
            unbeaten_streak=5,
            wins_in_last_five=4,
            goals_scored_last_five=10,
            goals_conceded_last_five=3,
            updated_at=now,
        ),
    ]

    analysis = MatchAnalyzer().analyze_match(
        match=match,
        standings=standings,
        news_items=news_items,
        team_forms=team_forms,
        focus_teams=["United States", "Japan"],
    )

    assert analysis.importance_score >= 80
    assert analysis.attention_level in {"S", "A"}
    assert analysis.qualification_impact >= 90
    assert analysis.news_heat > 0
    assert "重点关注球队" in analysis.explanation
    assert "淘汰赛" in analysis.explanation


def test_match_analyzer_raises_upset_risk_for_weaker_team_with_hot_news() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    match = Match(
        id="match-200",
        competition="FIFA World Cup 2026",
        stage="Group Stage",
        kickoff_at=now,
        home_team=Team(id="ger", name="Germany", ranking=4),
        away_team=Team(id="can", name="Canada", ranking=30),
        result=MatchResult(status="scheduled"),
    )
    standings = [
        Standing(
            team=Team(id="ger", name="Germany", ranking=4),
            stage="Group Stage",
            position=1,
            played=2,
            won=2,
            drawn=0,
            lost=0,
            goals_for=5,
            goals_against=1,
            goal_difference=4,
            points=6,
            updated_at=now,
        ),
        Standing(
            team=Team(id="can", name="Canada", ranking=30),
            stage="Group Stage",
            position=3,
            played=2,
            won=1,
            drawn=0,
            lost=1,
            goals_for=2,
            goals_against=3,
            goal_difference=-1,
            points=3,
            updated_at=now,
        ),
    ]
    news_items = [
        NewsItem(
            id="news-3",
            team_id="can",
            title="Canada World Cup surge gains attention",
            summary="FIFA coverage highlights Canada's aggressive style.",
            source="Mock A",
            url="https://example.com/3",
            published_at=now,
        ),
        NewsItem(
            id="news-4",
            team_id="can",
            title="Canada camp believes upset is possible",
            summary="World Cup confidence is rising in the underdog camp.",
            source="Mock B",
            url="https://example.com/4",
            published_at=now,
        ),
    ]

    analysis = MatchAnalyzer().analyze_match(
        match=match,
        standings=standings,
        news_items=news_items,
        team_forms=[],
        focus_teams=["Canada"],
    )

    assert analysis.upset_risk == "high"
    assert analysis.news_heat >= 40
    assert "爆冷风险判断为 high" in analysis.explanation
