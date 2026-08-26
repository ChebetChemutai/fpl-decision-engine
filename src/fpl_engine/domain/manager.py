"""Manager ('entry') domain models.

Field sets here are DELIBERATELY CONSERVATIVE: only fields independently
corroborated across multiple documentation sources are included. Fields
some sources mention but this codebase could not independently confirm
via a live fetch this session (e.g. whether picks carry `selling_price`/
`purchase_price` per player) are NOT included — see
docs/manager-integration.md for exactly what's confirmed vs assumed.
Extend this file once a real account's actual response is inspected,
rather than guessing now.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ManagerProfile(BaseModel):
    """Public profile from GET /entry/{id}/."""

    id: int
    player_first_name: str
    player_last_name: str
    team_name: str
    summary_overall_points: int
    summary_overall_rank: int | None
    current_event: int | None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ManagerProfile:
        return cls(
            id=int(raw["id"]),
            player_first_name=str(raw["player_first_name"]),
            player_last_name=str(raw["player_last_name"]),
            team_name=str(raw["name"]),
            summary_overall_points=int(raw.get("summary_overall_points") or 0),
            summary_overall_rank=raw.get("summary_overall_rank"),
            current_event=raw.get("current_event"),
        )


class ManagerGameweekHistory(BaseModel):
    """One entry from GET /entry/{id}/history/ -> `current` (this season,
    per gameweek). Core fields confirmed against a real live response
    (2026-08-26, manager 6313636, GW1) via /entry/{id}/event/{gw}/picks/'s
    `entry_history` block, which shares this shape. `rank_sort`,
    `percentile_rank`, `overall_rank_percentage` are also real and
    present but not yet captured here — deferred, not missed; add them
    if a future feature needs them rather than carrying unused fields now.
    """

    event: int
    points: int
    total_points: int
    rank: int | None
    overall_rank: int | None
    bank: int = 0
    value: int = 0
    event_transfers: int = 0
    event_transfers_cost: int = 0
    points_on_bench: int = 0

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ManagerGameweekHistory:
        return cls(
            event=int(raw["event"]),
            points=int(raw["points"]),
            total_points=int(raw["total_points"]),
            rank=raw.get("rank"),
            overall_rank=raw.get("overall_rank"),
            bank=int(raw.get("bank") or 0),
            value=int(raw.get("value") or 0),
            event_transfers=int(raw.get("event_transfers") or 0),
            event_transfers_cost=int(raw.get("event_transfers_cost") or 0),
            points_on_bench=int(raw.get("points_on_bench") or 0),
        )


class ManagerPick(BaseModel):
    """One squad slot from GET /entry/{id}/event/{gw}/picks/ -> `picks`.

    Field set CONFIRMED against a real, live response (2026-08-26,
    manager 6313636, GW1) — not documentation-based. Confirmed present:
    element, position, multiplier, is_captain, is_vice_captain,
    element_type. Confirmed ABSENT from this response: selling_price,
    purchase_price — do not add them; they are not part of this
    endpoint's real shape, at least not for a just-played gameweek.
    `automatic_subs` (a sibling key in the same response, not part of
    `picks`) exists but is not parsed here yet — deferred, not missed.
    """

    element: int  # player id, joins to bootstrap-static elements[].id
    position: int  # 1-15, squad slot order (1-11 starting, 12-15 bench)
    multiplier: int  # 0 (benched), 1 (starts), 2/3 (captain/triple captain)
    is_captain: bool
    is_vice_captain: bool
    element_type: int  # 1-4, matches domain.models.Position values

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ManagerPick:
        return cls(
            element=int(raw["element"]),
            position=int(raw["position"]),
            multiplier=int(raw["multiplier"]),
            is_captain=bool(raw["is_captain"]),
            is_vice_captain=bool(raw["is_vice_captain"]),
            element_type=int(raw["element_type"]),
        )
