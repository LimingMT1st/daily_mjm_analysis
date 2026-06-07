from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from pprint import pformat
from typing import Any
from zoneinfo import ZoneInfo

from analyzers import AnalyzerManager, LLMAnalyzer
from collectors import CollectorManager
from config import load_config
from models import DailyReportData, MatchAnalysis, Team
from notifiers import NotifierManager
from reports import ReportManager
from reports.manager import ReportArtifacts
from storage import SQLiteStore


LOGGER = logging.getLogger("daily_mjm_analysis")


@dataclass(slots=True)
class DailyPipelineResult:
    report_data: DailyReportData
    ai_summary: str
    artifacts: ReportArtifacts
    send_results: dict[str, bool]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Daily MJM World Cup intelligence analysis service."
    )
    parser.add_argument(
        "--mode",
        default="daily",
        choices=["pipeline", "fixtures", "news", "analyze", "report", "send", "daily"],
        help="Execution mode. Use daily for the end-to-end report pipeline.",
    )
    parser.add_argument(
        "--run-date",
        default=None,
        help="Run date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--window",
        default="today",
        choices=["today", "tomorrow", "next_3_days"],
        help="Fixture date window used in fixtures mode.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Reserved for future custom output overrides.",
    )
    parser.add_argument(
        "--skip-notify",
        action="store_true",
        help="Legacy flag for the old pipeline mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without external side effects such as sending notifications.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send the generated report in daily mode.",
    )
    return parser


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    app_config = load_config()

    print("Current configuration summary:")
    print(pformat(app_config.summary(), sort_dicts=False))

    collectors = CollectorManager(timezone=app_config.timezone)
    analyzers = AnalyzerManager()
    reports = ReportManager()
    notifiers = NotifierManager()
    store = SQLiteStore()

    if args.mode == "fixtures":
        print_fixture_lists(
            collectors=collectors,
            run_date=args.run_date,
            requested_window=args.window,
        )
        return 0
    if args.mode == "news":
        print_news_list(collectors=collectors)
        return 0
    if args.mode == "analyze":
        report_data = build_report_data(
            collectors=collectors,
            analyzers=analyzers,
            app_config=app_config,
            run_date=args.run_date,
        )
        print_analysis_markdown(report_data)
        return 0
    if args.mode == "report":
        report_data = build_report_data(
            collectors=collectors,
            analyzers=analyzers,
            app_config=app_config,
            run_date=args.run_date,
        )
        generate_local_report(report_manager=reports, report_data=report_data)
        return 0
    if args.mode == "send":
        report_data = build_report_data(
            collectors=collectors,
            analyzers=analyzers,
            app_config=app_config,
            run_date=args.run_date,
        )
        send_report(
            report_manager=reports,
            notifier_manager=notifiers,
            report_data=report_data,
            dry_run=args.dry_run,
        )
        return 0
    if args.mode == "daily":
        result = run_daily_pipeline(
            collectors=collectors,
            analyzers=analyzers,
            report_manager=reports,
            notifier_manager=notifiers,
            store=store,
            app_config=app_config,
            run_date=args.run_date,
            send_report_enabled=args.send,
            dry_run=args.dry_run,
        )
        print()
        print(f"Markdown report: {result.artifacts.markdown_path}")
        print(f"HTML report: {result.artifacts.html_path}")
        print(f"Send results: {result.send_results}")
        return 0

    collected = collectors.collect(run_date=args.run_date)
    analyzed = analyzers.analyze(collected)
    if not args.skip_notify:
        notifiers.notify({"analyzed": analyzed}, dry_run=args.dry_run)
    print("Legacy pipeline completed.")
    return 0


def print_fixture_lists(
    collectors: CollectorManager, run_date: str | None, requested_window: str
) -> None:
    today_matches = collectors.collect_fixtures(window="today", run_date=run_date)
    tomorrow_matches = collectors.collect_fixtures(window="tomorrow", run_date=run_date)

    print()
    print("Today's matches:")
    print(format_match_list(today_matches))
    print()
    print("Tomorrow's matches:")
    print(format_match_list(tomorrow_matches))

    if requested_window == "next_3_days":
        next_three_day_matches = collectors.collect_fixtures(
            window="next_3_days", run_date=run_date
        )
        print()
        print("Next 3 days matches:")
        print(format_match_list(next_three_day_matches))


def format_match_list(matches: list) -> str:
    if not matches:
        return "  No matches found."

    lines = []
    for match in matches:
        kickoff = match.kickoff_at.strftime("%Y-%m-%d %H:%M %z")
        lines.append(
            "  "
            f"{kickoff} | {match.home_team.name} vs {match.away_team.name} | "
            f"{match.stage} | {match.city or 'Unknown city'}"
        )
    return "\n".join(lines)


def print_news_list(collectors: CollectorManager) -> None:
    news_items = collectors.collect_news()
    print()
    print("Recent news:")
    if not news_items:
        print("  No news found.")
        return

    for item in news_items:
        published = item.published_at.strftime("%Y-%m-%d %H:%M %z")
        print(f"  {item.title}")
        print(f"    Source: {item.source}")
        print(f"    Published: {published}")
        print(f"    Link: {item.url}")


def build_report_data(
    collectors: CollectorManager,
    analyzers: AnalyzerManager,
    app_config: Any,
    run_date: str | None,
) -> DailyReportData:
    timezone = ZoneInfo(app_config.timezone)
    report_date = (
        datetime.strptime(run_date, "%Y-%m-%d").replace(tzinfo=timezone)
        if run_date
        else datetime.now(timezone)
    )
    matches = collectors.collect_fixtures(window="next_3_days", run_date=run_date)
    standings = collectors.collect_standings()
    news_items = collectors.collect_news(now=report_date)
    match_analyses = []
    for match in matches:
        analysis = analyzers.match_analyzer.analyze_match(
            match=match,
            standings=standings,
            news_items=news_items,
            team_forms=[],
            focus_teams=app_config.focus_teams,
        )
        match_analyses.append(analysis)

    return DailyReportData(
        report_date=report_date,
        timezone=app_config.timezone,
        language=app_config.language,
        focus_teams=[
            Team(id=name.casefold().replace(" ", "-"), name=name)
            for name in app_config.focus_teams
        ],
        matches=matches,
        standings=standings,
        news_items=news_items,
        injury_items=[],
        team_forms=[],
        match_analyses=match_analyses,
    )


def print_analysis_markdown(report_data: DailyReportData) -> None:
    markdown = LLMAnalyzer().analyze(report_data)
    print()
    print(markdown)


def generate_local_report(
    report_manager: ReportManager,
    report_data: DailyReportData,
) -> None:
    ai_summary = LLMAnalyzer().analyze(report_data)
    artifacts = report_manager.generate_daily_report(
        report_data=report_data,
        ai_summary=ai_summary,
    )
    print()
    print(f"Markdown report: {artifacts.markdown_path}")
    print(f"HTML report: {artifacts.html_path}")


def send_report(
    report_manager: ReportManager,
    notifier_manager: NotifierManager,
    report_data: DailyReportData,
    dry_run: bool = False,
) -> None:
    ai_summary = LLMAnalyzer().analyze(report_data)
    artifacts = report_manager.generate_daily_report(
        report_data=report_data,
        ai_summary=ai_summary,
    )
    results = notifier_manager.send(
        title="每日美加墨世界杯情报日报",
        content=artifacts.markdown_content,
        html=artifacts.html_content,
        dry_run=dry_run,
    )
    print()
    print(f"Markdown report: {artifacts.markdown_path}")
    print(f"HTML report: {artifacts.html_path}")
    print(f"Send results: {results}")


def run_daily_pipeline(
    collectors: Any,
    analyzers: Any,
    report_manager: ReportManager,
    notifier_manager: Any,
    store: SQLiteStore,
    app_config: Any,
    run_date: str | None,
    send_report_enabled: bool = False,
    dry_run: bool = False,
) -> DailyPipelineResult:
    LOGGER.info("Step 1/7: reading configuration")
    timezone = ZoneInfo(app_config.timezone)
    report_date = (
        datetime.strptime(run_date, "%Y-%m-%d").replace(tzinfo=timezone)
        if run_date
        else datetime.now(timezone)
    )

    LOGGER.info("Step 2/7: loading today's and tomorrow's fixtures")
    try:
        today_matches = collectors.collect_fixtures(window="today", run_date=run_date)
        tomorrow_matches = collectors.collect_fixtures(
            window="tomorrow", run_date=run_date
        )
        seen_ids = {match.id for match in today_matches}
        matches = today_matches + [
            match for match in tomorrow_matches if match.id not in seen_ids
        ]
    except Exception as exc:
        LOGGER.warning("Fixtures source failed, continuing with empty fixtures: %s", exc)
        matches = []

    LOGGER.info("Step 3/7: loading standings and related news")
    try:
        standings = collectors.collect_standings()
    except Exception as exc:
        LOGGER.warning("Standings source failed, continuing with empty standings: %s", exc)
        standings = []
    try:
        news_items = collectors.collect_news(now=report_date)
    except Exception as exc:
        LOGGER.warning("News source failed, continuing with empty news: %s", exc)
        news_items = []

    LOGGER.info("Step 4/7: running match analysis")
    match_analyses: list[MatchAnalysis] = []
    for match in matches:
        try:
            analysis = analyzers.match_analyzer.analyze_match(
                match=match,
                standings=standings,
                news_items=news_items,
                team_forms=[],
                focus_teams=app_config.focus_teams,
            )
            match_analyses.append(analysis)
        except Exception as exc:
            LOGGER.warning(
                "Match analysis failed for %s, continuing: %s",
                match.id,
                exc,
            )

    report_data = DailyReportData(
        report_date=report_date,
        timezone=app_config.timezone,
        language=app_config.language,
        focus_teams=[
            Team(id=name.casefold().replace(" ", "-"), name=name)
            for name in app_config.focus_teams
        ],
        matches=matches,
        standings=standings,
        news_items=news_items,
        injury_items=[],
        team_forms=[],
        match_analyses=match_analyses,
    )

    LOGGER.info("Step 5/7: generating AI summary")
    ai_summary = LLMAnalyzer().analyze(report_data)

    LOGGER.info("Step 6/7: generating Markdown and HTML reports")
    previous_run = store.load_previous_run(report_date.date())
    changes = store.compute_changes(report_data=report_data, previous_run=previous_run)
    artifacts = report_manager.generate_daily_report(
        report_data=report_data,
        ai_summary=ai_summary,
        changes=changes,
    )

    LOGGER.info("Step 7/7: sending report")
    send_results = {"email": False, "telegram": False, "wecom": False}
    if send_report_enabled:
        try:
            send_results = notifier_manager.send(
                title="每日美加墨世界杯情报日报",
                content=artifacts.markdown_content,
                html=artifacts.html_content,
                dry_run=dry_run,
            )
        except Exception as exc:
            LOGGER.warning("Sending failed, continuing after report generation: %s", exc)
    else:
        LOGGER.info("Send flag not enabled; skipping push step")

    LOGGER.info("Archiving daily run to SQLite")
    try:
        store.save_matches(report_data.matches)
        store.save_news_items(report_data.news_items)
        store.save_analyses(report_data.report_date.date(), report_data.match_analyses)
        store.save_report_run(
            report_data=report_data,
            artifacts=artifacts,
            ai_summary=ai_summary,
            send_results=send_results,
            changes=changes,
        )
    except Exception as exc:
        LOGGER.warning("Archiving failed, continuing after report generation: %s", exc)

    return DailyPipelineResult(
        report_data=report_data,
        ai_summary=ai_summary,
        artifacts=artifacts,
        send_results=send_results,
    )


if __name__ == "__main__":
    raise SystemExit(main())
