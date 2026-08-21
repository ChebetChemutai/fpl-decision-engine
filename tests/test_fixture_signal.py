from fpl_engine.baseline.fixture_signal import (
    NEUTRAL_DIFFICULTY,
    fixture_score_multiplier,
    team_difficulties_for_gameweek,
)
from fpl_engine.domain.models import Fixture


def _fixture(
    fid: int,
    event: int | None,
    team_h: int,
    team_a: int,
    team_h_difficulty: int | None = None,
    team_a_difficulty: int | None = None,
) -> Fixture:
    return Fixture(
        id=fid,
        event=event,
        team_h=team_h,
        team_a=team_a,
        team_h_difficulty=team_h_difficulty,
        team_a_difficulty=team_a_difficulty,
    )


def test_home_team_gets_its_own_difficulty_not_the_opponents() -> None:
    """The exact failure mode the spec calls out: using the wrong side's
    difficulty rating. Home team (1) has an easy match (2); away team (7)
    has a hard one (4) — same fixture, different numbers.
    """
    fixtures = [_fixture(1, event=1, team_h=1, team_a=7, team_h_difficulty=2, team_a_difficulty=4)]

    home_team_difficulties = team_difficulties_for_gameweek(fixtures, team_id=1, gameweek=1)
    away_team_difficulties = team_difficulties_for_gameweek(fixtures, team_id=7, gameweek=1)

    assert home_team_difficulties == [2]
    assert away_team_difficulties == [4]


def test_team_not_playing_that_gameweek_gets_no_difficulty() -> None:
    fixtures = [_fixture(1, event=1, team_h=1, team_a=7, team_h_difficulty=3, team_a_difficulty=3)]

    result = team_difficulties_for_gameweek(fixtures, team_id=99, gameweek=1)

    assert result == []


def test_wrong_gameweek_is_excluded() -> None:
    fixtures = [_fixture(1, event=2, team_h=1, team_a=7, team_h_difficulty=1, team_a_difficulty=1)]

    result = team_difficulties_for_gameweek(fixtures, team_id=1, gameweek=1)

    assert result == []


def test_postponed_fixture_with_no_event_is_excluded() -> None:
    """A postponed fixture with no rescheduled date yet has event=None in
    the existing Fixture model — must not match any specific gameweek.
    """
    fixtures = [
        _fixture(1, event=None, team_h=1, team_a=7, team_h_difficulty=3, team_a_difficulty=3)
    ]

    result = team_difficulties_for_gameweek(fixtures, team_id=1, gameweek=1)

    assert result == []


def test_double_gameweek_returns_both_difficulties() -> None:
    fixtures = [
        _fixture(1, event=1, team_h=1, team_a=7, team_h_difficulty=2, team_a_difficulty=4),
        _fixture(2, event=1, team_h=9, team_a=1, team_h_difficulty=3, team_a_difficulty=5),
    ]

    result = team_difficulties_for_gameweek(fixtures, team_id=1, gameweek=1)

    assert result == [2, 5]  # home diff from fixture 1, away diff from fixture 2


def test_missing_difficulty_rating_defaults_to_neutral_not_dropped() -> None:
    fixtures = [
        _fixture(1, event=1, team_h=1, team_a=7, team_h_difficulty=None, team_a_difficulty=3)
    ]

    result = team_difficulties_for_gameweek(fixtures, team_id=1, gameweek=1)

    assert result == [NEUTRAL_DIFFICULTY]


def test_blank_gameweek_multiplier_is_zero() -> None:
    assert fixture_score_multiplier([]) == 0.0


def test_neutral_difficulty_multiplier_is_one() -> None:
    assert fixture_score_multiplier([3]) == 1.0


def test_easy_fixture_multiplier_above_one() -> None:
    assert fixture_score_multiplier([1]) > 1.0


def test_hard_fixture_multiplier_below_one() -> None:
    assert fixture_score_multiplier([5]) < 1.0


def test_double_gameweek_multipliers_sum_not_average() -> None:
    single_neutral = fixture_score_multiplier([3])
    double_neutral = fixture_score_multiplier([3, 3])

    assert double_neutral == single_neutral * 2
