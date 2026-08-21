"""Player scoring — baseline and enhanced modes (integration spec Sec 3, 18).

Baseline mode (`score_players`) is unchanged and reproducible: FPL's own
`ep_next`, discounted by playing-time availability. Kept exactly as-is
deliberately — it's the control group enhanced mode is measured against,
not a stepping stone to delete once something better exists.

Enhanced mode (`score_players_enhanced`) layers in fixture difficulty
(always) and a history-based prior (only for players ep_next has nothing
to say about). It is still not the target architecture — the real
minutes model, component-prediction ensemble, and calibration layer
(architecture.md Sec 5, 6, 11, 14) supersede both of these in later
phases.
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


def enhanced_score(
    player: Player,
    fixture_multiplier: float,
    historical_prior: float | None = None,
) -> float:
    """Enhanced single-number score: baseline, adjusted for fixture
    difficulty, with a history-based prior standing in when FPL's own
    ep_next has nothing to say about this player at all.

    Deliberately layered rather than blended everywhere: fixture
    difficulty always applies (it's a property of the match, independent
    of how we estimated the player's underlying rate). The historical
    prior only substitutes in when ep_next==0 for an otherwise-available
    player — see historical_prior.py's docstring for why that specific
    trigger, and not just "low ep_next".
    """
    availability = availability_multiplier(player)
    base = player.ep_next * availability
    if base == 0.0 and availability > 0.0 and historical_prior is not None:
        base = historical_prior * availability
    return round(base * fixture_multiplier, 4)


def score_players_enhanced(
    players: list[Player],
    fixture_multipliers_by_team: dict[int, float],
    historical_priors_by_player: dict[int, float] | None = None,
) -> list[ScoredPlayer]:
    """Enhanced-mode scoring for a full player pool.

    `fixture_multipliers_by_team` and `historical_priors_by_player` are
    precomputed by the caller (see baseline/fixture_signal.py and
    baseline/historical_prior.py) — this function only combines them, it
    doesn't fetch or parse anything, keeping it trivially testable.
    A team with no entry in `fixture_multipliers_by_team` is treated as a
    blank gameweek (multiplier 0.0) rather than silently defaulting to
    neutral — missing fixture data should suppress the player, not hide
    the gap.
    """
    priors = historical_priors_by_player or {}
    scored = []
    for player in players:
        fixture_multiplier = fixture_multipliers_by_team.get(player.team_id, 0.0)
        prior = priors.get(player.id)
        score = enhanced_score(player, fixture_multiplier, prior)
        scored.append(ScoredPlayer(player=player, score=score))
    return scored
