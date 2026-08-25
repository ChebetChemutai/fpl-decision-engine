"""Temporal Feature Engine V4 (architecture.md Sec 6, Sec 8).

`compute_features` is the ONE function both historical (training) and live
(inference) code paths call — this is what makes "same feature contract"
in the architecture doc real rather than aspirational. There is no second
implementation for live mode to drift out of sync with.

THE LEAKAGE GUARD (read this before touching this file): `compute_features`
filters its input to strictly-before-`target_gameweek` records BEFORE any
computation touches them. This holds even if the caller passes a `history`
list containing future gameweeks — which is the normal, expected shape for
historical/training data (you have the whole season on disk). The function
does not trust the caller to have already filtered; it filters itself,
unconditionally. `test_temporal.py::test_future_gameweeks_never_leak_into_features`
is the test that must never be allowed to fail.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fpl_engine.features.contract import DataCompleteness, FeatureContractV4

FULL_DATA_THRESHOLD = 5  # >= this many eligible matches -> "full" completeness
FORM_EWMA_ALPHA = 0.5  # weight on the most recent match; higher = more reactive


class GameweekPerformance(BaseModel):
    """One player's actual result for one completed gameweek.

    This is historical fact (what happened), not a prediction — the input
    type to feature computation, never its output. Field set matches real
    element-summary `history` entries (confirmed via a live fetch against
    a played gameweek, 2026-08-25) — everything scoring_rules.MatchStats
    needs to be reconstructed for component-level modeling, not just the
    total_points/minutes that were sufficient for Phase 4/5's aggregate
    features alone.

    All the added fields default to 0 so existing callers/tests that only
    ever cared about minutes/total_points (Phase 4/5) keep working
    unchanged — this is additive, not a breaking change to the contract.
    """

    gameweek: int = Field(ge=1)
    minutes: int = Field(ge=0, le=120)
    total_points: int

    goals_scored: int = Field(default=0, ge=0)
    assists: int = Field(default=0, ge=0)
    clean_sheets: int = Field(default=0, ge=0, description="0 or 1 in practice, per match.")
    goals_conceded: int = Field(default=0, ge=0)
    own_goals: int = Field(default=0, ge=0)
    penalties_saved: int = Field(default=0, ge=0)
    penalties_missed: int = Field(default=0, ge=0)
    yellow_cards: int = Field(default=0, ge=0)
    red_cards: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    bonus: int = Field(default=0, ge=0, le=3)
    defensive_contribution: int = Field(default=0, ge=0)
    starts: int = Field(default=0, ge=0, le=1)


def _rolling_average(values: list[int], window: int) -> float | None:
    if not values:
        return None
    tail = values[-window:]
    return round(sum(tail) / len(tail), 3)


def _ewma(values: list[int], alpha: float) -> float | None:
    """Exponentially weighted moving average, oldest-to-newest input order.
    Most recent value gets weight `alpha`; each older value's weight decays
    by (1 - alpha) per step back.
    """
    if not values:
        return None
    weighted: float = values[0]
    for v in values[1:]:
        weighted = alpha * v + (1 - alpha) * weighted
    return round(weighted, 3)


def compute_features(
    player_id: int,
    target_gameweek: int,
    history: list[GameweekPerformance],
) -> FeatureContractV4:
    """Compute FeatureContractV4 for `player_id` as of `target_gameweek`'s
    deadline, from `history` (which may contain future gameweeks — those
    are filtered out here, not by the caller).
    """
    eligible = sorted(
        (h for h in history if h.gameweek < target_gameweek),
        key=lambda h: h.gameweek,
    )

    matches_played = len(eligible)
    if matches_played == 0:
        completeness = DataCompleteness.COLD_START
    elif matches_played < FULL_DATA_THRESHOLD:
        completeness = DataCompleteness.PARTIAL
    else:
        completeness = DataCompleteness.FULL

    minutes_series = [h.minutes for h in eligible]
    points_series = [h.total_points for h in eligible]

    return FeatureContractV4(
        player_id=player_id,
        target_gameweek=target_gameweek,
        data_completeness=completeness,
        matches_played_before=matches_played,
        minutes_avg_3=_rolling_average(minutes_series, 3),
        minutes_avg_5=_rolling_average(minutes_series, 5),
        minutes_season_to_date=_rolling_average(minutes_series, len(minutes_series))
        if minutes_series
        else None,
        points_avg_3=_rolling_average(points_series, 3),
        points_avg_5=_rolling_average(points_series, 5),
        points_season_to_date=_rolling_average(points_series, len(points_series))
        if points_series
        else None,
        form_ewma=_ewma(points_series, FORM_EWMA_ALPHA),
    )
