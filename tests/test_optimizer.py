import pytest

from fpl_engine.baseline.optimizer import InfeasibleSquadError, optimize_squad
from fpl_engine.baseline.scoring import score_players
from fpl_engine.domain.rules import BUDGET_M, MAX_PER_CLUB, validate_squad

from .fixtures.synthetic_players import synthetic_player_pool


def test_optimizer_produces_a_fully_legal_squad() -> None:
    scored = score_players(synthetic_player_pool())

    squad = optimize_squad(scored, budget=BUDGET_M)

    assert validate_squad(squad) == []


def test_optimizer_respects_budget() -> None:
    scored = score_players(synthetic_player_pool())

    squad = optimize_squad(scored, budget=BUDGET_M)

    assert sum(p.price for p in squad) <= BUDGET_M


def test_optimizer_excludes_injured_players() -> None:
    scored = score_players(synthetic_player_pool())

    squad = optimize_squad(scored, budget=BUDGET_M)

    assert not any(p.web_name == "FWD-Injured-Premium" for p in squad)


def test_optimizer_never_exceeds_max_per_club() -> None:
    scored = score_players(synthetic_player_pool())

    squad = optimize_squad(scored, budget=BUDGET_M)

    counts: dict[int, int] = {}
    for p in squad:
        counts[p.team_id] = counts.get(p.team_id, 0) + 1
    assert all(count <= MAX_PER_CLUB for count in counts.values())


def test_optimizer_raises_when_infeasible() -> None:
    scored = score_players(synthetic_player_pool())

    with pytest.raises(InfeasibleSquadError):
        optimize_squad(scored, budget=1.0)  # impossibly small budget
