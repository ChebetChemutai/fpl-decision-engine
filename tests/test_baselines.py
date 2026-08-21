from fpl_engine.domain.models import Position
from fpl_engine.features.contract import DataCompleteness, FeatureContractV4
from fpl_engine.models.baselines import FormWeightedBaseline, PositionAverageBaseline


def _features(form_ewma: float | None) -> FeatureContractV4:
    completeness = DataCompleteness.FULL if form_ewma is not None else DataCompleteness.COLD_START
    return FeatureContractV4(
        player_id=1,
        target_gameweek=5,
        data_completeness=completeness,
        matches_played_before=5 if form_ewma is not None else 0,
        minutes_avg_3=None,
        minutes_avg_5=None,
        minutes_season_to_date=None,
        points_avg_3=None,
        points_avg_5=None,
        points_season_to_date=None,
        form_ewma=form_ewma,
    )


def test_position_average_fits_separate_averages_per_position() -> None:
    training = {
        Position.FWD: [8, 10, 6],  # avg 8
        Position.DEF: [2, 4],  # avg 3
    }

    model = PositionAverageBaseline.fit(training)

    assert model.predict(_features(None), Position.FWD) == 8.0
    assert model.predict(_features(None), Position.DEF) == 3.0


def test_position_average_ignores_features_entirely() -> None:
    model = PositionAverageBaseline.fit({Position.MID: [5, 5, 5]})

    # Same prediction regardless of form — this model is intentionally naive.
    assert model.predict(_features(99.0), Position.MID) == 5.0
    assert model.predict(_features(None), Position.MID) == 5.0


def test_position_average_falls_back_to_overall_average_for_unseen_position() -> None:
    model = PositionAverageBaseline.fit({Position.FWD: [10, 10], Position.DEF: [2, 2]})

    # MID never appeared in training data.
    assert model.predict(_features(None), Position.MID) == 6.0  # overall avg of [10,10,2,2]


def test_form_weighted_uses_ewma_when_available() -> None:
    fallback = PositionAverageBaseline.fit({Position.MID: [1, 1]})
    model = FormWeightedBaseline(fallback)

    assert model.predict(_features(7.5), Position.MID) == 7.5


def test_form_weighted_falls_back_to_position_average_when_cold_start() -> None:
    fallback = PositionAverageBaseline.fit({Position.MID: [4, 4]})
    model = FormWeightedBaseline(fallback)

    assert model.predict(_features(None), Position.MID) == 4.0
