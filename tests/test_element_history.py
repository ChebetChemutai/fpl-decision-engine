import json
from pathlib import Path

from fpl_engine.data.contracts import parse_element_history

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "element_summary_sample.json"


def test_empty_current_season_history_before_gw1_is_not_an_error() -> None:
    """Real state as of 2026-08-21: GW1 hasn't been played, so `history` is
    genuinely []. This must parse cleanly, not be treated as a malformed
    or missing-data error.
    """
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    parsed = parse_element_history(player_id=4, raw=raw)

    assert parsed.is_clean
    assert parsed.current_season == []


def test_past_seasons_parse_as_season_level_summaries() -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    parsed = parse_element_history(player_id=4, raw=raw)

    assert len(parsed.past_seasons) == 2
    latest = parsed.past_seasons[-1]
    assert latest.season_name == "2025/26"
    assert latest.total_points == 209
    assert latest.starts == 30


def test_current_season_history_parses_into_gameweek_performance_once_played() -> None:
    """Shape-test for once gameweeks exist — history is empty today, but
    the parser must handle populated entries correctly when they arrive.
    """
    raw = {
        "history": [
            {"round": 1, "minutes": 90, "total_points": 6},
            {"round": 2, "minutes": 90, "total_points": 2},
        ],
        "history_past": [],
    }

    parsed = parse_element_history(player_id=4, raw=raw)

    assert parsed.is_clean
    assert len(parsed.current_season) == 2
    assert parsed.current_season[0].gameweek == 1
    assert parsed.current_season[0].total_points == 6


def test_malformed_gameweek_entry_is_reported_not_fatal() -> None:
    raw = {
        "history": [{"round": 1, "minutes": 90}],  # missing total_points
        "history_past": [],
    }

    parsed = parse_element_history(player_id=4, raw=raw)

    assert not parsed.is_clean
    assert parsed.current_season == []
    assert any(i.entity == "gameweek_performance" for i in parsed.issues)


def test_malformed_season_summary_is_reported_not_fatal() -> None:
    raw = {
        "history": [],
        "history_past": [{"season_name": "2025/26"}],  # missing required fields
    }

    parsed = parse_element_history(player_id=4, raw=raw)

    assert not parsed.is_clean
    assert parsed.past_seasons == []
    assert any(i.entity == "season_summary" for i in parsed.issues)
