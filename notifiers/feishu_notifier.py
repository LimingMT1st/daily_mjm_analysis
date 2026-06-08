from __future__ import annotations

import json
import os
from urllib import request


class FeishuNotifier:
    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = (
            webhook_url if webhook_url is not None else os.getenv("FEISHU_WEBHOOK_URL", "")
        )

    def send(self, title: str, content: str, html: str | None = None) -> bool:
        if not self.webhook_url:
            print("Warning: feishu notifier skipped because webhook is missing.")
            return False

        payload = self._build_card_payload(title=title, content=content)
        req = request.Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            response.read()
        return True

    def _build_card_payload(self, title: str, content: str) -> dict:
        sections = self._extract_sections(content)
        elements = [
            {
                "tag": "markdown",
                "content": (
                    "**📌 给运营的结论**\n"
                    + "\n".join(f"- {line}" for line in sections["运营速览"][:5])
                ),
            }
        ]

        for section_name in (
            "今日重点",
            "今日关键信号",
            "赛程速览",
            "爆冷风险",
            "重点球队",
            "新闻解读",
            "AI建议",
            "关键信息变化",
        ):
            lines = sections.get(section_name, [])
            if not lines:
                continue
            section_title = {
                "今日重点": "🔥 今日重点",
                "今日关键信号": "🧭 今日关键信号",
                "赛程速览": "🗓️ 赛程速览",
                "爆冷风险": "⚠️ 爆冷风险",
                "重点球队": "👥 重点球队",
                "新闻解读": "🧠 新闻解读",
                "AI建议": "💡 AI建议",
                "关键信息变化": "🔄 关键信息变化",
            }.get(section_name, section_name)
            elements.append(
                {
                    "tag": "markdown",
                    "content": f"**{section_title}**\n" + "\n".join(f"- {line}" for line in lines[:4]),
                }
            )

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "template": "blue",
                    "title": {"tag": "plain_text", "content": title},
                },
                "elements": elements,
            },
        }

    def _extract_sections(self, content: str) -> dict[str, list[str]]:
        sections = {
            "运营速览": [],
            "今日重点": [],
            "今日关键信号": [],
            "赛程速览": [],
            "爆冷风险": [],
            "重点球队": [],
            "新闻解读": [],
            "AI建议": [],
            "关键信息变化": [],
        }
        current = None
        mapping = {
            "## 运营速览": "运营速览",
            "## 今日最值得关注的 3 场比赛": "今日重点",
            "## 今日关键信号": "今日关键信号",
            "## 今日/明日赛程": "赛程速览",
            "## 爆冷风险榜": "爆冷风险",
            "## 重点球队动态": "重点球队",
            "## 🧠 新闻解读": "新闻解读",
            "## AI建议": "AI建议",
            "## 与昨日相比": "关键信息变化",
            "## 📌 运营速览": "运营速览",
            "## 🔥 今日最值得关注的 3 场比赛": "今日重点",
            "## 🧭 今日关键信号": "今日关键信号",
            "## 🗓️ 今日/明日赛程": "赛程速览",
            "## ⚠️ 爆冷风险榜": "爆冷风险",
            "## 👥 重点球队动态": "重点球队",
            "## 💡 AI建议": "AI建议",
            "## 🔄 与昨日相比": "关键信息变化",
        }
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line in mapping:
                current = mapping[line]
                continue
            if not current or not line:
                continue
            if line.startswith("## "):
                current = None
                continue
            if line.startswith("### "):
                sections[current].append(line.replace("### ", "").strip())
                continue
            if line.startswith("- "):
                sections[current].append(line[2:].strip())
        return sections
