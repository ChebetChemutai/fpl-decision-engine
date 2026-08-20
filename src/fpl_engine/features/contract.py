"""Feature Contract V4 (architecture.md Sec 6, Sec 8).

The single schema that both historical (training) and live (inference)
feature computation must produce. Historical/live parity is enforced by
having exactly one function (`compute_features` in temporal.py) that both
paths call — there is no second implementation to drift out of sync.

`data_completeness` makes the cold-start distinction from Sec 10 explicit
on every row, rather than silently zero-filling: a downstream model or
the UI can treat a COLD_START row differently from a FULL one instead of
being fed the same shape with hidden meaning.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class DataCompleteness(StrEnum):
    FULL = "full"  # >= 5 eligible historical matches
    PARTIAL = "partial"  # 1-4 eligible historical matches
    COLD_START = "cold_start"  # 0 eligible historical matches


class FeatureContractV4(BaseModel):
    """Temporal features for one player, as of one target gameweek's deadline.

    Every field here is computed ONLY from gameweeks strictly before
    `target_gameweek` — see temporal.py's leakage guard, which is the
    actual enforcement point, not this schema.
    """

    player_id: int
    target_gameweek: int
    data_completeness: DataCompleteness

    matches_played_before: int

    minutes_avg_3: float | None
    minutes_avg_5: float | None
    minutes_season_to_date: float | None

    points_avg_3: float | None
    points_avg_5: float | None
    points_season_to_date: float | None

    form_ewma: float | None  # exponentially weighted recent form
