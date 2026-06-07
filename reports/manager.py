from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from models import DailyReportData
from storage.sqlite_store import ReportChanges

from .html_report import HTMLReportRenderer
from .markdown_report import MarkdownReportRenderer


@dataclass(slots=True)
class ReportArtifacts:
    markdown_path: Path
    html_path: Path
    markdown_content: str
    html_content: str


class ReportManager:
    def __init__(
        self,
        output_dir: str | Path = "reports/output",
        templates_dir: str | Path | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.markdown_renderer = MarkdownReportRenderer(templates_dir=templates_dir)
        self.html_renderer = HTMLReportRenderer(templates_dir=templates_dir)

    def generate_daily_report(
        self,
        report_data: DailyReportData,
        ai_summary: str,
        changes: ReportChanges | None = None,
    ) -> ReportArtifacts:
        context = self._build_context(
            report_data=report_data,
            ai_summary=ai_summary,
            changes=changes or ReportChanges(0, [], []),
        )
        markdown_content = self.markdown_renderer.render(context)
        html_content = self.html_renderer.render(context)

        report_date = report_data.report_date.astimezone(
            ZoneInfo(report_data.timezone)
        ).date()
        filename = f"{report_date.isoformat()}-worldcup-report"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self.output_dir / f"{filename}.md"
        html_path = self.output_dir / f"{filename}.html"
        markdown_path.write_text(markdown_content, encoding="utf-8")
        html_path.write_text(html_content, encoding="utf-8")

        return ReportArtifacts(
            markdown_path=markdown_path,
            html_path=html_path,
            markdown_content=markdown_content,
            html_content=html_content,
        )

    def _build_context(
        self,
        report_data: DailyReportData,
        ai_summary: str,
        changes: ReportChanges,
    ) -> dict:
        timezone = ZoneInfo(report_data.timezone)
        report_day = report_data.report_date.astimezone(timezone).date()
        tomorrow = report_day.fromordinal(report_day.toordinal() + 1)
        match_map = {match.id: match for match in report_data.matches}

        decorated_matches = []
        for match in report_data.matches:
            local_kickoff = match.kickoff_at.astimezone(timezone)
            decorated_matches.append(
                {
                    "id": match.id,
                    "competition": match.competition,
                    "stage": match.stage,
                    "city": match.city,
                    "venue": match.venue,
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "kickoff_local": local_kickoff.strftime("%Y-%m-%d %H:%M"),
                    "date": local_kickoff.date(),
                }
            )

        today_matches = [item for item in decorated_matches if item["date"] == report_day]
        tomorrow_matches = [item for item in decorated_matches if item["date"] == tomorrow]

        sorted_analyses = sorted(
            report_data.match_analyses,
            key=lambda item: (item.importance_score, item.news_heat),
            reverse=True,
        )

        focus_matches = []
        for analysis in sorted_analyses[:5]:
            match = match_map.get(analysis.match_id)
            if match is None:
                continue
            focus_matches.append(
                {
                    "label": f"{match.home_team.name} vs {match.away_team.name}",
                    "analysis": analysis,
                    "confidence": self._analysis_confidence(analysis, report_data),
                }
            )

        top_matches = focus_matches[:3]

        upset_risk_board = []
        for analysis in sorted(
            report_data.match_analyses,
            key=lambda item: (
                {"high": 3, "medium": 2, "low": 1}.get(item.upset_risk, 0),
                item.news_heat,
                item.importance_score,
            ),
            reverse=True,
        )[:5]:
            match = match_map.get(analysis.match_id)
            if match is None:
                continue
            upset_risk_board.append(
                {
                    "label": f"{match.home_team.name} vs {match.away_team.name}",
                    "analysis": analysis,
                    "confidence": self._analysis_confidence(analysis, report_data),
                }
            )

        news_items = [
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_local": item.published_at.astimezone(timezone).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "credibility": self._news_credibility(item.source),
            }
            for item in report_data.news_items[:10]
        ]

        focus_team_dynamics = self._build_focus_team_dynamics(report_data, match_map)

        data_sources = [
            "赛程数据：config/fixtures.sample.json 本地样例",
            "新闻数据：config/sources.yaml 配置的 RSS 源",
            "规则分析：analyzers/match_analyzer.py",
            "AI 总结：analyzers/llm_analyzer.py",
        ]

        return {
            "title": "每日美加墨世界杯情报日报",
            "generated_at": report_data.report_date.astimezone(timezone).strftime(
                "%Y-%m-%d %H:%M %Z"
            ),
            "today_matches": today_matches,
            "tomorrow_matches": tomorrow_matches,
            "top_matches": top_matches,
            "focus_matches": focus_matches,
            "upset_risk_board": upset_risk_board,
            "focus_team_dynamics": focus_team_dynamics,
            "news_items": news_items,
            "ai_summary": ai_summary,
            "data_sources": data_sources,
            "changes": changes.to_dict(),
        }

    def _news_credibility(self, source: str) -> str:
        normalized = source.casefold()
        if any(keyword in normalized for keyword in ["fifa", "official", "api"]):
            return "high"
        if any(
            keyword in normalized
            for keyword in [
                "bbc",
                "reuters",
                "ap",
                "espn",
                "sky",
                "the athletic",
                "cnn",
            ]
        ):
            return "medium"
        return "low"

    def _analysis_confidence(
        self,
        analysis,
        report_data: DailyReportData,
    ) -> str:
        if report_data.standings:
            return "high"
        if analysis.news_heat > 0:
            return "medium"
        return "low"

    def _build_focus_team_dynamics(
        self,
        report_data: DailyReportData,
        match_map: dict,
    ) -> list[dict]:
        items: list[dict] = []
        focus_names = [team.name for team in report_data.focus_teams]
        for team_name in focus_names:
            related_news = [
                item
                for item in report_data.news_items
                if team_name.casefold() in f"{item.title} {item.summary}".casefold()
            ]
            related_matches = [
                match
                for match in report_data.matches
                if match.home_team.name == team_name or match.away_team.name == team_name
            ]
            related_analyses = [
                analysis
                for analysis in report_data.match_analyses
                if (
                    (match := match_map.get(analysis.match_id)) is not None
                    and (match.home_team.name == team_name or match.away_team.name == team_name)
                )
            ]

            if related_analyses:
                top_analysis = sorted(
                    related_analyses,
                    key=lambda item: (item.importance_score, item.news_heat),
                    reverse=True,
                )[0]
                summary = (
                    f"关联比赛关注等级 {top_analysis.attention_level}，"
                    f"新闻热度 {top_analysis.news_heat}，"
                    f"爆冷风险 {top_analysis.upset_risk}。"
                )
                confidence = self._analysis_confidence(top_analysis, report_data)
            elif related_news:
                summary = f"近48小时相关新闻 {len(related_news)} 条，最新标题《{related_news[0].title}》。"
                confidence = self._news_credibility(related_news[0].source)
            elif related_matches:
                next_match = related_matches[0]
                summary = f"已出现在赛程中，最近一场为 {next_match.home_team.name} vs {next_match.away_team.name}。"
                confidence = "high"
            else:
                summary = "暂无新增赛程或高价值情报。"
                confidence = "low"

            items.append(
                {
                    "team_name": team_name,
                    "summary": summary,
                    "confidence": confidence,
                }
            )
        return items
