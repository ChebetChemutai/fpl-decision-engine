"""Core domain models: players, positions, and the assembled squad.

These are the shapes that flow from ingestion -> rules -> optimizer -> CLI
output. Deliberately minimal for Phase 1.5 — no fixtures/xG/minutes-model
fields yet; those arrive with the full domain build in Phase 2.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Position(IntEnum):
    """Matches FPL's `element_type` values exactly — do not renumber."""

    GKP = 1
    DEF = 2
    MID = 3
    FWD = 4


class PlayerStatus(StrEnum):
    """FPL's `status` field. Governs availability, not form."""

    AVAILABLE = "a"
    DOUBTFUL = "d"
    INJURED = "i"
    NOT_AVAILABLE = "n"  # e.g. left the league / on loan elsewhere
    SUSPENDED = "s"
    UNAVAILABLE = "u"


class Player(BaseModel):
    """A single selectable FPL player, as of the snapshot it was read from."""

    id: int
    web_name: str
    team_id: int
    position: Position
    price: float = Field(description="Price in £m, e.g. 8.0 for a £8.0m player.")
    status: PlayerStatus
    chance_of_playing_next_round: int | None = Field(
        default=None, description="0-100, or None if not currently doubtful/injured."
    )
    ep_next: float = Field(description="FPL's own published expected points for the next GW.")
    points_per_game: float = Field(default=0.0)
    selected_by_percent: float = Field(default=0.0)

    @classmethod
    def from_bootstrap_element(cls, raw: dict[str, Any]) -> Player:
        """Build a Player from one entry of bootstrap-static's `elements` array."""
        chance = raw.get("chance_of_playing_next_round")
        return cls(
            id=int(raw["id"]),
            web_name=str(raw["web_name"]),
            team_id=int(raw["team"]),
            position=Position(int(raw["element_type"])),
            price=int(raw["now_cost"]) / 10.0,
            status=PlayerStatus(str(raw["status"])),
            chance_of_playing_next_round=int(chance) if chance is not None else None,
            ep_next=float(raw.get("ep_next") or 0.0),
            points_per_game=float(raw.get("points_per_game") or 0.0),
            selected_by_percent=float(raw.get("selected_by_percent") or 0.0),
        )


class ScoredPlayer(BaseModel):
    """A Player plus the baseline score the optimizer selects on.

    Kept separate from Player so the scoring function's assumptions are
    visible and swappable without touching the domain model.
    """

    player: Player
    score: float


class Squad(BaseModel):
    """A complete, rules-valid 15-player squad with a chosen starting XI."""

    all_15: list[Player]
    starting_xi: list[Player]
    bench: list[Player]
    captain: Player
    vice_captain: Player

    @property
    def total_price(self) -> float:
        return round(sum(p.price for p in self.all_15), 1)
