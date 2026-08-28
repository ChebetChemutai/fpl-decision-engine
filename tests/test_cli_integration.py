"""CLI integration tests.

Mocks FplClient entirely — the unit test suite must never depend on the
live FPL API (integration spec Sec 12). `ingest`/`ingest_history` are
tested by substituting a fake client; `squad` is tested by writing real-
shaped snapshot files directly, since that command never touches the
network itself, only the filesystem.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from fpl_engine.cli import app

runner = CliRunner()

# A tiny but structurally real bootstrap-static shape: enough players to
# fill a legal squad (2 GKP, 5 DEF, 5 MID, 3 FWD = 15, spread across 6
# clubs to respect the max-3-per-club rule), plus one MID with ep_next=0
# to exercise the historical-prior fallback path.
def _player(
    pid: int, name: str, team: int, element_type: int, cost: int, ep_next: str
) -> dict[str, Any]:
    return {
        "id": pid, "web_name": name, "team": team, "element_type": element_type,
        "now_cost": cost, "status": "a", "chance_of_playing_next_round": None,
        "ep_next": ep_next, "points_per_game": ep_next, "selected_by_percent": "5.0",
    }


_FAKE_BOOTSTRAP: dict[str, Any] = {
    "elements": [
        _player(1, "GK1", 1, 1, 45, "4.0"),
        _player(2, "GK2", 2, 1, 40, "3.0"),
        _player(3, "DEF1", 1, 2, 45, "3.0"),
        _player(4, "DEF2", 2, 2, 45, "3.2"),
        _player(5, "DEF3", 3, 2, 45, "2.8"),
        _player(6, "DEF4", 4, 2, 45, "2.9"),
        _player(7, "DEF5", 5, 2, 45, "3.1"),
        _player(8, "MID1", 3, 3, 55, "0.0"),  # ep_next=0 -> exercises historical-prior fallback
        _player(9, "MID2", 4, 3, 60, "3.5"),
        _player(10, "MID3", 5, 3, 60, "3.6"),
        _player(11, "MID4", 6, 3, 55, "3.0"),
        _player(12, "MID5", 6, 3, 55, "3.1"),
        _player(16, "MID6", 4, 3, 55, "3.2"),
        _player(13, "FWD1", 1, 4, 55, "2.5"),
        _player(14, "FWD2", 2, 4, 55, "2.6"),
        _player(15, "FWD3", 3, 4, 55, "2.4"),
    ],
    "teams": [
        {
            "id": i, "name": f"Team {i}", "short_name": f"TM{i}",
            "strength_overall_home": 3, "strength_overall_away": 3,
            "strength_attack_home": 3, "strength_attack_away": 3,
            "strength_defence_home": 3, "strength_defence_away": 3,
        }
        for i in range(1, 7)
    ],
    "events": [
        {
            "id": 1, "name": "Gameweek 1", "deadline_time": "2026-08-21T17:30:00Z",
            "finished": False, "is_current": False, "is_next": True,
        }
    ],
    "game_config": {"settings": {"static_content_url": "https://example.com/fantasy/2026_27/img"}},
}

_FAKE_FIXTURES: list[dict[str, Any]] = [
    {
        "id": 1, "event": 1, "team_h": 1, "team_a": 2,
        "team_h_difficulty": 2, "team_a_difficulty": 4,
        "kickoff_time": "2026-08-21T19:00:00Z", "finished": False,
    },
    {
        "id": 2, "event": 1, "team_h": 3, "team_a": 4,
        "team_h_difficulty": 3, "team_a_difficulty": 3,
        "kickoff_time": "2026-08-21T19:00:00Z", "finished": False,
    },
    {
        "id": 3, "event": 1, "team_h": 5, "team_a": 6,
        "team_h_difficulty": 2, "team_a_difficulty": 4,
        "kickoff_time": "2026-08-21T19:00:00Z", "finished": False,
    },
]


class _FakeFplClient:
    """Stand-in for FplClient — no network, deterministic fake data."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> _FakeFplClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass

    def fetch_bootstrap(self) -> dict[str, Any]:
        return _FAKE_BOOTSTRAP

    def fetch_fixtures(self, event: int | None = None) -> list[dict[str, Any]]:
        return _FAKE_FIXTURES

    def fetch_element_summary(self, element_id: int) -> dict[str, Any]:
        return {"history": [], "history_past": []}


def _write_snapshot(
    tmp_path: Path, source: str, season: str, gameweek: int, payload: dict[str, Any]
) -> None:
    target_dir = tmp_path / "raw" / source / season / str(gameweek)
    target_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "source": source, "season": season, "gameweek": gameweek,
        "schema_version": 1, "captured_at": "20260821T000000Z", "payload": payload,
    }
    (target_dir / "20260821T000000Z.json").write_text(json.dumps(envelope), encoding="utf-8")


def test_ingest_writes_bootstrap_and_fixtures_snapshots(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeFplClient)

    result = runner.invoke(app, ["ingest", "--gameweek", "1"])

    assert result.exit_code == 0
    assert "bootstrap snapshot" in result.stdout
    assert "players ingested   : 16" in result.stdout
    bootstrap_files = list((tmp_path / "raw" / "fpl_bootstrap").rglob("*.json"))
    fixtures_files = list((tmp_path / "raw" / "fpl_fixtures").rglob("*.json"))
    assert len(bootstrap_files) == 1
    assert len(fixtures_files) == 1


def test_ingest_history_fetches_every_player_from_latest_bootstrap(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeFplClient)
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    result = runner.invoke(app, ["ingest-history", "--gameweek", "1"])

    assert result.exit_code == 0
    assert "players fetched           : 16" in result.stdout
    history_files = list((tmp_path / "raw" / "fpl_element_history").rglob("*.json"))
    assert len(history_files) == 1


def test_ingest_history_respects_limit(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeFplClient)
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    result = runner.invoke(app, ["ingest-history", "--gameweek", "1", "--limit", "3"])

    assert result.exit_code == 0
    assert "players fetched           : 3" in result.stdout


def test_ingest_history_fails_clearly_without_a_bootstrap_snapshot(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["ingest-history", "--gameweek", "1"])

    assert result.exit_code == 1
    assert "fpl ingest --gameweek 1" in result.stdout


def test_squad_fails_clearly_without_a_snapshot(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["squad", "--gameweek", "1"])

    assert result.exit_code == 1
    assert "fpl ingest --gameweek 1" in result.stdout


def test_squad_rejects_invalid_mode(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["squad", "--gameweek", "1", "--mode", "bogus"])

    assert result.exit_code == 1
    assert "bogus" in result.stdout


def test_squad_baseline_mode_produces_a_legal_squad(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    result = runner.invoke(
        app, ["squad", "--gameweek", "1", "--budget", "9999", "--mode", "baseline"]
    )

    assert result.exit_code == 0
    assert "BASELINE MODEL" in result.stdout


def test_squad_enhanced_mode_falls_back_gracefully_without_fixtures_or_history(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Enhanced mode with neither fixtures nor element-history ingested
    must degrade to neutral fixture multipliers and no historical priors -
    never crash.
    """
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    result = runner.invoke(app, ["squad", "--gameweek", "1", "--budget", "9999"])

    assert result.exit_code == 0
    assert "ENHANCED MODEL" in result.stdout
    assert "fixture difficulty skipped" in result.stdout
    assert "historical priors skipped" in result.stdout


def test_squad_enhanced_mode_uses_fixture_difficulty_when_available(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)
    _write_snapshot(tmp_path, "fpl_fixtures", "2026_27", 1, {"fixtures": _FAKE_FIXTURES})

    result = runner.invoke(app, ["squad", "--gameweek", "1", "--budget", "9999"])

    assert result.exit_code == 0
    assert "fixture difficulty skipped" not in result.stdout


# --- chip-status / chip-play ---------------------------------------------


def test_chip_status_shows_all_four_chips(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["chip-status", "--gameweek", "1"])

    assert result.exit_code == 0
    assert "wildcard" in result.stdout
    assert "free_hit" in result.stdout
    assert "bench_boost" in result.stdout
    assert "triple_captain" in result.stdout


def test_chip_status_shows_wildcard_ineligible_in_gw1(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["chip-status", "--gameweek", "1"])

    assert result.exit_code == 0
    wildcard_line = next(line for line in result.stdout.splitlines() if "wildcard" in line)
    assert "not eligible" in wildcard_line


def test_chip_status_shows_bench_boost_eligible_in_gw1(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["chip-status", "--gameweek", "1"])

    assert result.exit_code == 0
    bb_line = next(line for line in result.stdout.splitlines() if "bench_boost" in line)
    assert "available" in bb_line


def test_chip_play_records_a_legal_chip(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["chip-play", "--chip", "bench_boost", "--gameweek", "1"])

    assert result.exit_code == 0
    assert "Recorded" in result.stdout
    assert (tmp_path / "state" / "chips.json").exists()


def test_chip_play_rejects_wildcard_in_gameweek_1(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["chip-play", "--chip", "wildcard", "--gameweek", "1"])

    assert result.exit_code == 1
    assert "Cannot play" in result.stdout


def test_chip_play_rejects_playing_the_same_chip_twice(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    runner.invoke(app, ["chip-play", "--chip", "bench_boost", "--gameweek", "1"])

    result = runner.invoke(app, ["chip-play", "--chip", "bench_boost", "--gameweek", "5"])

    assert result.exit_code == 1
    assert "already used" in result.stdout


def test_chip_play_rejects_unknown_chip_name(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["chip-play", "--chip", "super_sub", "--gameweek", "1"])

    assert result.exit_code == 1
    assert "not a valid chip" in result.stdout


# --- transfer-check --------------------------------------------------------


def _current_squad_ids() -> list[str]:
    """All 16 fake players except MID6 (id 16) - a legal 15-man squad
    (2 GKP, 5 DEF, 5 MID, 3 FWD) drawn from _FAKE_BOOTSTRAP."""
    return [str(i) for i in range(1, 16)]


def test_transfer_check_valid_transfer_is_legal(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    args = ["transfer-check", "--gameweek", "1", "--free-transfers", "1"]
    for pid in _current_squad_ids():
        args += ["--current", pid]
    args += ["--out", "8", "--in", "16"]  # swap MID1 (ep_next=0) for MID6

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert "LEGAL" in result.stdout
    assert "Cost: 0 points" in result.stdout  # 1 transfer, 1 free


def test_transfer_check_reports_hit_cost_beyond_free_transfers(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    args = ["transfer-check", "--gameweek", "1", "--free-transfers", "0"]
    for pid in _current_squad_ids():
        args += ["--current", pid]
    args += ["--out", "8", "--in", "16"]

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert "Cost: 4 points" in result.stdout


def test_transfer_check_rejects_transferring_out_a_player_not_in_current_squad(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    args = ["transfer-check", "--gameweek", "1"]
    for pid in _current_squad_ids():
        args += ["--current", pid]
    args += ["--out", "16", "--in", "8"]  # 16 (MID6) isn't in --current

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "not in --current" in result.stdout


def test_transfer_check_rejects_unknown_player_id(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    args = ["transfer-check", "--gameweek", "1"]
    for pid in _current_squad_ids():
        args += ["--current", pid]
    args += ["--out", "8", "--in", "9999"]  # doesn't exist

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "Unknown player ID" in result.stdout


def test_transfer_check_flags_a_squad_made_illegal_by_the_transfer(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Swap a GKP out for the extra MID (id 16), leaving only 1 GKP - an
    illegal squad the resulting-squad validation must catch."""
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    args = ["transfer-check", "--gameweek", "1"]
    for pid in _current_squad_ids():
        args += ["--current", pid]
    args += ["--out", "1", "--in", "16"]  # out: GK1, in: MID6 -> only 1 GKP left

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "ILLEGAL" in result.stdout


def test_transfer_check_requires_matching_out_and_in_counts(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    args = ["transfer-check", "--gameweek", "1"]
    for pid in _current_squad_ids():
        args += ["--current", pid]
    args += ["--out", "8", "--out", "9", "--in", "16"]  # 2 out, 1 in

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "same count" in result.stdout


# --- backtest ---------------------------------------------------------------


def test_backtest_reports_zero_cases_honestly_when_no_real_results_exist(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """The actual real-world state today: GW1 has been ingested (bootstrap)
    but not yet played out, so element-history has no results for it.
    Must report 0 cases plainly - not a fabricated or misleading metric.
    """
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)
    empty_histories = {str(i): {"history": [], "history_past": []} for i in range(1, 17)}
    _write_snapshot(
        tmp_path, "fpl_element_history", "2026_27", 1, {"player_histories": empty_histories}
    )

    result = runner.invoke(app, ["backtest", "--gameweek", "1"])

    assert result.exit_code == 0
    assert "0 cases" in result.stdout
    assert "not an error" in result.stdout


def test_backtest_fails_clearly_without_required_snapshots(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(app, ["backtest", "--gameweek", "1"])

    assert result.exit_code == 1
    assert "Missing snapshot" in result.stdout


def test_backtest_runs_a_real_evaluation_when_results_exist(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Once real per-gameweek results exist (simulated here with a
    deterministic, clearly-synthetic history - see test_data_pipeline.py's
    module docstring for why synthetic fixtures are legitimate for this),
    the command must actually run both baselines and report real numbers.
    """
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    histories = {}
    for i in range(1, 17):
        # every player has a GW1 result, so GW1 is backtestable
        histories[str(i)] = {
            "history": [{"round": 1, "minutes": 90, "total_points": 4}],
            "history_past": [],
        }
    _write_snapshot(tmp_path, "fpl_element_history", "2026_27", 1, {"player_histories": histories})

    result = runner.invoke(app, ["backtest", "--gameweek", "1"])

    assert result.exit_code == 0
    assert "REAL HISTORICAL EVALUATION" in result.stdout
    assert "16 case(s)" in result.stdout
    assert "PositionAverageBaseline" in result.stdout
    assert "FormWeightedBaseline" in result.stdout


# --- manager status/history/picks -------------------------------------------


class _FakeManagerFplClient(_FakeFplClient):
    """Extends the existing fake client with manager (entry) endpoints."""

    def fetch_manager_entry(self, manager_id: int) -> dict[str, Any]:
        return {
            "id": manager_id,
            "player_first_name": "Test",
            "player_last_name": "Manager",
            "name": "Test FC",
            "summary_overall_points": 65,
            "summary_overall_rank": 500000,
            "current_event": 1,
        }

    def fetch_manager_history(self, manager_id: int) -> dict[str, Any]:
        return {
            "current": [
                {
                    "event": 1, "points": 65, "total_points": 65, "rank": 500000,
                    "overall_rank": 500000, "bank": 5, "value": 1000,
                    "event_transfers": 0, "event_transfers_cost": 0, "points_on_bench": 8,
                }
            ]
        }

    def fetch_manager_picks(self, manager_id: int, event_id: int) -> dict[str, Any]:
        return {
            "active_chip": None,
            "picks": [
                {
                    "element": 1, "position": 1, "multiplier": 1,
                    "is_captain": False, "is_vice_captain": False, "element_type": 1,
                },
                {
                    "element": 4, "position": 2, "multiplier": 2,
                    "is_captain": True, "is_vice_captain": False, "element_type": 2,
                },
            ],
        }


def test_manager_status_prints_profile(monkeypatch: Any) -> None:
    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeManagerFplClient)

    result = runner.invoke(app, ["manager", "status", "--manager-id", "331434"])

    assert result.exit_code == 0
    assert "Test FC" in result.stdout
    assert "65" in result.stdout


def test_manager_history_prints_gameweek_rows(monkeypatch: Any) -> None:
    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeManagerFplClient)

    result = runner.invoke(app, ["manager", "history", "--manager-id", "331434"])

    assert result.exit_code == 0
    assert "GW1" in result.stdout


def test_manager_picks_prints_captain_marker(monkeypatch: Any) -> None:
    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeManagerFplClient)

    result = runner.invoke(
        app, ["manager", "picks", "--manager-id", "331434", "--gameweek", "1"]
    )

    assert result.exit_code == 0
    assert "(C)" in result.stdout


def test_manager_picks_marks_bench_slots(monkeypatch: Any) -> None:
    class _FakeWithBench(_FakeManagerFplClient):
        def fetch_manager_picks(self, manager_id: int, event_id: int) -> dict[str, Any]:
            return {
                "active_chip": None,
                "picks": [
                    {
                        "element": 1, "position": 12, "multiplier": 0,
                        "is_captain": False, "is_vice_captain": False, "element_type": 1,
                    }
                ],
            }

    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeWithBench)

    result = runner.invoke(
        app, ["manager", "picks", "--manager-id", "331434", "--gameweek", "1"]
    )

    assert result.exit_code == 0
    assert "[bench]" in result.stdout


# --- manager evaluate --------------------------------------------------------


def test_manager_evaluate_compares_actual_vs_baseline(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    # Real per-GW results for every fake player, keyed to build a
    # deterministic, checkable evaluation.
    histories = {}
    for i in range(1, 17):
        histories[str(i)] = {
            "history": [{"round": 1, "minutes": 90, "total_points": 5}],
            "history_past": [],
        }
    _write_snapshot(tmp_path, "fpl_element_history", "2026_27", 1, {"player_histories": histories})

    class _FakeEvalClient(_FakeManagerFplClient):
        def fetch_manager_picks(self, manager_id: int, event_id: int) -> dict[str, Any]:
            # A tiny (not full 15-player) actual squad is fine for this
            # test - evaluate_squad_points sums whatever picks it's given.
            return {
                "active_chip": None,
                "picks": [
                    {
                        "element": 1, "position": 1, "multiplier": 1,
                        "is_captain": False, "is_vice_captain": False, "element_type": 1,
                    },
                    {
                        "element": 8, "position": 2, "multiplier": 2,
                        "is_captain": True, "is_vice_captain": False, "element_type": 3,
                    },
                ],
            }

    monkeypatch.setattr("fpl_engine.data.fpl_client.FplClient", _FakeEvalClient)

    result = runner.invoke(
        app, ["manager", "evaluate", "--manager-id", "331434", "--gameweek", "1"]
    )

    assert result.exit_code == 0
    assert "Actual submitted squad: 15 points" in result.stdout  # 5*1 + 5*2
    assert "Baseline model squad:" in result.stdout
    assert "automatic substitutions are not modeled" in result.stdout


def test_manager_evaluate_fails_clearly_without_bootstrap_snapshot(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))

    result = runner.invoke(
        app, ["manager", "evaluate", "--manager-id", "331434", "--gameweek", "1"]
    )

    assert result.exit_code == 1
    assert "fpl ingest --gameweek 1" in result.stdout


def test_manager_evaluate_fails_clearly_without_history_snapshot(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPL_DATA_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "fpl_bootstrap", "2026_27", 1, _FAKE_BOOTSTRAP)

    result = runner.invoke(
        app, ["manager", "evaluate", "--manager-id", "331434", "--gameweek", "1"]
    )

    assert result.exit_code == 1
    assert "fpl ingest-history --gameweek 1" in result.stdout
