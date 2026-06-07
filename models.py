from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AwareDateTimeModel(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def validate_datetime_fields(cls, value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("datetime fields must be timezone-aware")
        return value


class Team(AwareDateTimeModel):
    id: str = Field(description="Unique team identifier.")
    name: str = Field(description="Official team name.")
    short_name: str | None = Field(
        default=None, description="Short display name for the team."
    )
    fifa_code: str | None = Field(
        default=None, description="FIFA code or other short team code."
    )
    confederation: str | None = Field(
        default=None, description="Football confederation the team belongs to."
    )
    group_name: str | None = Field(
        default=None, description="Tournament group or stage label for the team."
    )
    coach: str | None = Field(
        default=None, description="Current head coach of the team."
    )
    ranking: int | None = Field(
        default=None, description="Current ranking or seeding number."
    )


class MatchResult(AwareDateTimeModel):
    home_score: int | None = Field(
        default=None, description="Goals scored by the home team."
    )
    away_score: int | None = Field(
        default=None, description="Goals scored by the away team."
    )
    status: str = Field(description="Match status such as scheduled, live, or finished.")
    winner_team_id: str | None = Field(
        default=None, description="Identifier of the winning team, if available."
    )
    decided_by: str | None = Field(
        default=None,
        description="How the result was decided, such as regular_time or penalties.",
    )


class Match(AwareDateTimeModel):
    id: str = Field(description="Unique match identifier.")
    competition: str = Field(description="Competition or tournament name.")
    stage: str = Field(description="Tournament stage such as group stage or knockout.")
    venue: str | None = Field(default=None, description="Venue or stadium name.")
    city: str | None = Field(default=None, description="Host city of the match.")
    kickoff_at: datetime = Field(description="Scheduled kickoff datetime with timezone.")
    home_team: Team = Field(description="Home team information.")
    away_team: Team = Field(description="Away team information.")
    result: MatchResult | None = Field(
        default=None, description="Match result or current score information."
    )
    importance: str | None = Field(
        default=None, description="Business-defined importance label for the match."
    )


class Standing(AwareDateTimeModel):
    team: Team = Field(description="Team included in the standings row.")
    stage: str = Field(description="Stage or group the standing belongs to.")
    position: int = Field(description="Current rank position.")
    played: int = Field(description="Number of matches played.")
    won: int = Field(description="Number of matches won.")
    drawn: int = Field(description="Number of matches drawn.")
    lost: int = Field(description="Number of matches lost.")
    goals_for: int = Field(description="Total goals scored.")
    goals_against: int = Field(description="Total goals conceded.")
    goal_difference: int = Field(description="Goal difference value.")
    points: int = Field(description="Total points earned.")
    updated_at: datetime = Field(
        description="Last update time for this standings record with timezone."
    )


class NewsItem(AwareDateTimeModel):
    id: str = Field(description="Unique news item identifier.")
    team_id: str | None = Field(
        default=None, description="Related team identifier if the news is team-specific."
    )
    title: str = Field(description="News headline.")
    summary: str = Field(description="Short summary of the news content.")
    source: str = Field(description="Publisher or source name.")
    url: str = Field(description="Original URL for the news article.")
    published_at: datetime = Field(
        description="Publication datetime of the news item with timezone."
    )
    sentiment: str | None = Field(
        default=None, description="Simple sentiment label such as positive or negative."
    )


class InjuryItem(AwareDateTimeModel):
    id: str = Field(description="Unique injury or availability item identifier.")
    team_id: str = Field(description="Identifier of the related team.")
    player_name: str = Field(description="Name of the player involved.")
    status: str = Field(description="Availability status such as injured, doubtful, or out.")
    issue: str = Field(description="Short description of the injury or absence reason.")
    expected_return_at: datetime | None = Field(
        default=None, description="Expected return datetime with timezone if known."
    )
    updated_at: datetime = Field(
        description="Last update datetime for the injury item with timezone."
    )
    source: str | None = Field(
        default=None, description="Source of the injury or squad information."
    )


class TeamForm(AwareDateTimeModel):
    team_id: str = Field(description="Identifier of the related team.")
    recent_results: list[str] = Field(
        default_factory=list,
        description="Recent match outcomes such as W, D, and L in chronological order.",
    )
    unbeaten_streak: int = Field(description="Current unbeaten streak length.")
    wins_in_last_five: int = Field(description="Number of wins in the last five matches.")
    goals_scored_last_five: int = Field(
        description="Goals scored across the last five matches."
    )
    goals_conceded_last_five: int = Field(
        description="Goals conceded across the last five matches."
    )
    updated_at: datetime = Field(
        description="Last update datetime for the form snapshot with timezone."
    )


class MatchAnalysis(AwareDateTimeModel):
    match_id: str = Field(description="Identifier of the match being analyzed.")
    importance_score: int = Field(
        description="Rule-based importance score from 0 to 100."
    )
    upset_risk: str = Field(description="Estimated upset risk label.")
    attention_level: str = Field(description="Attention level from S, A, B, or C.")
    qualification_impact: int = Field(
        description="Estimated qualification impact score from 0 to 100."
    )
    news_heat: int = Field(description="News heat score from 0 to 100.")
    explanation: str = Field(
        description="Human-readable explanation for the analysis result."
    )
    form_summary: str = Field(description="Short summary of both teams' recent form.")
    generated_at: datetime = Field(
        description="Datetime when this analysis was produced with timezone."
    )


class DailyReportData(AwareDateTimeModel):
    report_date: datetime = Field(
        description="Logical report date or generation datetime with timezone."
    )
    timezone: str = Field(description="Timezone used to interpret the report timeline.")
    language: str = Field(description="Language code used for the report output.")
    focus_teams: list[Team] = Field(
        default_factory=list, description="Teams highlighted by the report configuration."
    )
    matches: list[Match] = Field(
        default_factory=list, description="Matches included in the daily report."
    )
    standings: list[Standing] = Field(
        default_factory=list, description="Standings rows included in the report."
    )
    news_items: list[NewsItem] = Field(
        default_factory=list, description="News items included in the report."
    )
    injury_items: list[InjuryItem] = Field(
        default_factory=list, description="Injury or squad availability items."
    )
    team_forms: list[TeamForm] = Field(
        default_factory=list, description="Recent form snapshots for tracked teams."
    )
    match_analyses: list[MatchAnalysis] = Field(
        default_factory=list, description="Per-match analysis entries for the report."
    )
    generated_markdown: str | None = Field(
        default=None, description="Rendered markdown output if already generated."
    )
