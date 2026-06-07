from __future__ import annotations

import json
import os
from urllib import error, request

from models import DailyReportData


DEFAULT_LLM_MODEL = "gpt-4o-mini"


class LLMAnalyzer:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY", "")
        self.base_url = (
            base_url if base_url is not None else os.getenv("LLM_BASE_URL", "")
        )
        self.model = (
            model if model is not None else os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
        )

    def analyze(self, report_data: DailyReportData) -> str:
        if not self.api_key:
            return self._build_local_summary(report_data)

        try:
            return self._call_llm(report_data)
        except (
            OSError,
            ValueError,
            error.URLError,
            error.HTTPError,
            KeyError,
            IndexError,
        ):
            return self._build_local_summary(report_data)

    def _call_llm(self, report_data: DailyReportData) -> str:
        endpoint = self._resolve_chat_completions_url()
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是面向体育内容运营团队的世界杯情报简报助手。"
                        "输出必须像内部情报简报，不要写成普通新闻摘要。"
                        "只能基于输入事实作答，不编造信息。"
                        "每条判断都要显式标记为【事实】、【数据推断】或【AI判断】。"
                        "每条判断都尽量补充【可信度: high|medium|low】。"
                        "重要结论必须尽量引用来源标题、比赛字段、积分或评分字段。"
                        "严禁给出赌博建议、投注建议、盘口建议。"
                        "中文表达要简洁、专业，适合直接发给体育内容运营人员。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(report_data),
                },
            ],
            "temperature": 0.2,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = request.Request(endpoint, data=body, headers=headers, method="POST")

        with request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode("utf-8")

        data = json.loads(response_body)
        return data["choices"][0]["message"]["content"].strip()

    def _resolve_chat_completions_url(self) -> str:
        if not self.base_url:
            raise ValueError("LLM_BASE_URL is required when LLM_API_KEY is configured")
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return self.base_url.rstrip("/") + "/chat/completions"

    def _build_prompt(self, report_data: DailyReportData) -> str:
        payload = report_data.model_dump(mode="json")
        return (
            "请基于以下结构化世界杯日报数据生成一份中文 Markdown 情报简报。\n"
            "要求：\n"
            "1. 不编造信息。\n"
            "2. 每条判断必须带标签：【事实】、【数据推断】或【AI判断】。\n"
            "3. 每条判断尽量带【可信度: high|medium|low】。\n"
            "4. 输出要像情报简报，不要写成普通新闻摘要。\n"
            "5. 必须包含以下栏目：\n"
            "   - 今日最值得关注的3场比赛\n"
            "   - 爆冷风险榜\n"
            "   - 重点球队动态\n"
            "   - 今日/明日赛程摘要\n"
            "   - 数据分析\n"
            "   - AI总结\n"
            "6. 重要结论尽量引用来源标题、比赛字段、积分榜字段或评分字段。\n"
            "7. 禁止输出任何赌博建议、投注建议。\n"
            "8. 语言风格适合体育内容运营人员直接转发或二次编辑。\n\n"
            "结构化数据如下：\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _build_local_summary(self, report_data: DailyReportData) -> str:
        match_map = {match.id: match for match in report_data.matches}
        sorted_analyses = sorted(
            report_data.match_analyses,
            key=lambda item: (item.importance_score, item.news_heat),
            reverse=True,
        )
        upset_rank = sorted(
            report_data.match_analyses,
            key=lambda item: (
                {"high": 3, "medium": 2, "low": 1}.get(item.upset_risk, 0),
                item.news_heat,
                item.importance_score,
            ),
            reverse=True,
        )

        lines = [
            "# 每日美加墨世界杯情报简报",
            "",
            "## 说明",
            "- 当前未配置 `LLM_API_KEY`，以下内容为本地规则情报摘要。",
            "- 所有结论按【事实】、【数据推断】、【AI判断】标记，未提供的数据不会被补写。",
            "- 本简报不提供任何赌博建议或投注建议。",
            "",
            "## 今日最值得关注的3场比赛",
        ]

        if not sorted_analyses:
            lines.append("- 【事实】【可信度: high】当前没有可分析比赛。")
        else:
            for analysis in sorted_analyses[:3]:
                match = match_map.get(analysis.match_id)
                if match is None:
                    continue
                lines.append(
                    "- 【数据推断】【可信度: high】"
                    f"{match.home_team.name} vs {match.away_team.name}"
                    f" | 关注等级 {analysis.attention_level}"
                    f" | 重要性 {analysis.importance_score}"
                    f" | 爆冷风险 {analysis.upset_risk}"
                    f" | 出线影响 {analysis.qualification_impact}"
                )
                lines.append(f"  - 【AI判断】【可信度: medium】{analysis.explanation}")

        lines.extend(["", "## 爆冷风险榜"])

        if not upset_rank:
            lines.append("- 【事实】【可信度: high】暂无爆冷风险样本。")
        else:
            for analysis in upset_rank[:5]:
                match = match_map.get(analysis.match_id)
                if match is None:
                    continue
                lines.append(
                    "- 【数据推断】【可信度: medium】"
                    f"{match.home_team.name} vs {match.away_team.name}"
                    f" | 风险 {analysis.upset_risk}"
                    f" | 新闻热度 {analysis.news_heat}"
                    f" | 重要性 {analysis.importance_score}"
                )

        lines.extend(["", "## 重点球队动态"])

        focus_names = {team.name for team in report_data.focus_teams}
        if not focus_names:
            lines.append("- 【事实】【可信度: high】当前未设置重点球队。")
        else:
            for team_name in sorted(focus_names):
                related_news = [
                    item for item in report_data.news_items if (item.team_id and item.team_id.casefold() in team_name.casefold()) or team_name.casefold() in f"{item.title} {item.summary}".casefold()
                ]
                related_matches = [
                    match for match in report_data.matches if match.home_team.name == team_name or match.away_team.name == team_name
                ]
                if related_news:
                    lines.append(
                        f"- 【事实】【可信度: medium】{team_name} 相关新闻 {len(related_news)} 条，最新标题：《{related_news[0].title}》。"
                    )
                elif related_matches:
                    next_match = related_matches[0]
                    lines.append(
                        f"- 【事实】【可信度: high】{team_name} 已进入今日/明日赛程，最近一场为 {next_match.home_team.name} vs {next_match.away_team.name}。"
                    )
                else:
                    lines.append(
                        f"- 【事实】【可信度: low】{team_name} 暂无新增赛程或重点新闻。"
                    )

        lines.extend(["", "## 今日/明日赛程摘要"])

        if report_data.matches:
            for match in report_data.matches[:5]:
                lines.append(
                    "- 【事实】【可信度: high】"
                    f"比赛字段 `{match.id}`：{match.home_team.name} vs {match.away_team.name}，"
                    f"开球时间 {match.kickoff_at.isoformat()}，阶段 {match.stage}。"
                )
        else:
            lines.append("- 【事实】【可信度: high】当前没有比赛数据。")

        lines.extend(["", "## 新闻情报"])
        if report_data.news_items:
            for item in report_data.news_items[:5]:
                lines.append(
                    "- 【事实】【可信度: medium】"
                    f"新闻标题：《{item.title}》；来源 {item.source}；发布时间 {item.published_at.isoformat()}。"
                )
        else:
            lines.append("- 【事实】【可信度: high】当前没有近 48 小时新闻数据。")

        lines.extend(["", "## 数据分析"])
        has_inference = False
        if report_data.match_analyses:
            for analysis in report_data.match_analyses[:5]:
                match = match_map.get(analysis.match_id)
                label = (
                    analysis.match_id
                    if match is None
                    else f"{match.home_team.name} vs {match.away_team.name}"
                )
                lines.append(
                    "- 【数据推断】【可信度: high】"
                    f"{label}：出线影响 {analysis.qualification_impact}，新闻热度 {analysis.news_heat}，关注等级 {analysis.attention_level}。"
                )
                if analysis.upset_risk != "low":
                    has_inference = True
                    lines.append(
                        "- 【AI判断】【可信度: medium】"
                        f"基于规则评分，比赛 `{analysis.match_id}` 的爆冷风险为 {analysis.upset_risk}，"
                        "这表示关注异常赛果可能性，不代表任何投注建议。"
                    )
        if not report_data.match_analyses:
            lines.append("- 【数据推断】【可信度: low】暂无可分析比赛。")
        elif not has_inference:
            lines.append("- 【AI判断】【可信度: medium】暂无高风险爆冷样本。")

        lines.extend(["", "## AI总结"])
        if report_data.match_analyses:
            for analysis in report_data.match_analyses[:5]:
                match = match_map.get(analysis.match_id)
                label = (
                    analysis.match_id
                    if match is None
                    else f"{match.home_team.name} vs {match.away_team.name}"
                )
                lines.append(f"- 【AI判断】【可信度: medium】{label}：{analysis.explanation}")
        else:
            lines.append("- 【AI判断】【可信度: low】建议先补充比赛、积分榜和新闻数据后再生成完整简报。")

        return "\n".join(lines)
