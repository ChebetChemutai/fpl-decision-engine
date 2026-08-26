"""Tests for manager (entry) parsing.

Fixture shapes below are based on published third-party documentation of
the /entry/ endpoints (multiple independent sources agreed on these
field names) — they are NOT independently confirmed via a live fetch in
this codebase, unlike bootstrap-static/element-summary/fixtures, which
were. See docs/manager-integration.md for exactly what's confirmed vs
documented-only. Treat these tests as validating the parser's logic
against a plausible, well-documented shape, not as real-data proof.
"""

from fpl_engine.data.contracts import parse_manager_history, parse_manager_picks
from fpl_engine.domain.manager import ManagerGameweekHistory, ManagerPick, ManagerProfile


def test_manager_profile_parses_documented_shape() -> None:
    raw = {
        "id": 331434,
        "player_first_name": "Test",
        "player_last_name": "Manager",
        "name": "Test FC",
        "summary_overall_points": 114,
        "summary_overall_rank": 1000,
        "current_event": 1,
    }

    profile = ManagerProfile.from_raw(raw)

    assert profile.id == 331434
    assert profile.team_name == "Test FC"
    assert profile.summary_overall_points == 114


def test_manager_profile_handles_null_rank_before_first_gameweek() -> None:
    raw = {
        "id": 1,
        "player_first_name": "New",
        "player_last_name": "Manager",
        "name": "New FC",
        "summary_overall_points": 0,
        "summary_overall_rank": None,
        "current_event": None,
    }

    profile = ManagerProfile.from_raw(raw)

    assert profile.summary_overall_rank is None
    assert profile.current_event is None


def test_manager_gameweek_history_parses_documented_shape() -> None:
    raw = {
        "event": 1,
        "points": 65,
        "total_points": 65,
        "rank": 500000,
        "overall_rank": 500000,
        "bank": 5,
        "value": 1000,
        "event_transfers": 0,
        "event_transfers_cost": 0,
        "points_on_bench": 8,
    }

    entry = ManagerGameweekHistory.from_raw(raw)

    assert entry.event == 1
    assert entry.points == 65
    assert entry.value == 1000  # tenths-of-a-million, i.e. £100.0m


def test_parse_manager_history_skips_malformed_entries() -> None:
    raw = {
        "current": [
            {
                "event": 1, "points": 65, "total_points": 65, "rank": 1,
                "overall_rank": 1, "bank": 0, "value": 1000,
                "event_transfers": 0, "event_transfers_cost": 0, "points_on_bench": 0,
            },
            {"event": 2},  # missing required fields
        ]
    }

    parsed = parse_manager_history(manager_id=1, raw=raw)

    assert not parsed.is_clean
    assert len(parsed.gameweeks) == 1
    assert parsed.gameweeks[0].event == 1


def test_manager_pick_parses_documented_shape() -> None:
    raw = {
        "element": 4, "position": 3, "multiplier": 1,
        "is_captain": False, "is_vice_captain": False,
    }

    pick = ManagerPick.from_raw(raw)

    assert pick.element == 4
    assert pick.position == 3
    assert not pick.is_captain


def test_parse_manager_picks_extracts_active_chip_and_picks() -> None:
    raw = {
        "active_chip": "bboost",
        "picks": [
            {
                "element": 1, "position": 1, "multiplier": 1,
                "is_captain": False, "is_vice_captain": False,
            },
            {
                "element": 4, "position": 2, "multiplier": 2,
                "is_captain": True, "is_vice_captain": False,
            },
        ],
    }

    parsed = parse_manager_picks(manager_id=1, gameweek=1, raw=raw)

    assert parsed.is_clean
    assert parsed.active_chip == "bboost"
    assert len(parsed.picks) == 2
    assert any(p.is_captain for p in parsed.picks)


def test_parse_manager_picks_handles_no_active_chip() -> None:
    raw = {"picks": []}

    parsed = parse_manager_picks(manager_id=1, gameweek=1, raw=raw)

    assert parsed.active_chip is None


def test_parse_manager_picks_skips_malformed_pick() -> None:
    raw = {"picks": [{"element": 1}]}  # missing required fields

    parsed = parse_manager_picks(manager_id=1, gameweek=1, raw=raw)

    assert not parsed.is_clean
    assert parsed.picks == []
