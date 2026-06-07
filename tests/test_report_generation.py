from __future__ import annotations

from datetime import UTC, datetime

from models import DailyReportData, Match, MatchAnalysis, MatchResult, NewsItem, Team
from reports.manager import ReportManager


def test_report_manager_generates_markdown_and_html_files(tmp_path) -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    match = Match(
        id="fixture-001",
        competition="FIFA World Cup 2026",
        stage="Group Stage",
        city="Tokyo",
        kickoff_at=now,
        home_team=Team(id="jpn", name="Japan"),
        away_team=Team(id="usa", name="United States"),
        result=MatchResult(status="scheduled"),
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
    report_data = DailyReportData(
        report_date=now,
        timezone="Asia/Tokyo",
        language="zh-CN",
        focus_teams=[Team(id="jpn", name="Japan")],
        matches=[match],
        standings=[],
        news_items=[
            NewsItem(
                id="news-001",
                team_id="jpn",
                title="World Cup preview: Japan ready",
                summary="Japan enter the FIFA event with stable preparation.",
                source="Mock Feed",
                url="https://example.com/news-1",
                published_at=now,
            )
        ],
        injury_items=[],
        team_forms=[],
        match_analyses=[analysis],
    )

    manager = ReportManager(output_dir=tmp_path)
    artifacts = manager.generate_daily_report(
        report_data=report_data,
        ai_summary="# AI 总结\n\n这里是测试摘要。",
    )

    assert artifacts.markdown_path.exists()
    assert artifacts.html_path.exists()
    assert "今日最值得关注的 3 场比赛" in artifacts.markdown_content
    assert "爆冷风险榜" in artifacts.markdown_content
    assert "重点球队动态" in artifacts.markdown_content
    assert "可信度" in artifacts.markdown_content
    assert "AI 总结" in artifacts.markdown_content
    assert "<html" in artifacts.html_content.lower()
    assert "Japan vs United States" in artifacts.html_content
