from fpl_engine.domain.models import Player, Position, Squad
from fpl_engine.features.temporal import GameweekPerformance
from fpl_engine.models.evaluation import (
    SquadPick,
    evaluate_squad_points,
    points_by_player_from_element_history,
    squad_to_picks,
)


def _player(pid: int, position: Position = Position.MID) -> Player:
    return Player(
        id=pid, web_name=f"P{pid}", team_id=1, position=position,
        price=5.0, status="a", ep_next=1.0,  # type: ignore[arg-type]
    )


def test_evaluate_squad_points_sums_points_times_multiplier() -> None:
    picks = [SquadPick(player_id=1, multiplier=1), SquadPick(player_id=2, multiplier=2)]
    points = {1: 5, 2: 8}

    assert evaluate_squad_points(picks, points) == 5 + 16


def test_evaluate_squad_points_benched_players_contribute_zero() -> None:
    picks = [SquadPick(player_id=1, multiplier=0)]
    points = {1: 99}  # scored well, but benched -> contributes 0

    assert evaluate_squad_points(picks, points) == 0


def test_evaluate_squad_points_missing_player_defaults_to_zero() -> None:
    picks = [SquadPick(player_id=999, multiplier=1)]  # not in points_by_player at all

    assert evaluate_squad_points(picks, {}) == 0


def test_evaluate_squad_points_triple_captain_multiplier() -> None:
    picks = [SquadPick(player_id=1, multiplier=3)]
    points = {1: 10}

    assert evaluate_squad_points(picks, points) == 30


def test_points_by_player_from_element_history_extracts_correct_gameweek() -> None:
    histories = {
        1: [
            GameweekPerformance(gameweek=1, minutes=90, total_points=6),
            GameweekPerformance(gameweek=2, minutes=90, total_points=2),
        ]
    }

    points_gw1 = points_by_player_from_element_history(histories, gameweek=1)
    points_gw2 = points_by_player_from_element_history(histories, gameweek=2)

    assert points_gw1 == {1: 6}
    assert points_gw2 == {1: 2}


def test_points_by_player_omits_players_with_no_result_for_that_gameweek() -> None:
    histories = {1: [GameweekPerformance(gameweek=1, minutes=90, total_points=6)]}

    points_gw2 = points_by_player_from_element_history(histories, gameweek=2)

    assert 1 not in points_gw2


def test_squad_to_picks_captain_gets_multiplier_two() -> None:
    captain = _player(1)
    others = [_player(i) for i in range(2, 11)]
    bench = [_player(i) for i in range(11, 15)]
    squad = Squad(
        all_15=[captain, *others, *bench],
        starting_xi=[captain, *others],
        bench=bench,
        captain=captain,
        vice_captain=others[0],
    )

    picks = squad_to_picks(squad)

    captain_pick = next(p for p in picks if p.player_id == captain.id)
    assert captain_pick.multiplier == 2


def test_squad_to_picks_bench_gets_multiplier_zero() -> None:
    captain = _player(1)
    others = [_player(i) for i in range(2, 11)]
    bench = [_player(i) for i in range(11, 15)]
    squad = Squad(
        all_15=[captain, *others, *bench],
        starting_xi=[captain, *others],
        bench=bench,
        captain=captain,
        vice_captain=others[0],
    )

    picks = squad_to_picks(squad)

    bench_picks = [p for p in picks if p.player_id in {b.id for b in bench}]
    assert all(p.multiplier == 0 for p in bench_picks)
    assert len(bench_picks) == 4


def test_squad_to_picks_non_captain_starters_get_multiplier_one() -> None:
    captain = _player(1)
    others = [_player(i) for i in range(2, 11)]
    bench = [_player(i) for i in range(11, 15)]
    squad = Squad(
        all_15=[captain, *others, *bench],
        starting_xi=[captain, *others],
        bench=bench,
        captain=captain,
        vice_captain=others[0],
    )

    picks = squad_to_picks(squad)

    non_captain_starters = [p for p in picks if p.player_id in {o.id for o in others}]
    assert all(p.multiplier == 1 for p in non_captain_starters)
