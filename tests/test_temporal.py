from fpl_engine.features.contract import DataCompleteness
from fpl_engine.features.temporal import GameweekPerformance, compute_features


def _perf(gameweek: int, points: int, minutes: int = 90) -> GameweekPerformance:
    return GameweekPerformance(gameweek=gameweek, total_points=points, minutes=minutes)


def test_future_gameweeks_never_leak_into_features() -> None:
    """THE core test of this module. If this ever fails, stop and fix the
    feature engine before touching anything else - a model trained on
    leaked future data will look great in backtests and be useless live.
    """
    history = [
        _perf(1, points=2),
        _perf(2, points=3),
        _perf(3, points=4),
        # A wildly-out-of-range future score that would obviously skew any
        # rolling average if it leaked in. If target_gameweek=4 and this
        # value influences the output, the guard has failed.
        _perf(4, points=9999),
        _perf(5, points=9999),
    ]

    features = compute_features(player_id=1, target_gameweek=4, history=history)

    assert features.matches_played_before == 3
    assert features.points_avg_3 == 3.0  # avg of GW1-3 only: (2+3+4)/3
    assert features.points_season_to_date == 3.0
    assert 9999 not in {features.points_avg_3, features.points_season_to_date}


def test_leakage_guard_holds_even_when_history_is_unsorted() -> None:
    """The guard must not rely on the caller passing sorted, pre-filtered
    input — real historical data on disk is naturally out of order across
    files. This deliberately shuffles gameweeks including a future one.
    """
    history = [
        _perf(5, points=9999),  # future, must be excluded
        _perf(2, points=3),
        _perf(1, points=2),
        _perf(3, points=4),
    ]

    features = compute_features(player_id=1, target_gameweek=4, history=history)

    assert features.matches_played_before == 3
    assert features.points_avg_3 == 3.0


def test_zero_history_is_cold_start_not_zero_filled() -> None:
    features = compute_features(player_id=1, target_gameweek=1, history=[])

    assert features.data_completeness == DataCompleteness.COLD_START
    assert features.matches_played_before == 0
    # None, not 0.0 - a true zero and "no data" must stay distinguishable
    # (architecture.md Sec 10).
    assert features.points_avg_3 is None
    assert features.minutes_avg_3 is None
    assert features.form_ewma is None


def test_partial_history_below_full_threshold() -> None:
    history = [_perf(1, points=5), _perf(2, points=7)]

    features = compute_features(player_id=1, target_gameweek=3, history=history)

    assert features.data_completeness == DataCompleteness.PARTIAL
    assert features.matches_played_before == 2


def test_full_history_at_or_above_threshold() -> None:
    history = [_perf(gw, points=5) for gw in range(1, 6)]  # 5 matches

    features = compute_features(player_id=1, target_gameweek=6, history=history)

    assert features.data_completeness == DataCompleteness.FULL
    assert features.matches_played_before == 5


def test_rolling_averages_use_the_correct_window() -> None:
    # 6 eligible matches with distinct point values so windows are
    # distinguishable from each other and from season-to-date.
    history = [_perf(gw, points=gw) for gw in range(1, 7)]  # points = gw number

    features = compute_features(player_id=1, target_gameweek=7, history=history)

    assert features.points_avg_3 == 5.0  # avg of GW4,5,6 = (4+5+6)/3
    assert features.points_avg_5 == 4.0  # avg of GW2-6 = (2+3+4+5+6)/5
    assert features.points_season_to_date == 3.5  # avg of GW1-6


def test_true_zero_is_preserved_not_treated_as_missing() -> None:
    """A player who actually scored 0 in every eligible match is different
    from a player with no data at all - both must be representable and
    distinguishable.
    """
    history = [_perf(1, points=0), _perf(2, points=0)]

    features = compute_features(player_id=1, target_gameweek=3, history=history)

    assert features.data_completeness == DataCompleteness.PARTIAL  # has data
    assert features.points_avg_3 == 0.0  # a real zero, not None


def test_form_ewma_weights_recent_matches_more_heavily() -> None:
    improving = [_perf(1, points=0), _perf(2, points=0), _perf(3, points=10)]
    declining = [_perf(1, points=10), _perf(2, points=0), _perf(3, points=0)]

    improving_features = compute_features(player_id=1, target_gameweek=4, history=improving)
    declining_features = compute_features(player_id=2, target_gameweek=4, history=declining)

    assert improving_features.form_ewma is not None
    assert declining_features.form_ewma is not None
    assert improving_features.form_ewma > declining_features.form_ewma


def test_gameweek_equal_to_target_is_excluded_not_just_greater_than() -> None:
    """Off-by-one guard: a record for the target gameweek itself is future
    information relative to that gameweek's deadline and must be excluded,
    not just gameweeks strictly greater than the target.
    """
    history = [_perf(1, points=5), _perf(2, points=999)]  # GW2 == target

    features = compute_features(player_id=1, target_gameweek=2, history=history)

    assert features.matches_played_before == 1
    assert features.points_avg_3 == 5.0
