"""GW evaluation: actual submitted squad vs. the baseline model's
reconstructed recommendation, scored against real per-gameweek results.

This does NOT model automatic substitutions (a benched player replacing
a starting XI player who scored 0 minutes) — that needs minutes data
plus substitution-eligibility logic this module doesn't implement yet.
Both the actual and baseline comparison use nominal picks/bench exactly
as selected; treat a close comparison with caution if either squad had
a starter who didn't play.
"""

from __future__ import annotations

from pydantic import BaseModel

from fpl_engine.domain.models import Squad
from fpl_engine.features.temporal import GameweekPerformance


class SquadPick(BaseModel):
    """One player's contribution weight for a single gameweek's scoring.

    multiplier: 0 = benched (no auto-sub modeling), 1 = starts,
    2 = captain, 3 = triple captain.
    """

    player_id: int
    multiplier: int


def evaluate_squad_points(picks: list[SquadPick], points_by_player: dict[int, int]) -> int:
    """Total points for a set of picks against real per-gameweek results.

    A player with no entry in `points_by_player` (no result yet, or an
    unknown id) contributes 0 — the correct default, not an error: FPL
    itself awards 0 points to a player who didn't feature.
    """
    return sum(points_by_player.get(pick.player_id, 0) * pick.multiplier for pick in picks)


def points_by_player_from_element_history(
    player_histories: dict[int, list[GameweekPerformance]], gameweek: int
) -> dict[int, int]:
    """Real per-gameweek points, keyed by player id, for one gameweek —
    built from ingested element-history data (not bootstrap-static's
    season-cumulative total_points, which is only correct for GW1 and
    silently wrong for any later gameweek).
    """
    result: dict[int, int] = {}
    for player_id, history in player_histories.items():
        match = next((h for h in history if h.gameweek == gameweek), None)
        if match is not None:
            result[player_id] = match.total_points
    return result


def squad_to_picks(squad: Squad) -> list[SquadPick]:
    """Convert a baseline Squad (starting_xi/bench/captain) into the same
    SquadPick shape a real manager's picks come in, so both sides of a
    comparison run through the identical scoring function.
    """
    picks: list[SquadPick] = []
    for player in squad.starting_xi:
        multiplier = 2 if player.id == squad.captain.id else 1
        picks.append(SquadPick(player_id=player.id, multiplier=multiplier))
    for player in squad.bench:
        picks.append(SquadPick(player_id=player.id, multiplier=0))
    return picks
