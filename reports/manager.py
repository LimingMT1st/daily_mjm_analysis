from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from models import DailyReportData
from storage.sqlite_store import ReportChanges

from .html_report import HTMLReportRenderer
from .markdown_report import MarkdownReportRenderer

TEAM_NAME_MAP = {
    "Japan": "日本",
    "United States": "美国",
    "USA": "美国",
    "Mexico": "墨西哥",
    "Canada": "加拿大",
    "England": "英格兰",
    "Brazil": "巴西",
    "France": "法国",
    "Argentina": "阿根廷",
    "Germany": "德国",
    "Iran": "伊朗",
    "Scotland": "苏格兰",
    "DR Congo": "刚果（金）",
    "Messi": "梅西",
}
CITY_NAME_MAP = {
    "Tokyo": "东京",
    "Yokohama": "横滨",
    "Saitama": "埼玉",
    "Nagoya": "名古屋",
}
STAGE_NAME_MAP = {
    "Group Stage": "小组赛",
    "Quarter-final": "四分之一决赛",
    "Quarterfinal": "四分之一决赛",
    "Semi-final": "半决赛",
    "Semifinal": "半决赛",
    "Final": "决赛",
}


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
                    "stage": self._translate_stage(match.stage),
                    "city": match.city,
                    "city_display": CITY_NAME_MAP.get(match.city or "", match.city or "待定"),
                    "venue": match.venue,
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "home_name": self._translate_name(match.home_team.name),
                    "away_name": self._translate_name(match.away_team.name),
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
                    "label": self._match_label(match.home_team.name, match.away_team.name),
                    "analysis": analysis,
                    "explanation_localized": self._localize_text(analysis.explanation),
                    "form_summary_localized": self._localize_text(analysis.form_summary),
                    "upset_risk_label": self._risk_label(analysis.upset_risk),
                    "confidence": self._analysis_confidence(analysis, report_data),
                    "confidence_label": self._confidence_label(
                        self._analysis_confidence(analysis, report_data)
                    ),
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
                    "label": self._match_label(match.home_team.name, match.away_team.name),
                    "analysis": analysis,
                    "upset_risk_label": self._risk_label(analysis.upset_risk),
                    "confidence": self._analysis_confidence(analysis, report_data),
                    "confidence_label": self._confidence_label(
                        self._analysis_confidence(analysis, report_data)
                    ),
                }
            )

        news_items = [
            {
                "title": item.title,
                "summary_cn": self._summarize_news_item(item),
                "source": item.source,
                "url": item.url,
                "published_local": item.published_at.astimezone(timezone).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "credibility": self._news_credibility(item.source),
                "credibility_label": self._confidence_label(
                    self._news_credibility(item.source)
                ),
            }
            for item in report_data.news_items[:10]
        ]

        focus_team_dynamics = self._build_focus_team_dynamics(report_data, match_map)
        ai_summary_lines = self._normalize_ai_summary(ai_summary)
        briefing_highlights = self._build_briefing_highlights(
            top_matches=top_matches,
            today_matches=today_matches,
            tomorrow_matches=tomorrow_matches,
            changes=changes,
            news_items=news_items,
        )

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
            "ai_summary_lines": ai_summary_lines,
            "briefing_highlights": briefing_highlights,
            "data_sources": data_sources,
            "changes": changes.to_dict(),
        }

    def _build_briefing_highlights(
        self,
        top_matches: list[dict],
        today_matches: list[dict],
        tomorrow_matches: list[dict],
        changes: ReportChanges,
        news_items: list[dict],
    ) -> list[str]:
        lines: list[str] = []
        if top_matches:
            top_item = top_matches[0]
            lines.append(
                f"头号关注比赛是 {top_item['label']}，关注等级 {top_item['analysis'].attention_level}，"
                f"重要性 {top_item['analysis'].importance_score}。"
            )
        elif today_matches or tomorrow_matches:
            lines.append("当前暂无高优先级前瞻，但赛程窗口内仍有可跟踪比赛。")
        else:
            lines.append("当前赛程窗口内暂无比赛，简报重心转向球队动态与舆情。")

        if news_items:
            lines.append(
                f"近 48 小时共纳入 {len(news_items)} 条重点新闻，最新动态来自 {news_items[0]['source']}。"
            )
        else:
            lines.append("近 48 小时暂无进入简报的重点新闻。")

        lines.append(f"与昨日相比，新增新闻 {changes.new_news_count} 条。")

        if changes.match_status_changes:
            lines.append(f"比赛状态出现 {len(changes.match_status_changes)} 项变化。")
        else:
            lines.append("比赛状态暂无明显变化。")
        return lines

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

    def _confidence_label(self, value: str) -> str:
        return {"high": "高", "medium": "中", "low": "低"}.get(value, "中")

    def _risk_label(self, value: str) -> str:
        return {"high": "高", "medium": "中", "low": "低"}.get(value, value)

    def _translate_name(self, value: str) -> str:
        return TEAM_NAME_MAP.get(value, value)

    def _match_label(self, home_name: str, away_name: str) -> str:
        return f"{self._translate_name(home_name)} 对 {self._translate_name(away_name)}"

    def _translate_stage(self, value: str) -> str:
        return STAGE_NAME_MAP.get(value, value)

    def _normalize_ai_summary(self, ai_summary: str) -> list[str]:
        lines: list[str] = []
        for raw_line in ai_summary.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line == "## 说明":
                continue
            if "当前未配置 `LLM_API_KEY`" in line:
                continue
            if "不提供任何赌博建议" in line:
                continue
            if line.startswith("- "):
                line = line[2:]
            lines.append(self._localize_text(line))
        return lines[:6]

    def _localize_text(self, value: str) -> str:
        localized = value.replace(" vs ", " 对 ")
        for english, chinese in TEAM_NAME_MAP.items():
            localized = localized.replace(english, chinese)
        localized = (
            localized.replace(" high", " 高")
            .replace(" medium", " 中")
            .replace(" low", " 低")
            .replace("为 high", "为高")
            .replace("为 medium", "为中")
            .replace("为 low", "为低")
        )
        return localized

    def _summarize_news_item(self, item) -> str:
        text = f"{item.title} {item.summary}"
        lowered = text.casefold()
        related_names = [
            cn_name
            for en_name, cn_name in TEAM_NAME_MAP.items()
            if en_name.casefold() in lowered
        ]
        prefix = f"{'、'.join(dict.fromkeys(related_names))}相关动态，" if related_names else ""

        if any(word in lowered for word in ["injured", "injury", "omission", "replaces", "replace"]):
            core = "阵容与人员变动值得关注"
        elif any(word in lowered for word in ["captain", "vice-captain"]):
            core = "队内角色分工出现新信号"
        elif "friendly" in lowered:
            core = "热身赛安排与备战节奏出现变化"
        elif any(word in lowered for word in ["visa", "lands", "travel"]):
            core = "行程与场外因素进入观察范围"
        elif "world cup" in lowered:
            core = "世界杯相关话题热度持续上升"
        else:
            core = "主流媒体出现新的外围动态"
        return f"{prefix}{core}，原文标题《{item.title}》。"

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
                    f"爆冷风险 {self._risk_label(top_analysis.upset_risk)}。"
                )
                confidence = self._analysis_confidence(top_analysis, report_data)
            elif related_news:
                summary = f"近48小时相关新闻 {len(related_news)} 条，最新标题《{related_news[0].title}》。"
                confidence = self._news_credibility(related_news[0].source)
            elif related_matches:
                next_match = related_matches[0]
                summary = (
                    f"已出现在赛程中，最近一场为 "
                    f"{self._match_label(next_match.home_team.name, next_match.away_team.name)}。"
                )
                confidence = "high"
            else:
                summary = "暂无新增赛程或高价值情报。"
                confidence = "low"

            items.append(
                {
                    "team_name": self._translate_name(team_name),
                    "summary": summary,
                    "confidence": confidence,
                    "confidence_label": self._confidence_label(confidence),
                }
            )
        return items
