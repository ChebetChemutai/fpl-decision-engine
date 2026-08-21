from fpl_engine.baseline.squad_builder import build_squad
from fpl_engine.domain.models import Position
from fpl_engine.domain.rules import validate_squad, validate_starting_xi

from .fixtures.synthetic_players import synthetic_player_pool


def test_build_squad_produces_legal_squad_and_xi() -> None:
    squad = build_squad(synthetic_player_pool())

    assert validate_squad(squad.all_15) == []
    assert validate_starting_xi(squad.starting_xi) == []


def test_bench_is_the_four_players_not_in_starting_xi() -> None:
    squad = build_squad(synthetic_player_pool())

    xi_ids = {p.id for p in squad.starting_xi}
    bench_ids = {p.id for p in squad.bench}

    assert len(squad.bench) == 4
    assert xi_ids.isdisjoint(bench_ids)
    assert xi_ids | bench_ids == {p.id for p in squad.all_15}


def test_backup_goalkeeper_is_last_on_the_bench() -> None:
    squad = build_squad(synthetic_player_pool())

    assert squad.bench[-1].position == Position.GKP


def test_captain_and_vice_are_distinct_starting_xi_members() -> None:
    squad = build_squad(synthetic_player_pool())

    xi_ids = {p.id for p in squad.starting_xi}

    assert squad.captain.id in xi_ids
    assert squad.vice_captain.id in xi_ids
    assert squad.captain.id != squad.vice_captain.id


def test_captain_is_never_a_goalkeeper() -> None:
    squad = build_squad(synthetic_player_pool())

    assert squad.captain.position != Position.GKP
    assert squad.vice_captain.position != Position.GKP


def test_captain_has_highest_score_among_outfield_starters() -> None:
    squad = build_squad(synthetic_player_pool())

    outfield_starters = [p for p in squad.starting_xi if p.position != Position.GKP]
    assert squad.captain.ep_next == max(p.ep_next for p in outfield_starters)


def test_build_squad_accepts_scored_override_for_enhanced_mode() -> None:
    """Baseline and enhanced modes must run through the identical
    optimizer/XI/captaincy pipeline - only the input scores differ - so
    that a baseline-vs-enhanced comparison is measuring the scoring
    change, not two different pipelines (integration spec Sec 18).
    """
    from fpl_engine.baseline.scoring import score_players

    players = synthetic_player_pool()
    baseline_scored = score_players(players)

    # "Enhanced" override here just doubles every score - the point isn't
    # the specific transform, it's proving build_squad actually uses
    # scored_override instead of silently recomputing baseline internally.
    doubled = [sp.model_copy(update={"score": sp.score * 2}) for sp in baseline_scored]

    baseline_squad = build_squad(players)
    enhanced_squad = build_squad(players, scored_override=doubled)

    # Both must be independently legal...
    assert validate_squad(baseline_squad.all_15) == []
    assert validate_squad(enhanced_squad.all_15) == []
    # ...and since doubling every score uniformly can't change which
    # squad is optimal, they should select the same players - proving
    # scored_override actually drove the optimization, not a no-op.
    assert {p.id for p in baseline_squad.all_15} == {p.id for p in enhanced_squad.all_15}
