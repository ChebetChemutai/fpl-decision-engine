import pytest

from fpl_engine.domain.models import Position
from fpl_engine.features.temporal import GameweekPerformance
from fpl_engine.models.backtest import BacktestCase, run_backtest
from fpl_engine.models.baselines import FormWeightedBaseline, PositionAverageBaseline


def _perf(gw: int, points: int) -> GameweekPerformance:
    return GameweekPerformance(gameweek=gw, total_points=points, minutes=90)


def test_run_backtest_rejects_empty_case_list() -> None:
    model = PositionAverageBaseline.fit({Position.MID: [5]})

    with pytest.raises(ValueError, match="empty"):
        run_backtest(model, [])


def test_perfect_predictions_yield_zero_error() -> None:
    model = PositionAverageBaseline.fit({Position.FWD: [5, 5, 5]})
    cases = [
        BacktestCase(
            player_id=1,
            position=Position.FWD,
            target_gameweek=1,
            history=[],
            actual_points=5,  # matches the fitted average exactly
        )
    ]

    result = run_backtest(model, cases)

    assert result.mae == 0.0
    assert result.rmse == 0.0
    assert result.n == 1


def test_backtest_recomputes_features_and_respects_the_leakage_guard() -> None:
    """A case whose history includes a future gameweek (relative to that
    case's own target_gameweek) must not have that future data influence
    the prediction — proves the harness re-derives features itself rather
    than trusting pre-computed ones.
    """
    fallback = PositionAverageBaseline.fit({Position.MID: [0]})
    model = FormWeightedBaseline(fallback)

    case = BacktestCase(
        player_id=1,
        position=Position.MID,
        target_gameweek=3,
        history=[_perf(1, 2), _perf(2, 2), _perf(3, 9999)],  # GW3 == target, must be excluded
        actual_points=2,
    )

    result = run_backtest(model, [case])

    # form_ewma computed only from GW1-2 (both = 2) should be ~2, giving a
    # small error against actual=2 - NOT the huge error a leaked 9999 would
    # cause.
    assert result.mae < 1.0


def test_form_weighted_baseline_beats_position_average_when_form_is_predictive() -> None:
    """The Sec 12 gate in practice: a more sophisticated model only earns
    its place if it measurably beats the naive baseline on held-out data.

    Note on scenario design: EWMA smooths toward recent values, it does
    NOT extrapolate a trend beyond them — a first draft of this test used
    a still-climbing/falling trend as the "actual" value, which EWMA can
    never predict by construction (it's a weighted average, not a
    forecaster), and the two baselines tied. Fixed to a scenario where the
    next result matches what recent matches already settled toward, which
    is what EWMA-style form actually captures.
    """
    training_points = {Position.MID: [4, 4, 4, 4]}  # flat prior, avg 4
    position_avg_model = PositionAverageBaseline.fit(training_points)
    form_model = FormWeightedBaseline(position_avg_model)

    cases = [
        BacktestCase(
            player_id=1,
            position=Position.MID,
            target_gameweek=5,
            history=[_perf(1, 0), _perf(2, 0), _perf(3, 8), _perf(4, 9)],
            actual_points=9,  # settled into a new, higher level; holds
        ),
        BacktestCase(
            player_id=2,
            position=Position.MID,
            target_gameweek=5,
            history=[_perf(1, 9), _perf(2, 8), _perf(3, 0), _perf(4, 0)],
            actual_points=0,  # settled into a new, lower level; holds
        ),
    ]

    position_avg_result = run_backtest(position_avg_model, cases)
    form_result = run_backtest(form_model, cases)

    assert form_result.mae < position_avg_result.mae
