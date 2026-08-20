import json
from pathlib import Path

import pytest

from fpl_engine.data.contracts import (
    cross_check_referential_integrity,
    parse_bootstrap,
    parse_fixtures,
    validate_bootstrap_shape,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bootstrap_arsenal_sample.json"


@pytest.fixture
def real_bootstrap() -> dict[str, object]:
    data: dict[str, object] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data


def test_valid_shape_has_no_issues(real_bootstrap: dict[str, object]) -> None:
    assert validate_bootstrap_shape(real_bootstrap) == []


def test_missing_top_level_key_is_flagged() -> None:
    broken = {"elements": [], "teams": []}  # missing "events"

    issues = validate_bootstrap_shape(broken)

    assert len(issues) == 1
    assert "events" in issues[0].message


def test_parse_bootstrap_produces_players_teams_events(
    real_bootstrap: dict[str, object],
) -> None:
    parsed = parse_bootstrap(real_bootstrap)

    assert parsed.is_clean
    assert len(parsed.players) == 10
    assert len(parsed.teams) == 2
    assert len(parsed.events) == 2


def test_parse_bootstrap_aborts_per_record_parsing_on_shape_failure() -> None:
    broken = {"elements": [{"id": 1}]}  # missing teams/events entirely

    parsed = parse_bootstrap(broken)

    assert not parsed.is_clean
    assert parsed.players == []
    assert any("missing required top-level keys" in i.message for i in parsed.issues)


def test_one_malformed_player_does_not_abort_the_rest(
    real_bootstrap: dict[str, object],
) -> None:
    elements = list(real_bootstrap["elements"])  # type: ignore[call-overload]
    broken_player = {**elements[0]}
    del broken_player["now_cost"]  # required field missing
    bootstrap_with_one_bad_record = {**real_bootstrap, "elements": [broken_player, *elements[1:]]}

    parsed = parse_bootstrap(bootstrap_with_one_bad_record)

    assert not parsed.is_clean
    assert len(parsed.players) == 9  # 10 - 1 broken
    assert any(i.entity == "player" for i in parsed.issues)


def test_parse_fixtures_from_real_shape() -> None:
    raw_fixtures = [
        {
            "id": 1,
            "event": 1,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 3,
            "team_a_difficulty": 2,
            "kickoff_time": "2026-08-21T19:00:00Z",
            "finished": False,
        }
    ]

    parsed = parse_fixtures(raw_fixtures)

    assert parsed.is_clean
    assert len(parsed.fixtures) == 1
    assert parsed.fixtures[0].team_h == 1


def test_parse_fixtures_flags_malformed_records() -> None:
    raw_fixtures: list[dict[str, object]] = [{"id": 1}]  # missing team_h/team_a

    parsed = parse_fixtures(raw_fixtures)

    assert not parsed.is_clean
    assert parsed.fixtures == []


def test_referential_integrity_catches_orphaned_team_id(
    real_bootstrap: dict[str, object],
) -> None:
    # Corrupt one player's team_id to reference a team that doesn't exist
    # in the (small, real) teams list this fixture carries.
    corrupted = dict(real_bootstrap)
    elements = [dict(e) for e in corrupted["elements"]]  # type: ignore[union-attr]
    elements[0]["team"] = 999  # no team with id=999 in the fixture
    corrupted["elements"] = elements

    parsed = parse_bootstrap(corrupted)
    integrity_issues = cross_check_referential_integrity(parsed)

    assert any("unknown team_id=999" in i.message for i in integrity_issues)


def test_referential_integrity_is_clean_for_real_data(real_bootstrap: dict[str, object]) -> None:
    parsed = parse_bootstrap(real_bootstrap)

    assert cross_check_referential_integrity(parsed) == []
