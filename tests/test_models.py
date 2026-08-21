import json
from pathlib import Path

import pytest

from fpl_engine.domain.models import Player, PlayerStatus, Position

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bootstrap_arsenal_sample.json"


@pytest.fixture
def real_elements() -> list[dict[str, object]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["elements"]  # type: ignore[no-any-return]


def test_parses_available_outfield_player(real_elements: list[dict[str, object]]) -> None:
    raw = next(e for e in real_elements if e["web_name"] == "Saka")

    player = Player.from_bootstrap_element(raw)

    assert player.id == 12
    assert player.web_name == "Saka"
    assert player.position == Position.MID
    assert player.price == 9.5  # now_cost 95 -> £9.5m
    assert player.status == PlayerStatus.AVAILABLE
    assert player.ep_next == 3.2


def test_parses_injured_player_with_zero_chance(real_elements: list[dict[str, object]]) -> None:
    raw = next(e for e in real_elements if e["web_name"] == "J.Timber")

    player = Player.from_bootstrap_element(raw)

    assert player.status == PlayerStatus.INJURED
    assert player.chance_of_playing_next_round == 0


def test_parses_goalkeeper_position(real_elements: list[dict[str, object]]) -> None:
    raw = next(e for e in real_elements if e["web_name"] == "Raya")

    player = Player.from_bootstrap_element(raw)

    assert player.position == Position.GKP
    assert player.price == 6.0


def test_parses_team_from_bootstrap_shape() -> None:
    from fpl_engine.domain.models import Team

    raw = {
        "id": 1,
        "name": "Arsenal",
        "short_name": "ARS",
        "strength_overall_home": 4,
        "strength_overall_away": 5,
        "strength_attack_home": 0,
        "strength_attack_away": 0,
        "strength_defence_home": 0,
        "strength_defence_away": 0,
    }

    team = Team.from_bootstrap_team(raw)

    assert team.id == 1
    assert team.short_name == "ARS"


def test_parses_gameweek_event_from_bootstrap_shape() -> None:
    from fpl_engine.domain.models import GameweekEvent

    raw = {
        "id": 1,
        "name": "Gameweek 1",
        "deadline_time": "2026-08-21T17:30:00Z",
        "finished": False,
        "is_current": False,
        "is_next": True,
    }

    event = GameweekEvent.from_bootstrap_event(raw)

    assert event.id == 1
    assert event.is_next is True


def test_parses_fixture_from_raw_shape() -> None:
    from fpl_engine.domain.models import Fixture

    raw = {
        "id": 1,
        "event": 1,
        "team_h": 1,
        "team_a": 2,
        "team_h_difficulty": 3,
        "team_a_difficulty": 2,
        "kickoff_time": "2026-08-21T19:00:00Z",
        "finished": False,
    }

    fixture = Fixture.from_raw_fixture(raw)

    assert fixture.team_h == 1
    assert fixture.team_a == 2
    assert fixture.event == 1


def test_parses_fixture_with_no_scheduled_event_yet() -> None:
    from fpl_engine.domain.models import Fixture

    raw = {"id": 1, "event": None, "team_h": 1, "team_a": 2}

    fixture = Fixture.from_raw_fixture(raw)

    assert fixture.event is None
    assert fixture.finished is False


def test_parses_season_summary_from_history_past_shape() -> None:
    from fpl_engine.domain.models import SeasonSummary

    raw = {
        "season_name": "2025/26",
        "element_code": 226597,
        "start_cost": 60,
        "end_cost": 73,
        "total_points": 209,
        "minutes": 2750,
        "goals_scored": 3,
        "assists": 5,
        "clean_sheets": 18,
        "starts": 30,
    }

    summary = SeasonSummary.from_history_past_entry(raw)

    assert summary.season_name == "2025/26"
    assert summary.total_points == 209
    assert summary.starts == 30
