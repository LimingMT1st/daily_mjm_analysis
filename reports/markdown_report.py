from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class MarkdownReportRenderer:
    def __init__(self, templates_dir: str | Path | None = None) -> None:
        base_dir = Path(templates_dir) if templates_dir else Path(__file__).parent / "templates"
        self.environment = Environment(
            loader=FileSystemLoader(str(base_dir)),
            autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, context: dict[str, Any]) -> str:
        template = self.environment.get_template("daily_report.md.j2")
        return template.render(**context)

