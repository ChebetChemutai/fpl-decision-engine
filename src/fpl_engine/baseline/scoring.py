"""Baseline expected-points scoring (Phase 1.5 / Track A only).

This is intentionally simple and says so everywhere it surfaces: it uses
FPL's own published `ep_next` (their next-gameweek expected-points estimate)
discounted by playing-time availability. It is explicitly a floor, not the
target architecture — the real minutes model, component-prediction ensemble,
and calibration layer (architecture.md Sec 5, 6, 11, 14) supersede this in
later phases. Every recommendation this produces should say "baseline model"
somewhere in its output.
"""

from __future__ import annotations

from fpl_engine.domain.models import Player, PlayerStatus, ScoredPlayer

# Status values that make a player effectively unselectable regardless of
# published chance_of_playing — a nailed-on-cold-start we don't try to
# second-guess with a fractional multiplier.
UNAVAILABLE_STATUSES = {
    PlayerStatus.INJURED,
    PlayerStatus.SUSPENDED,
    PlayerStatus.UNAVAILABLE,
    PlayerStatus.NOT_AVAILABLE,
}


def availability_multiplier(player: Player) -> float:
    """0.0-1.0 multiplier reflecting how likely the player is to play at all."""
    if player.status in UNAVAILABLE_STATUSES:
        return 0.0
    if player.status == PlayerStatus.DOUBTFUL:
        if player.chance_of_playing_next_round is not None:
            return player.chance_of_playing_next_round / 100.0
        return 0.5  # doubtful with no published percentage — conservative default
    return 1.0


def baseline_score(player: Player) -> float:
    """Baseline single-number score used by the Phase 1.5 optimizer.

    score = ep_next * availability_multiplier

    Falls back toward 0 for anyone effectively unavailable, so the optimizer
    naturally excludes them without a separate filtering pass.
    """
    return round(player.ep_next * availability_multiplier(player), 4)


def score_players(players: list[Player]) -> list[ScoredPlayer]:
    return [ScoredPlayer(player=p, score=baseline_score(p)) for p in players]
