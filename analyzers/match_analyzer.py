from __future__ import annotations

from datetime import UTC, datetime

from models import Match, MatchAnalysis, NewsItem, Standing, TeamForm


KNOCKOUT_KEYWORDS = {
    "knockout",
    "round of 16",
    "quarter-final",
    "quarterfinal",
    "semi-final",
    "semifinal",
    "final",
    "third place",
}
DEFAULT_HOST_NATIONS = {"United States", "Mexico", "Canada"}


class MatchAnalyzer:
    def __init__(self, host_nations: set[str] | None = None) -> None:
        self.host_nations = host_nations or set(DEFAULT_HOST_NATIONS)

    def analyze_match(
        self,
        match: Match,
        standings: list[Standing] | None = None,
        news_items: list[NewsItem] | None = None,
        team_forms: list[TeamForm] | None = None,
        focus_teams: list[str] | None = None,
    ) -> MatchAnalysis:
        standings = standings or []
        news_items = news_items or []
        team_forms = team_forms or []
        focus_teams = focus_teams or []

        related_news = self._filter_related_news(match=match, news_items=news_items)
        home_news = self._team_news(match.home_team.id, related_news)
        away_news = self._team_news(match.away_team.id, related_news)

        news_heat = self._calculate_news_heat(related_news=related_news)
        qualification_impact, qualification_reasons = self._calculate_qualification_impact(
            match=match,
            standings=standings,
        )

        score = 10
        reasons: list[str] = []

        focus_bonus = self._focus_bonus(match=match, focus_teams=focus_teams)
        if focus_bonus:
            score += focus_bonus
            reasons.append("涉及重点关注球队，基础关注度上调。")

        if self._is_knockout_match(match.stage):
            score += 25
            reasons.append("比赛属于淘汰赛阶段，重要性显著提升。")

        if self._is_host_nation_match(match):
            score += 15
            reasons.append("涉及东道主球队，舆论和观赛关注度更高。")

        if news_heat:
            score += min(20, round(news_heat * 0.2))
            reasons.append(f"赛前相关新闻热度为 {news_heat} 分，带来额外关注。")

        if qualification_impact:
            score += min(30, round(qualification_impact * 0.3))
            reasons.extend(qualification_reasons)

        importance_score = max(0, min(100, score))
        attention_level = self._attention_level(importance_score)
        upset_risk = self._calculate_upset_risk(
            match=match,
            standings=standings,
            home_news_count=len(home_news),
            away_news_count=len(away_news),
        )

        form_summary = self._build_form_summary(
            match=match,
            team_forms=team_forms,
        )
        explanation = self._build_explanation(
            match=match,
            reasons=reasons,
            upset_risk=upset_risk,
            form_summary=form_summary,
        )

        return MatchAnalysis(
            match_id=match.id,
            importance_score=importance_score,
            upset_risk=upset_risk,
            attention_level=attention_level,
            qualification_impact=qualification_impact,
            news_heat=news_heat,
            explanation=explanation,
            form_summary=form_summary,
            generated_at=datetime.now(UTC),
        )

    def _filter_related_news(
        self,
        match: Match,
        news_items: list[NewsItem],
    ) -> list[NewsItem]:
        related_team_ids = {match.home_team.id, match.away_team.id}
        related_names = {
            match.home_team.name.casefold(),
            match.away_team.name.casefold(),
            (match.home_team.short_name or "").casefold(),
            (match.away_team.short_name or "").casefold(),
        }

        related: list[NewsItem] = []
        for item in news_items:
            haystack = f"{item.title} {item.summary}".casefold()
            if item.team_id and item.team_id in related_team_ids:
                related.append(item)
                continue
            if any(name and name in haystack for name in related_names):
                related.append(item)
        return related

    def _team_news(self, team_id: str, news_items: list[NewsItem]) -> list[NewsItem]:
        return [item for item in news_items if item.team_id == team_id]

    def _focus_bonus(self, match: Match, focus_teams: list[str]) -> int:
        normalized = {name.casefold() for name in focus_teams}
        bonus = 0
        for team_name in (match.home_team.name, match.away_team.name):
            if team_name.casefold() in normalized:
                bonus += 15
        return min(bonus, 30)

    def _is_knockout_match(self, stage: str) -> bool:
        normalized_stage = stage.casefold()
        return any(keyword in normalized_stage for keyword in KNOCKOUT_KEYWORDS)

    def _is_host_nation_match(self, match: Match) -> bool:
        return (
            match.home_team.name in self.host_nations
            or match.away_team.name in self.host_nations
        )

    def _calculate_news_heat(self, related_news: list[NewsItem]) -> int:
        if not related_news:
            return 0
        unique_sources = {item.source.casefold() for item in related_news if item.source}
        score = len(related_news) * 18 + len(unique_sources) * 6
        return min(100, score)

    def _calculate_qualification_impact(
        self,
        match: Match,
        standings: list[Standing],
    ) -> tuple[int, list[str]]:
        if self._is_knockout_match(match.stage):
            return 95, ["淘汰赛为单场决定走向，出线影响接近满分。"]

        rows = [
            row
            for row in standings
            if row.team.id in {match.home_team.id, match.away_team.id}
            and row.stage.casefold() == match.stage.casefold()
        ]
        if len(rows) < 2:
            return 35, ["缺少完整积分背景，先给出中等出线影响评分。"]

        rows_by_team = {row.team.id: row for row in rows}
        home_row = rows_by_team.get(match.home_team.id)
        away_row = rows_by_team.get(match.away_team.id)
        if home_row is None or away_row is None:
            return 35, ["缺少完整积分背景，先给出中等出线影响评分。"]

        score = 40
        reasons: list[str] = []
        point_gap = abs(home_row.points - away_row.points)

        if max(home_row.position, away_row.position) <= 2:
            score += 20
            reasons.append("两队都处在潜在出线区附近，积分变化更关键。")
        if point_gap <= 3:
            score += 20
            reasons.append("双方积分接近，赛果可能直接改变出线形势。")
        if home_row.played >= 2 and away_row.played >= 2:
            score += 10
            reasons.append("小组赛后段比赛，单场结果对晋级影响更直接。")

        if not reasons:
            reasons.append("当前积分格局一般，出线影响保持中等。")
        return min(100, score), reasons

    def _calculate_upset_risk(
        self,
        match: Match,
        standings: list[Standing],
        home_news_count: int,
        away_news_count: int,
    ) -> str:
        strength_gap = self._calculate_strength_gap(match=match, standings=standings)
        if strength_gap < 8:
            return "low"

        home_strength = self._team_strength(match.home_team.id, match.home_team.ranking, standings)
        away_strength = self._team_strength(match.away_team.id, match.away_team.ranking, standings)

        weaker_team_id = match.home_team.id if home_strength > away_strength else match.away_team.id
        weaker_team_news = home_news_count if weaker_team_id == match.home_team.id else away_news_count

        if strength_gap >= 20 and weaker_team_news >= 2:
            return "high"
        if strength_gap >= 12 and weaker_team_news >= 1:
            return "medium"
        return "low"

    def _attention_level(self, importance_score: int) -> str:
        if importance_score >= 85:
            return "S"
        if importance_score >= 70:
            return "A"
        if importance_score >= 50:
            return "B"
        return "C"

    def _calculate_strength_gap(self, match: Match, standings: list[Standing]) -> int:
        home_strength = self._team_strength(match.home_team.id, match.home_team.ranking, standings)
        away_strength = self._team_strength(match.away_team.id, match.away_team.ranking, standings)
        return abs(home_strength - away_strength)

    def _team_strength(
        self,
        team_id: str,
        ranking: int | None,
        standings: list[Standing],
    ) -> int:
        if ranking is not None:
            return ranking

        for row in standings:
            if row.team.id == team_id:
                return row.position * 10
        return 50

    def _build_form_summary(self, match: Match, team_forms: list[TeamForm]) -> str:
        forms = {item.team_id: item for item in team_forms}
        home_form = forms.get(match.home_team.id)
        away_form = forms.get(match.away_team.id)

        if home_form is None or away_form is None:
            return "近期状态数据有限，先保留中性判断。"

        if home_form.wins_in_last_five > away_form.wins_in_last_five:
            leader = match.home_team.name
        elif away_form.wins_in_last_five > home_form.wins_in_last_five:
            leader = match.away_team.name
        else:
            leader = "双方"

        return (
            f"{leader}近期状态更占优；"
            f"{match.home_team.name}近五场{home_form.wins_in_last_five}胜，"
            f"{match.away_team.name}近五场{away_form.wins_in_last_five}胜。"
        )

    def _build_explanation(
        self,
        match: Match,
        reasons: list[str],
        upset_risk: str,
        form_summary: str,
    ) -> str:
        base = (
            f"{match.home_team.name} vs {match.away_team.name} 的规则分析已完成。"
        )
        reason_text = "；".join(reasons) if reasons else "当前可用上下文较少，评分以基础规则为主。"
        return f"{base}{reason_text} 爆冷风险判断为 {upset_risk}。{form_summary}"
