"""Bridges a real ingested GameweekPerformance into scoring_rules.MatchStats
— the prerequisite for Phase 6 component modeling (minutes/goals/assists/
clean-sheets/defensive-contribution/bonus predicted separately, then
converted to points via the same scoring_rules.calculate_points FPL
itself effectively implements).

Also home to the real-data validation this enables: if scoring_rules.py's
point calculation is correct, running a real player's actual GW1 stats
through it must reproduce FPL's own real total_points exactly. See
test_scoring_validation.py for that proof.
"""

from __future__ import annotations

from fpl_engine.domain.models import Position
from fpl_engine.domain.scoring_rules import MatchStats
from fpl_engine.features.temporal import GameweekPerformance


def to_match_stats(performance: GameweekPerformance, position: Position) -> MatchStats:
    """Reconstruct the MatchStats scoring_rules.calculate_points needs
    from a real ingested GameweekPerformance. Pure field mapping — no
    inference, no defaults beyond what GameweekPerformance itself already
    defaults to 0 for missing real data.
    """
    return MatchStats(
        position=position,
        minutes=performance.minutes,
        goals_scored=performance.goals_scored,
        assists=performance.assists,
        goals_conceded=performance.goals_conceded,
        own_goals=performance.own_goals,
        penalties_saved=performance.penalties_saved,
        penalties_missed=performance.penalties_missed,
        yellow_cards=performance.yellow_cards,
        red_cards=performance.red_cards,
        saves=performance.saves,
        defensive_contributions=performance.defensive_contribution,
        bonus=performance.bonus,
    )
