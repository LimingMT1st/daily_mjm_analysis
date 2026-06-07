from __future__ import annotations

import json
from pathlib import Path

from collectors.football_data_collector import FootballDataCollector


def test_football_data_collector_falls_back_to_sample_without_api_key(tmp_path, capsys) -> None:
    sample_path = tmp_path / "fixtures.sample.json"
    sample_path.write_text(
        json.dumps(
            [
                {
                    "id": "fixture-001",
                    "competition": "FIFA World Cup 2026",
                    "stage": "Group Stage",
                    "venue": "Tokyo Dome",
                    "city": "Tokyo",
                    "kickoff_at": "2026-06-07T19:00:00+09:00",
                    "home_team": {"id": "jpn", "name": "Japan"},
                    "away_team": {"id": "can", "name": "Canada"},
                    "result": {"status": "scheduled"},
                }
            ]
        ),
        encoding="utf-8",
    )
    collector = FootballDataCollector(
        api_key="",
        timezone="Asia/Tokyo",
        sample_collector=None,
    )
    collector.sample_collector.sample_path = sample_path

    matches = collector.collect_matches(window="today", run_date="2026-06-07")

    captured = capsys.readouterr()
    assert len(matches) == 1
    assert matches[0].home_team.name == "Japan"
    assert "using local sample fixtures" in captured.out


def test_football_data_collector_maps_matches_and_standings(monkeypatch) -> None:
    match_payload = {
        "matches": [
            {
                "id": 1001,
                "utcDate": "2026-06-07T10:00:00Z",
                "status": "SCHEDULED",
                "stage": "GROUP_STAGE",
                "group": "GROUP_A",
                "competition": {"name": "FIFA World Cup"},
                "area": {"name": "Japan"},
                "homeTeam": {"id": 1, "name": "Japan", "shortName": "Japan", "tla": "JPN"},
                "awayTeam": {"id": 2, "name": "Canada", "shortName": "Canada", "tla": "CAN"},
                "score": {
                    "winner": None,
                    "duration": "REGULAR",
                    "fullTime": {"home": None, "away": None},
                },
            }
        ]
    }
    standings_payload = {
        "standings": [
            {
                "stage": "GROUP_STAGE",
                "group": "GROUP_A",
                "table": [
                    {
                        "position": 1,
                        "playedGames": 2,
                        "won": 2,
                        "draw": 0,
                        "lost": 0,
                        "points": 6,
                        "goalsFor": 4,
                        "goalsAgainst": 1,
                        "goalDifference": 3,
                        "team": {"id": 1, "name": "Japan", "shortName": "Japan", "tla": "JPN"},
                    }
                ],
            }
        ]
    }
    calls: list[str] = []

    def mock_fetch_json(self, path, query=None):
        calls.append(path)
        if path.endswith("/matches"):
            return match_payload
        return standings_payload

    monkeypatch.setattr(FootballDataCollector, "_fetch_json", mock_fetch_json)
    collector = FootballDataCollector(api_key="test-key", timezone="Asia/Tokyo")

    matches = collector.collect_matches(window="today", run_date="2026-06-07")
    standings = collector.collect_standings()

    assert calls == ["/competitions/WC/matches", "/competitions/WC/standings"]
    assert len(matches) == 1
    assert matches[0].competition == "FIFA World Cup"
    assert matches[0].stage == "GROUP_A"
    assert matches[0].home_team.fifa_code == "JPN"
    assert len(standings) == 1
    assert standings[0].team.name == "Japan"
    assert standings[0].points == 6


def test_football_data_collector_retries_then_succeeds(monkeypatch) -> None:
    attempts = {"count": 0}

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"matches": []}'

    def mock_urlopen(req, timeout=15):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise OSError("temporary network issue")
        return MockResponse()

    monkeypatch.setattr("collectors.football_data_collector.request.urlopen", mock_urlopen)
    monkeypatch.setattr("collectors.football_data_collector.time.sleep", lambda seconds: None)

    collector = FootballDataCollector(api_key="test-key", timezone="Asia/Tokyo", retries=2)
    payload = collector._fetch_json("/competitions/WC/matches")

    assert attempts["count"] == 2
    assert payload == {"matches": []}
