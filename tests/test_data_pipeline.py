"""SYNTHETIC test data throughout this file — a deterministic, hand-built
multi-player/multi-gameweek history structure shaped like real ingested
data, used to prove the pipeline's plumbing and leakage guard work
correctly. This is NOT a real historical evaluation; see
docs/checkpoint-review-gw1.md and the `fpl backtest` CLI command's
explicit REAL/SYNTHETIC labeling for that distinction.
"""

from fpl_engine.domain.models import Position
from fpl_engine.features.temporal import GameweekPerformance
from fpl_engine.models.backtest import run_backtest
from fpl_engine.models.baselines import FormWeightedBaseline, PositionAverageBaseline
from fpl_engine.models.data_pipeline import build_backtest_cases, build_training_points_by_position


def _perf(gw: int, points: int) -> GameweekPerformance:
    return GameweekPerformance(gameweek=gw, total_points=points, minutes=90)


def test_build_backtest_cases_skips_players_with_no_result_for_target_gw() -> None:
    """The realistic state as of today: GW1 hasn't been ingested
    post-match, so every player's history is []. No case should be
    fabricated for them.
    """
    histories = {1: [], 2: []}
    positions = {1: Position.MID, 2: Position.FWD}

    cases = build_backtest_cases(histories, positions, target_gameweek=1)

    assert cases == []


def test_build_backtest_cases_includes_only_players_with_a_real_result() -> None:
    histories = {
        1: [_perf(1, 6)],  # has a GW1 result
        2: [],  # doesn't yet
    }
    positions = {1: Position.MID, 2: Position.FWD}

    cases = build_backtest_cases(histories, positions, target_gameweek=1)

    assert len(cases) == 1
    assert cases[0].player_id == 1
    assert cases[0].actual_points == 6


def test_build_backtest_cases_skips_players_missing_from_the_position_map() -> None:
    """A player_id with history but no known position (e.g. a bootstrap/
    history snapshot mismatch) must be skipped, not crash or guess.
    """
    histories = {1: [_perf(1, 6)]}
    positions: dict[int, Position] = {}  # player 1 not in the position map

    cases = build_backtest_cases(histories, positions, target_gameweek=1)

    assert cases == []


def test_end_to_end_leakage_guard_holds_through_the_real_ingestion_shaped_path() -> None:
    """The centerpiece test for this module: builds cases the way
    `fpl backtest` actually would (multi-player, multi-gameweek,
    unfiltered history handed straight to BacktestCase), then proves a
    wildly-out-of-range future result never influences the prediction for
    an earlier gameweek — the same guarantee test_temporal.py proves for
    a single player, now proven again through the full real-shaped
    ingestion -> backtest-case -> compute_features path.
    """
    histories = {
        1: [
            _perf(1, 2),
            _perf(2, 3),
            _perf(3, 4),  # this is the target GW's actual result
            _perf(4, 9999),  # future relative to GW3 - must never leak in
        ],
    }
    positions = {1: Position.MID}

    cases = build_backtest_cases(histories, positions, target_gameweek=3)
    assert len(cases) == 1
    assert cases[0].actual_points == 4  # GW3's real result, not the GW4 outlier

    fallback = PositionAverageBaseline.fit({Position.MID: [3]})
    model = FormWeightedBaseline(fallback)
    result = run_backtest(model, cases)

    # form_ewma for GW3 should be computed from GW1-2 only (2, 3) - a
    # small, sane error, not one blown up by the planted 9999.
    assert result.mae < 5.0


def test_build_training_points_excludes_the_target_and_future_gameweeks() -> None:
    histories = {
        1: [_perf(1, 5), _perf(2, 7), _perf(3, 9999)],  # GW3 must be excluded if before_gw=3
    }
    positions = {1: Position.MID}

    training = build_training_points_by_position(histories, positions, before_gameweek=3)

    assert training[Position.MID] == [5, 7]
    assert 9999 not in training[Position.MID]


def test_build_training_points_pools_multiple_players_by_position() -> None:
    histories = {
        1: [_perf(1, 5)],
        2: [_perf(1, 7)],
        3: [_perf(1, 2)],  # different position, must not mix in
    }
    positions = {1: Position.MID, 2: Position.MID, 3: Position.FWD}

    training = build_training_points_by_position(histories, positions, before_gameweek=2)

    assert sorted(training[Position.MID]) == [5, 7]
    assert training[Position.FWD] == [2]


def test_full_pipeline_produces_a_measurable_backtest_result() -> None:
    """Wires build_training_points_by_position -> PositionAverageBaseline
    -> build_backtest_cases -> run_backtest end to end, the same sequence
    `fpl backtest` runs against real (currently empty) data.
    """
    histories = {
        1: [_perf(1, 4), _perf(2, 6)],
        2: [_perf(1, 3), _perf(2, 5)],
    }
    positions = {1: Position.MID, 2: Position.MID}

    training = build_training_points_by_position(histories, positions, before_gameweek=2)
    model = PositionAverageBaseline.fit(training)
    cases = build_backtest_cases(histories, positions, target_gameweek=2)

    result = run_backtest(model, cases)

    assert result.n == 2
    assert result.mae >= 0.0
