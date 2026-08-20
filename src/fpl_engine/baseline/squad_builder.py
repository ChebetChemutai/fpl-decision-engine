"""Assembles a full `Squad` (15-man, XI, bench, captain, vice) from a raw
player pool. This is the Phase 1.5 entry point everything else calls.
"""

from __future__ import annotations

from fpl_engine.baseline.optimizer import optimize_squad, optimize_starting_xi
from fpl_engine.baseline.scoring import score_players
from fpl_engine.domain.models import Player, Position, Squad
from fpl_engine.domain.rules import BUDGET_M, validate_squad, validate_starting_xi


def build_squad(players: list[Player], budget: float = BUDGET_M) -> Squad:
    """Run scoring -> squad optimization -> XI optimization -> captaincy.

    Raises AssertionError if the result fails rules validation — that should
    never happen given a correct optimizer, but we check anyway (architecture
    Sec 14 testing strategy: an illegal recommendation is worse than a
    suboptimal one).
    """
    scored = score_players(players)
    scores_by_id = {sp.player.id: sp.score for sp in scored}

    squad_15 = optimize_squad(scored, budget=budget)
    squad_violations = validate_squad(squad_15)
    assert not squad_violations, f"optimizer produced an illegal squad: {squad_violations}"

    starting_xi = optimize_starting_xi(squad_15, scores_by_id)
    xi_violations = validate_starting_xi(starting_xi)
    assert not xi_violations, f"optimizer produced an illegal starting XI: {xi_violations}"

    xi_ids = {p.id for p in starting_xi}
    bench = [p for p in squad_15 if p.id not in xi_ids]
    # Bench convention: outfield players ordered by score desc, backup GK last.
    bench_outfield = sorted(
        (p for p in bench if p.position != Position.GKP),
        key=lambda p: scores_by_id[p.id],
        reverse=True,
    )
    bench_gk = [p for p in bench if p.position == Position.GKP]
    bench_ordered = bench_outfield + bench_gk

    xi_by_score = sorted(starting_xi, key=lambda p: scores_by_id[p.id], reverse=True)
    captain, vice_captain = xi_by_score[0], xi_by_score[1]

    return Squad(
        all_15=squad_15,
        starting_xi=starting_xi,
        bench=bench_ordered,
        captain=captain,
        vice_captain=vice_captain,
    )
