"""Constrained squad and starting-XI optimization (Phase 1.5 baseline).

Uses an actual mixed-integer linear program (PuLP/CBC) rather than "sort by
score and take the top N" — sorting alone cannot respect the budget, club,
and position constraints simultaneously (architecture.md Sec 16, "never
simply select the highest predicted players").
"""

from __future__ import annotations

import pulp

from fpl_engine.domain.models import Player, ScoredPlayer
from fpl_engine.domain.rules import BUDGET_M, MAX_PER_CLUB, POSITION_RULES


class InfeasibleSquadError(RuntimeError):
    """Raised when no legal 15-man squad exists under the given constraints
    and player pool (e.g. too few affordable players at a position)."""


class InfeasibleXIError(RuntimeError):
    """Raised when no legal starting XI can be formed from a given squad."""


def optimize_squad(scored_players: list[ScoredPlayer], budget: float = BUDGET_M) -> list[Player]:
    """Select the score-maximizing legal 15-man squad within budget.

    Excludes zero-score (effectively unavailable) players from consideration
    entirely, so the optimizer never wastes a squad slot on someone who
    can't play.
    """
    candidates = [sp for sp in scored_players if sp.score > 0.0]
    if not candidates:
        raise InfeasibleSquadError("no available (score > 0) players to select from")

    problem = pulp.LpProblem("fpl_squad_selection", pulp.LpMaximize)
    choice_vars = {
        sp.player.id: pulp.LpVariable(f"pick_{sp.player.id}", cat="Binary") for sp in candidates
    }

    problem += pulp.lpSum(choice_vars[sp.player.id] * sp.score for sp in candidates)

    problem += pulp.lpSum(choice_vars[sp.player.id] for sp in candidates) == sum(
        rule.squad_count for rule in POSITION_RULES.values()
    )
    problem += (
        pulp.lpSum(choice_vars[sp.player.id] * sp.player.price for sp in candidates) <= budget
    )

    for position, rule in POSITION_RULES.items():
        problem += (
            pulp.lpSum(
                choice_vars[sp.player.id] for sp in candidates if sp.player.position == position
            )
            == rule.squad_count
        )

    club_ids = {sp.player.team_id for sp in candidates}
    for team_id in club_ids:
        problem += (
            pulp.lpSum(
                choice_vars[sp.player.id] for sp in candidates if sp.player.team_id == team_id
            )
            <= MAX_PER_CLUB
        )

    status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise InfeasibleSquadError(
            f"solver returned status={pulp.LpStatus[status]!r} — "
            "likely too few affordable candidates at some position"
        )

    selected_ids = {
        sp.player.id for sp in candidates if choice_vars[sp.player.id].value() == 1.0
    }
    return [sp.player for sp in candidates if sp.player.id in selected_ids]


def optimize_starting_xi(squad: list[Player], scores: dict[int, float]) -> list[Player]:
    """Select the score-maximizing legal starting XI from an already-legal squad."""
    problem = pulp.LpProblem("fpl_xi_selection", pulp.LpMaximize)
    start_vars = {p.id: pulp.LpVariable(f"start_{p.id}", cat="Binary") for p in squad}

    problem += pulp.lpSum(start_vars[p.id] * scores[p.id] for p in squad)
    problem += pulp.lpSum(start_vars.values()) == 11

    for position, rule in POSITION_RULES.items():
        position_vars = [start_vars[p.id] for p in squad if p.position == position]
        if position.name == "GKP":
            problem += pulp.lpSum(position_vars) == 1
        else:
            problem += pulp.lpSum(position_vars) >= rule.min_play
            problem += pulp.lpSum(position_vars) <= rule.max_play

    status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise InfeasibleXIError(f"solver returned status={pulp.LpStatus[status]!r}")

    return [p for p in squad if start_vars[p.id].value() == 1.0]
