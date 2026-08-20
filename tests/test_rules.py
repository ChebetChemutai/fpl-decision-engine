from fpl_engine.domain.models import Player, Position
from fpl_engine.domain.rules import validate_squad, validate_starting_xi


def _player(id: int, position: Position, team_id: int, price: float = 5.0) -> Player:
    return Player(
        id=id,
        web_name=f"Player{id}",
        team_id=team_id,
        position=position,
        price=price,
        status="a",  # type: ignore[arg-type]
        ep_next=1.0,
    )


def _legal_squad() -> list[Player]:
    """2 GKP, 5 DEF, 5 MID, 3 FWD spread across 6 clubs, under budget."""
    players: list[Player] = []
    pid = 1
    layout = [
        (Position.GKP, 2),
        (Position.DEF, 5),
        (Position.MID, 5),
        (Position.FWD, 3),
    ]
    team_cycle = [1, 2, 3, 4, 5, 6]
    team_idx = 0
    for position, count in layout:
        for _ in range(count):
            players.append(
                _player(pid, position, team_cycle[team_idx % len(team_cycle)], price=5.0)
            )
            pid += 1
            team_idx += 1
    return players


def test_legal_squad_has_no_violations() -> None:
    assert validate_squad(_legal_squad()) == []


def test_wrong_squad_size_is_flagged() -> None:
    squad = _legal_squad()[:14]

    violations = validate_squad(squad)

    assert any("exactly 15" in v for v in violations)


def test_over_budget_squad_is_flagged() -> None:
    squad = _legal_squad()
    squad[0] = _player(squad[0].id, squad[0].position, squad[0].team_id, price=95.0)

    violations = validate_squad(squad)

    assert any("exceeds budget" in v for v in violations)


def test_too_many_from_one_club_is_flagged() -> None:
    squad = _legal_squad()
    # Force 4 players onto team 1.
    for i in range(4):
        squad[i] = _player(squad[i].id, squad[i].position, team_id=1)

    violations = validate_squad(squad)

    assert any("team 1" in v and "exceeds max" in v for v in violations)


def test_wrong_position_count_is_flagged() -> None:
    squad = _legal_squad()
    squad[0] = _player(squad[0].id, Position.DEF, squad[0].team_id)  # was GKP

    violations = validate_squad(squad)

    assert any("GKP" in v for v in violations)


def test_duplicate_player_is_flagged() -> None:
    squad = _legal_squad()
    squad[1] = squad[0]

    violations = validate_squad(squad)

    assert any("duplicate" in v for v in violations)


def test_legal_starting_xi_has_no_violations() -> None:
    # 1 GKP + 4 DEF + 4 MID + 2 FWD = 11, a valid formation (4-4-2).
    xi = (
        [_player(1, Position.GKP, 1)]
        + [_player(i, Position.DEF, i) for i in range(2, 6)]
        + [_player(i, Position.MID, i) for i in range(6, 10)]
        + [_player(i, Position.FWD, i) for i in range(10, 12)]
    )

    assert validate_starting_xi(xi) == []


def test_starting_xi_with_two_goalkeepers_is_flagged() -> None:
    xi = (
        [_player(1, Position.GKP, 1), _player(2, Position.GKP, 2)]
        + [_player(i, Position.DEF, i) for i in range(3, 6)]
        + [_player(i, Position.MID, i) for i in range(6, 10)]
        + [_player(10, Position.FWD, 10)]
    )

    violations = validate_starting_xi(xi)

    assert any("GKP" in v for v in violations)
