from __future__ import annotations

from pathlib import Path

from collectors.fixture_collector import FixtureCollector
from models import Match


def test_fixture_collector_loads_sample_matches() -> None:
    collector = FixtureCollector(
        sample_path=Path("config/fixtures.sample.json"),
        timezone="Asia/Tokyo",
    )

    matches = collector.load_matches()

    assert len(matches) == 4
    assert all(isinstance(match, Match) for match in matches)
    assert matches[0].home_team.name == "Japan"


def test_fixture_collector_filters_today_tomorrow_and_next_three_days() -> None:
    collector = FixtureCollector(
        sample_path=Path("config/fixtures.sample.json"),
        timezone="Asia/Tokyo",
    )

    today_matches = collector.collect(window="today", run_date="2026-06-07")
    tomorrow_matches = collector.collect(window="tomorrow", run_date="2026-06-07")
    next_three_day_matches = collector.collect(
        window="next_3_days", run_date="2026-06-07"
    )

    assert [match.id for match in today_matches] == ["fixture-001"]
    assert [match.id for match in tomorrow_matches] == ["fixture-002"]
    assert [match.id for match in next_three_day_matches] == [
        "fixture-001",
        "fixture-002",
        "fixture-003",
    ]
