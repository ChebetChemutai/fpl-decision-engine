"""Validates scoring_rules.calculate_points against REAL GW1 results.

Data below is real — captured via a live fetch of
https://fantasy.premierleague.com/api/bootstrap-static/ on 2026-08-25,
after GW1 had actually been played (kickoffs 2026-08-21 through
2026-08-24). This is genuinely different from every other test fixture
in this repo, which is either real-but-pre-match (ep_next, prices) or
explicitly synthetic. These are real match outcomes with a real,
independently-known correct answer (FPL's own total_points) — the
strongest validation available for this codebase's scoring logic.
"""

from fpl_engine.domain.models import Position
from fpl_engine.domain.scoring_rules import MatchStats, calculate_points
from fpl_engine.features.temporal import GameweekPerformance
from fpl_engine.models.match_stats_bridge import to_match_stats

# Real GW1 2026/27 results (id, web_name, element_type -> Position mapping
# done in the test itself). Field values copied verbatim from the live
# bootstrap-static response.
_REAL_GW1_RESULTS: list[tuple[str, Position, dict[str, int], int]] = [
    # (name, position, real stats, real total_points)
    (
        "Gabriel",
        Position.DEF,
        dict(
            minutes=90, goals_scored=0, assists=0, goals_conceded=0, own_goals=0,
            penalties_saved=0, penalties_missed=0, yellow_cards=1, red_cards=0,
            saves=0, defensive_contribution=4, bonus=0,
        ),
        5,
    ),
    (
        "White",
        Position.DEF,
        dict(
            minutes=90, goals_scored=0, assists=1, goals_conceded=0, own_goals=0,
            penalties_saved=0, penalties_missed=0, yellow_cards=0, red_cards=0,
            saves=0, defensive_contribution=5, bonus=2,
        ),
        11,
    ),
    (
        "Saka",
        Position.MID,
        dict(
            minutes=67, goals_scored=1, assists=0, goals_conceded=0, own_goals=0,
            penalties_saved=0, penalties_missed=0, yellow_cards=0, red_cards=0,
            saves=0, defensive_contribution=7, bonus=1,
        ),
        9,
    ),
    (
        "Ødegaard",
        Position.MID,
        dict(
            minutes=75, goals_scored=1, assists=0, goals_conceded=0, own_goals=0,
            penalties_saved=0, penalties_missed=0, yellow_cards=0, red_cards=0,
            saves=0, defensive_contribution=8, bonus=3,
        ),
        11,
    ),
    (
        "Havertz",
        Position.FWD,
        dict(
            minutes=90, goals_scored=1, assists=0, goals_conceded=0, own_goals=0,
            penalties_saved=0, penalties_missed=0, yellow_cards=0, red_cards=0,
            saves=0, defensive_contribution=2, bonus=0,
        ),
        6,
    ),
    (
        "Raya",
        Position.GKP,
        dict(
            minutes=90, goals_scored=0, assists=0, goals_conceded=0, own_goals=0,
            penalties_saved=0, penalties_missed=0, yellow_cards=0, red_cards=0,
            saves=1, defensive_contribution=0, bonus=0,
        ),
        6,
    ),
]


def test_scoring_engine_reproduces_real_gw1_results_exactly() -> None:
    """The centerpiece of this file: our own calculate_points logic,
    given the same raw stats FPL recorded for real, must produce the
    exact same total_points FPL itself awarded. Any mismatch here means
    scoring_rules.py has a real bug, not a hypothetical one.
    """
    for name, position, stats, expected_points in _REAL_GW1_RESULTS:
        match_stats = MatchStats(position=position, **stats)
        computed = calculate_points(match_stats)
        assert computed == expected_points, (
            f"{name} ({position.name}): computed {computed}, "
            f"FPL's real total was {expected_points}. Stats: {stats}"
        )


def test_match_stats_bridge_reproduces_the_same_real_results() -> None:
    """Same validation, but through the actual production path this
    session added: GameweekPerformance (what ingestion produces) ->
    to_match_stats -> calculate_points. Proves the bridge function
    itself is correct, not just calculate_points in isolation.
    """
    for name, position, stats, expected_points in _REAL_GW1_RESULTS:
        performance = GameweekPerformance(
            gameweek=1,
            minutes=stats["minutes"],
            total_points=expected_points,
            goals_scored=stats["goals_scored"],
            assists=stats["assists"],
            goals_conceded=stats["goals_conceded"],
            own_goals=stats["own_goals"],
            penalties_saved=stats["penalties_saved"],
            penalties_missed=stats["penalties_missed"],
            yellow_cards=stats["yellow_cards"],
            red_cards=stats["red_cards"],
            saves=stats["saves"],
            bonus=stats["bonus"],
            defensive_contribution=stats["defensive_contribution"],
        )

        match_stats = to_match_stats(performance, position)
        computed = calculate_points(match_stats)

        assert computed == expected_points, (
            f"{name}: bridge produced {computed}, expected {expected_points}"
        )
