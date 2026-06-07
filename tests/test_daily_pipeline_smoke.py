from __future__ import annotations

from types import SimpleNamespace

from main import run_daily_pipeline
from reports.manager import ReportManager
from storage import SQLiteStore
from tests.test_llm_analyzer import build_report_data


def test_daily_pipeline_smoke(tmp_path) -> None:
    report_data = build_report_data()
    match = report_data.matches[0]
    news_item = report_data.news_items[0]

    collectors = SimpleNamespace(
        collect_fixtures=lambda window, run_date=None: [match],
        collect_news=lambda now=None: [news_item],
    )
    analyzers = SimpleNamespace(
        match_analyzer=SimpleNamespace(
            analyze_match=lambda match, standings, news_items, team_forms, focus_teams: report_data.match_analyses[0]
        )
    )

    class StubNotifierManager:
        def send(
            self,
            title: str,
            content: str,
            html: str | None = None,
            dry_run: bool = False,
        ) -> dict[str, bool]:
            return {"email": False, "telegram": False, "wecom": False}

    app_config = SimpleNamespace(
        timezone="Asia/Tokyo",
        language="zh-CN",
        focus_teams=["Japan", "United States"],
    )

    result = run_daily_pipeline(
        collectors=collectors,
        analyzers=analyzers,
        report_manager=ReportManager(output_dir=tmp_path),
        notifier_manager=StubNotifierManager(),
        store=SQLiteStore(tmp_path / "cache.db"),
        app_config=app_config,
        run_date="2026-06-07",
        send_report_enabled=True,
        dry_run=True,
    )

    assert result.artifacts.markdown_path.exists()
    assert result.artifacts.html_path.exists()
    assert "每日美加墨世界杯情报日报" in result.artifacts.markdown_content
    assert result.send_results == {"email": False, "telegram": False, "wecom": False}
