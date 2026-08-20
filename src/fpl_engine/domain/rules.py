"""FPL rules engine — season 2026/27 (`rules/season_2026_27` per architecture Sec 7).

Values below were read directly from the live `bootstrap-static` `game_settings`
and `element_types` payload on 2026-08-20 (see docs/architecture.md Sec 7 for
why this must stay a versioned, testable module rather than hard-coded
constants scattered through the optimizer). If FPL changes squad/budget rules
mid-season, only this file should need to change.
"""

from __future__ import annotations

from dataclasses import dataclass

from fpl_engine.domain.models import Player, Position


@dataclass(frozen=True)
class PositionRule:
    squad_count: int  # exactly this many in the 15-man squad
    min_play: int  # minimum in the starting XI
    max_play: int  # maximum in the starting XI


SQUAD_SIZE = 15
STARTING_XI_SIZE = 11
BUDGET_M = 100.0  # squad_total_spend=1000 in FPL's tenths-of-a-million units
MAX_PER_CLUB = 3

POSITION_RULES: dict[Position, PositionRule] = {
    Position.GKP: PositionRule(squad_count=2, min_play=1, max_play=1),
    Position.DEF: PositionRule(squad_count=5, min_play=3, max_play=5),
    Position.MID: PositionRule(squad_count=5, min_play=2, max_play=5),
    Position.FWD: PositionRule(squad_count=3, min_play=1, max_play=3),
}


def validate_squad(players: list[Player]) -> list[str]:
    """Return a list of rule violations for a candidate 15-man squad.

    Empty list means the squad is legal. This is the single source of
    truth for legality — the optimizer must produce squads that pass this,
    and this function must never be bypassed to "fix" an optimizer bug.
    """
    violations: list[str] = []

    if len(players) != SQUAD_SIZE:
        violations.append(f"squad must have exactly {SQUAD_SIZE} players, got {len(players)}")

    if len({p.id for p in players}) != len(players):
        violations.append("squad contains duplicate players")

    total_price = sum(p.price for p in players)
    if total_price > BUDGET_M + 1e-9:
        violations.append(f"total price {total_price:.1f} exceeds budget {BUDGET_M:.1f}")

    for position, rule in POSITION_RULES.items():
        count = sum(1 for p in players if p.position == position)
        if count != rule.squad_count:
            violations.append(
                f"{position.name}: expected {rule.squad_count} in squad, got {count}"
            )

    club_counts: dict[int, int] = {}
    for p in players:
        club_counts[p.team_id] = club_counts.get(p.team_id, 0) + 1
    for team_id, count in club_counts.items():
        if count > MAX_PER_CLUB:
            violations.append(f"team {team_id}: {count} players exceeds max {MAX_PER_CLUB}")

    return violations


def validate_starting_xi(xi: list[Player]) -> list[str]:
    """Return violations for a starting XI drawn from an already-legal squad."""
    violations: list[str] = []

    if len(xi) != STARTING_XI_SIZE:
        violations.append(
            f"starting XI must have exactly {STARTING_XI_SIZE} players, got {len(xi)}"
        )

    for position, rule in POSITION_RULES.items():
        count = sum(1 for p in xi if p.position == position)
        if position == Position.GKP and count != 1:
            violations.append(f"GKP: exactly 1 required in starting XI, got {count}")
        elif position != Position.GKP and not (rule.min_play <= count <= rule.max_play):
            violations.append(
                f"{position.name}: starting XI count {count} outside "
                f"[{rule.min_play}, {rule.max_play}]"
            )

    return violations
