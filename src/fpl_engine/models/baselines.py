"""Baseline prediction models (architecture.md Sec 5, Sec 12).

"Start with strong baselines... [later models] must beat the baseline on
held-out gameweeks before being allowed into the ensemble." These two
models ARE that baseline gate — nothing more sophisticated (gradient
boosting, etc., in a later phase) gets used unless `run_backtest` shows
it beating `FormWeightedBaseline` on real held-out data.

Both models predict expected points for the NEXT gameweek from a
FeatureContractV4 — never from raw history directly, so every model
automatically inherits the Phase 4 leakage guard rather than needing its
own.
"""

from __future__ import annotations

from typing import Protocol

from fpl_engine.domain.models import Position
from fpl_engine.features.contract import FeatureContractV4


class PredictionModel(Protocol):
    def predict(self, features: FeatureContractV4, position: Position) -> float: ...


class PositionAverageBaseline:
    """Predicts the training-set average points for the player's position,
    ignoring everything else about the player. The floor every other model
    must beat — if a fancier model can't outperform "just guess the
    position average," it isn't adding value.
    """

    def __init__(self, position_averages: dict[Position, float], overall_average: float) -> None:
        self._position_averages = position_averages
        self._overall_average = overall_average

    @classmethod
    def fit(cls, training_points_by_position: dict[Position, list[int]]) -> PositionAverageBaseline:
        position_averages: dict[Position, float] = {}
        all_points: list[int] = []
        for position, points in training_points_by_position.items():
            if points:
                position_averages[position] = sum(points) / len(points)
            all_points.extend(points)
        overall_average = sum(all_points) / len(all_points) if all_points else 0.0
        return cls(position_averages, overall_average)

    def predict(self, features: FeatureContractV4, position: Position) -> float:
        del features  # unused by design — this model is intentionally naive
        return self._position_averages.get(position, self._overall_average)


class FormWeightedBaseline:
    """Predicts recent EWMA form when available, falling back to the
    position average for cold-start / low-data players (architecture.md
    Sec 10 — cold start must never be silently treated the same as "we
    have a confident signal").
    """

    def __init__(self, fallback: PositionAverageBaseline) -> None:
        self._fallback = fallback

    def predict(self, features: FeatureContractV4, position: Position) -> float:
        if features.form_ewma is not None:
            return features.form_ewma
        return self._fallback.predict(features, position)
