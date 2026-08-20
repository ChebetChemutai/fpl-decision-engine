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


def test_captain_has_highest_score_in_starting_xi() -> None:
    squad = build_squad(synthetic_player_pool())

    assert squad.captain.ep_next == max(p.ep_next for p in squad.starting_xi)
