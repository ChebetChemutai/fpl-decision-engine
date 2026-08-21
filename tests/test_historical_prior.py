from fpl_engine.baseline.historical_prior import (
    HISTORICAL_PRIOR_WEIGHT,
    MIN_MINUTES_FOR_RELIABLE_RATE,
    historical_prior_score,
    points_per_90,
)
from fpl_engine.domain.models import SeasonSummary


def _season(name: str, total_points: int, minutes: int, starts: int = 20) -> SeasonSummary:
    return SeasonSummary(
        season_name=name, total_points=total_points, minutes=minutes, starts=starts
    )


def test_points_per_90_computes_correct_rate() -> None:
    season = _season("2025/26", total_points=180, minutes=1800)  # exactly 20 full matches

    assert points_per_90(season) == 9.0


def test_points_per_90_returns_none_below_reliability_threshold() -> None:
    season = _season("2025/26", total_points=20, minutes=MIN_MINUTES_FOR_RELIABLE_RATE - 1)

    assert points_per_90(season) is None


def test_points_per_90_at_exact_threshold_is_reliable() -> None:
    season = _season("2025/26", total_points=45, minutes=MIN_MINUTES_FOR_RELIABLE_RATE)

    assert points_per_90(season) is not None


def test_historical_prior_uses_most_recent_reliable_season() -> None:
    seasons = [
        _season("2023/24", total_points=90, minutes=1800),  # rate 4.5
        _season("2024/25", total_points=180, minutes=1800),  # rate 9.0 - most recent, should win
    ]

    prior = historical_prior_score(seasons)

    assert prior == round(9.0 * HISTORICAL_PRIOR_WEIGHT, 4)


def test_historical_prior_skips_unreliable_recent_season_for_older_reliable_one() -> None:
    seasons = [
        _season("2023/24", total_points=180, minutes=1800),  # rate 9.0, reliable
        _season("2024/25", total_points=5, minutes=50),  # barely played, unreliable
    ]

    prior = historical_prior_score(seasons)

    assert prior == round(9.0 * HISTORICAL_PRIOR_WEIGHT, 4)


def test_no_seasons_returns_none_not_zero() -> None:
    """A genuinely brand-new player (no FPL history at all) must be
    distinguishable from a player whose historical rate was actually 0 -
    the same true-zero-vs-missing distinction the temporal engine enforces.
    """
    assert historical_prior_score([]) is None


def test_all_seasons_unreliable_returns_none() -> None:
    seasons = [_season("2024/25", total_points=2, minutes=30)]

    assert historical_prior_score(seasons) is None


def test_prior_is_weighted_down_from_raw_rate() -> None:
    """The prior must never equal the raw historical rate at full strength -
    that would be treating a stale season as equivalent to a live signal."""
    seasons = [_season("2025/26", total_points=180, minutes=1800)]  # raw rate 9.0

    prior = historical_prior_score(seasons)

    assert prior is not None
    assert prior < 9.0
    assert HISTORICAL_PRIOR_WEIGHT < 1.0  # sanity: the weight itself is a real discount
