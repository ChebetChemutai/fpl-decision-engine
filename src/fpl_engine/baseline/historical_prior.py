"""History-based cold-start prior (integration spec Sec 5).

Fallback hierarchy this module implements the second tier of:

    current-season signal (ep_next)  [tier 1, handled in scoring.py]
        -> history_past prior         [tier 2, this module]
            -> position-level fallback [tier 3, handled by the optimizer's
                                         existing zero-score exclusion —
                                         see note below]
                -> safe neutral (0.0)

A player only reaches this module when FPL's own `ep_next` is 0 AND they
are actually available to play (not injured/suspended) — i.e. FPL has no
current projection for them, typically a new signing or a player recently
returned from a long absence. This is deliberately NOT triggered by every
low-ep_next player; ep_next=0.5 is a real (if pessimistic) projection FPL
has made, and overriding it with a historical guess would throw away a
more current signal in favor of a stale one.
"""

from __future__ import annotations

from fpl_engine.domain.models import SeasonSummary

# Last season's rate is a genuine signal but a noisy one for THIS season -
# new club, new manager, new system, a year older. Weighting it down
# rather than using it at full strength reflects that uncertainty
# explicitly instead of pretending a prior season transfers 1:1.
HISTORICAL_PRIOR_WEIGHT = 0.5

MIN_MINUTES_FOR_RELIABLE_RATE = 450  # ~5 full matches - below this, the
# points-per-90 rate is too noisy to trust as a prior at all.


def points_per_90(summary: SeasonSummary) -> float | None:
    """Points-per-90-minutes rate for one season, or None if the player
    barely featured (rate would be noise, not signal).
    """
    if summary.minutes < MIN_MINUTES_FOR_RELIABLE_RATE:
        return None
    return round(summary.total_points / (summary.minutes / 90.0), 4)


def historical_prior_score(past_seasons: list[SeasonSummary]) -> float | None:
    """A single-gameweek expected-points prior derived from the player's
    most recent season with a reliable minutes total.

    `past_seasons` is expected in the API's natural (oldest-to-newest)
    order — confirmed against a real element-summary response, where
    2020/21 appears first and 2025/26 last. Returns None (not 0.0) when
    no usable season exists, so the caller can distinguish "we have no
    prior" from "we have a prior and it's genuinely zero" — the same
    true-zero-vs-missing distinction the temporal feature engine enforces
    (architecture.md Sec 10).
    """
    for summary in reversed(past_seasons):  # most recent first
        rate = points_per_90(summary)
        if rate is not None:
            return round(rate * HISTORICAL_PRIOR_WEIGHT, 4)
    return None
