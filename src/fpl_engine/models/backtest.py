"""Temporal backtesting (architecture.md Sec 8, Sec 12).

Backtesting here is temporal BY CONSTRUCTION, not by discipline: each
`BacktestCase` carries its own `target_gameweek` and full `history`, and
`run_backtest` calls `compute_features` itself for every case rather than
accepting pre-computed features from the caller. This means a case's
features can never accidentally have been computed with a different
(possibly leaky) target_gameweek than the one it's being scored against —
the harness re-derives them every time, same as live inference would.

This is explicitly NOT k-fold cross-validation. Shuffling gameweeks
across folds would let a model trained on GW10 be validated against
GW5 — training on the future to predict the past, which the model would
never have access to in production. Every case here is scored using only
data that existed strictly before its own target_gameweek.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from fpl_engine.domain.models import Position
from fpl_engine.features.temporal import GameweekPerformance, compute_features
from fpl_engine.models.baselines import PredictionModel


class BacktestCase(BaseModel):
    """One held-out (player, gameweek) instance: what actually happened,
    plus everything a model would legitimately have known beforehand.
    """

    player_id: int
    position: Position
    target_gameweek: int = Field(ge=1)
    history: list[GameweekPerformance]
    actual_points: int


class BacktestResult(BaseModel):
    mae: float  # mean absolute error — primary metric, robust to outliers
    rmse: float  # root mean squared error — penalizes large misses harder
    n: int


def run_backtest(model: PredictionModel, cases: list[BacktestCase]) -> BacktestResult:
    if not cases:
        raise ValueError("cannot backtest against an empty case list")

    errors: list[float] = []
    for case in cases:
        features = compute_features(
            player_id=case.player_id,
            target_gameweek=case.target_gameweek,
            history=case.history,
        )
        predicted = model.predict(features, case.position)
        errors.append(predicted - case.actual_points)

    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e**2 for e in errors) / len(errors))
    return BacktestResult(mae=round(mae, 4), rmse=round(rmse, 4), n=len(cases))
