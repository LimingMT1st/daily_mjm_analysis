from __future__ import annotations

from .match_analyzer import MatchAnalyzer


class AnalyzerManager:
    def __init__(self) -> None:
        self.match_analyzer = MatchAnalyzer()

    def analyze(self, collected: dict) -> dict:
        return {
            "summary": "Analysis logic has not been implemented yet.",
            "data": collected,
        }
