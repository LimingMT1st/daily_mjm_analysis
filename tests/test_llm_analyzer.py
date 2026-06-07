from __future__ import annotations

import json
from datetime import UTC, datetime

from analyzers.llm_analyzer import LLMAnalyzer
from models import DailyReportData, Match, MatchAnalysis, MatchResult, NewsItem, Team


def build_report_data() -> DailyReportData:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    match = Match(
        id="fixture-001",
        competition="FIFA World Cup 2026",
        stage="Group Stage",
        kickoff_at=now,
        home_team=Team(id="jpn", name="Japan"),
        away_team=Team(id="usa", name="United States"),
        result=MatchResult(status="scheduled"),
    )
    analysis = MatchAnalysis(
        match_id="fixture-001",
        importance_score=82,
        upset_risk="medium",
        attention_level="A",
        qualification_impact=60,
        news_heat=54,
        explanation="基于新闻热度与关注球队规则，当前比赛值得重点观察。",
        form_summary="近期状态数据有限，先保留中性判断。",
        generated_at=now,
    )
    news_item = NewsItem(
        id="news-001",
        team_id="jpn",
        title="World Cup preview: Japan ready",
        summary="Japan enter the FIFA event with stable preparation.",
        source="Mock Feed",
        url="https://example.com/news-1",
        published_at=now,
    )
    return DailyReportData(
        report_date=now,
        timezone="Asia/Tokyo",
        language="zh-CN",
        focus_teams=[Team(id="jpn", name="Japan")],
        matches=[match],
        standings=[],
        news_items=[news_item],
        injury_items=[],
        team_forms=[],
        match_analyses=[analysis],
    )


def test_llm_analyzer_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    analyzer = LLMAnalyzer()
    markdown = analyzer.analyze(build_report_data())

    assert "当前未配置 `LLM_API_KEY`" in markdown
    assert "## 今日最值得关注的3场比赛" in markdown
    assert "## 爆冷风险榜" in markdown
    assert "## 重点球队动态" in markdown
    assert "【数据推断】" in markdown
    assert "【AI判断】" in markdown
    assert "Japan vs United States" in markdown


def test_llm_analyzer_uses_openai_compatible_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "# LLM Report\n\n## 事实\n- 引用 fixture-001。"
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def mock_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return MockResponse()

    monkeypatch.setattr("analyzers.llm_analyzer.request.urlopen", mock_urlopen)

    analyzer = LLMAnalyzer(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="mock-model",
    )
    markdown = analyzer.analyze(build_report_data())

    assert markdown.startswith("# LLM Report")
    assert captured["url"] == "https://example.com/v1/chat/completions"
    assert captured["payload"]["model"] == "mock-model"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
