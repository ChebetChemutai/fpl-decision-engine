"""Fixture difficulty signal (integration spec Sec 4).

Semantics verified against a real live fixture before writing any of this
(not assumed): `Fixture.team_h_difficulty` is how hard the match is FOR
THE HOME TEAM; `team_a_difficulty` is how hard it is FOR THE AWAY TEAM.
Confirmed via a real GW1 Arsenal-at-home fixture, where Arsenal (strong,
home advantage) had team_h_difficulty=2 (easy for them) while their
opponent had team_a_difficulty=4 (hard for the visitor). Getting this
backwards — using the home team's difficulty to score the away player, or
vice versa — was explicitly the failure mode to avoid, so this is checked
with a dedicated home-vs-away test, not just eyeballed.

Postponed fixtures with no new date yet have `event=None` in the existing
Fixture model (see domain/models.py) — filtering by exact gameweek number
naturally excludes them without needing a separate "postponed" flag. A
fixture rescheduled to a different gameweek simply appears under that
gameweek's event number instead, which is the correct behavior with no
extra code.
"""

from __future__ import annotations

from fpl_engine.domain.models import Fixture

NEUTRAL_DIFFICULTY = 3

# FPL's difficulty scale is 1 (easiest) to 5 (hardest), centered on 3
# (neutral -> multiplier 1.0). Deliberately modest step size (~7-8% per
# difficulty level, capped at +-15% at the extremes): fixture difficulty
# is a coarse proxy for match outcome, not a precise predictor, and it
# should nudge the ep_next-based score rather than dominate it.
DIFFICULTY_SCORE_MULTIPLIER: dict[int, float] = {
    1: 1.15,
    2: 1.08,
    3: 1.00,
    4: 0.92,
    5: 0.85,
}


def team_difficulties_for_gameweek(
    fixtures: list[Fixture], team_id: int, gameweek: int
) -> list[int]:
    """Difficulty rating(s) for `team_id`'s fixture(s) in `gameweek`, from
    that team's own perspective (never the opponent's).

    Returns: [] for a blank gameweek (team has no fixture), one value for
    a normal gameweek, two or more for a double gameweek. A fixture with
    a null difficulty rating (rare, but the field is Optional) is treated
    as neutral (3) rather than dropped — an unrated match still happened
    and the player can still score in it.
    """
    difficulties: list[int] = []
    for fixture in fixtures:
        if fixture.event != gameweek:
            continue
        if fixture.team_h == team_id:
            difficulty = fixture.team_h_difficulty
            difficulties.append(difficulty if difficulty is not None else NEUTRAL_DIFFICULTY)
        elif fixture.team_a == team_id:
            difficulty = fixture.team_a_difficulty
            difficulties.append(difficulty if difficulty is not None else NEUTRAL_DIFFICULTY)
    return difficulties


def fixture_score_multiplier(difficulties: list[int]) -> float:
    """Convert difficulty rating(s) into a scoring multiplier.

    Blank gameweek (no fixtures) -> 0.0: the player literally cannot
    score. Double gameweek (2+ fixtures) -> multipliers SUM rather than
    average, since expected points are roughly additive across two
    separate matches — a double gameweek is (correctly) worth more than
    either match alone, not the same as a single average-difficulty match.
    """
    if not difficulties:
        return 0.0
    return round(sum(DIFFICULTY_SCORE_MULTIPLIER.get(d, 1.0) for d in difficulties), 4)
