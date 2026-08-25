"""Bridges ingested element-history data into the backtest harness
(integration spec Sec 7).

This is the connection point between `data/contracts.py::parse_element_history`
(real ingestion output) and `models/backtest.py::run_backtest` (evaluation).
Nothing here fabricates data — if no player has a real result for
`target_gameweek` yet (true today: GW1 hasn't been ingested post-match),
both functions correctly return empty, and the CLI must say so plainly
rather than reporting a hollow "0 cases, 0.0 error" as if it meant
something.
"""

from __future__ import annotations

from fpl_engine.domain.models import Position
from fpl_engine.features.temporal import GameweekPerformance
from fpl_engine.models.backtest import BacktestCase


def build_backtest_cases(
    player_histories: dict[int, list[GameweekPerformance]],
    positions_by_player: dict[int, Position],
    target_gameweek: int,
) -> list[BacktestCase]:
    """One BacktestCase per player who has a REAL recorded result for
    `target_gameweek` — that result becomes `actual_points` (the held-out
    ground truth), and the player's full history becomes `history` (the
    leakage guard in `compute_features`/`run_backtest` filters this to
    strictly-before-target internally, same as always — this function
    does not pre-filter, deliberately, so it exercises the real guard
    rather than duplicating its logic).

    A player with no record for `target_gameweek` (not played, or that
    gameweek hasn't happened yet) is skipped, not defaulted to 0 — there
    is no ground truth to evaluate against, so including them would be
    scoring a case that doesn't exist.
    """
    cases: list[BacktestCase] = []
    for player_id, history in player_histories.items():
        position = positions_by_player.get(player_id)
        if position is None:
            continue
        actual = next((h for h in history if h.gameweek == target_gameweek), None)
        if actual is None:
            continue
        cases.append(
            BacktestCase(
                player_id=player_id,
                position=position,
                target_gameweek=target_gameweek,
                history=history,
                actual_points=actual.total_points,
            )
        )
    return cases


def build_training_points_by_position(
    player_histories: dict[int, list[GameweekPerformance]],
    positions_by_player: dict[int, Position],
    before_gameweek: int,
) -> dict[Position, list[int]]:
    """Training data for `PositionAverageBaseline.fit`, built from real
    results strictly before `before_gameweek` — so the baseline itself is
    never fit on future information relative to whatever gameweek it's
    about to be evaluated against. Same leakage discipline as feature
    computation, applied to model fitting rather than a single player's
    features.
    """
    training: dict[Position, list[int]] = {}
    for player_id, history in player_histories.items():
        position = positions_by_player.get(player_id)
        if position is None:
            continue
        for record in history:
            if record.gameweek < before_gameweek:
                training.setdefault(position, []).append(record.total_points)
    return training
