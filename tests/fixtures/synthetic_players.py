"""Synthetic test player pool.

NOT real FPL data — a small, hand-built player universe spanning 6 clubs and
all 4 positions, sized so a legal 15-man squad is achievable under budget.
Used only to exercise the optimizer's constraint handling (budget, position
counts, max-3-per-club) in isolation from real-world data volume.
"""

from __future__ import annotations

from fpl_engine.domain.models import Player, Position

# (id, web_name, team_id, position, price, ep_next)
_SYNTHETIC_PLAYERS: list[tuple[int, str, int, Position, float, float]] = [
    # Goalkeepers
    (1, "GK-Cheap-A", 1, Position.GKP, 4.0, 3.0),
    (2, "GK-Premium-A", 2, Position.GKP, 5.5, 4.5),
    (3, "GK-Cheap-B", 3, Position.GKP, 4.0, 2.5),
    # Defenders
    (10, "DEF-Cheap-A", 1, Position.DEF, 4.0, 2.0),
    (11, "DEF-Cheap-B", 1, Position.DEF, 4.0, 2.0),
    (12, "DEF-Mid-A", 2, Position.DEF, 5.0, 3.5),
    (13, "DEF-Mid-B", 3, Position.DEF, 5.0, 3.2),
    (14, "DEF-Premium-A", 4, Position.DEF, 6.5, 5.0),
    (15, "DEF-Premium-B", 5, Position.DEF, 6.0, 4.5),
    (16, "DEF-Cheap-C", 6, Position.DEF, 4.0, 2.1),
    # Midfielders
    (20, "MID-Cheap-A", 1, Position.MID, 4.5, 2.5),
    (21, "MID-Mid-A", 2, Position.MID, 6.5, 4.0),
    (22, "MID-Premium-A", 3, Position.MID, 10.0, 8.5),
    (23, "MID-Premium-B", 4, Position.MID, 9.5, 8.0),
    (24, "MID-Mid-B", 5, Position.MID, 7.0, 4.5),
    (25, "MID-Cheap-B", 6, Position.MID, 4.5, 2.3),
    # Forwards
    (30, "FWD-Cheap-A", 1, Position.FWD, 4.5, 2.5),
    (31, "FWD-Premium-A", 2, Position.FWD, 9.0, 7.5),
    (32, "FWD-Mid-A", 3, Position.FWD, 6.5, 4.5),
    (33, "FWD-Injured-Premium", 4, Position.FWD, 11.0, 9.5),  # status=i, see below
]

_INJURED_IDS = {33}


def synthetic_player_pool() -> list[Player]:
    players: list[Player] = []
    for pid, name, team_id, position, price, ep_next in _SYNTHETIC_PLAYERS:
        status = "i" if pid in _INJURED_IDS else "a"
        players.append(
            Player(
                id=pid,
                web_name=name,
                team_id=team_id,
                position=position,
                price=price,
                status=status,  # type: ignore[arg-type]
                chance_of_playing_next_round=0 if pid in _INJURED_IDS else None,
                ep_next=ep_next,
            )
        )
    return players
