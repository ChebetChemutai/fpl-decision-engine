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


class Team(BaseModel):
    """A Premier League club, as of the snapshot it was read from."""

    id: int
    name: str
    short_name: str
    strength_overall_home: int
    strength_overall_away: int
    strength_attack_home: int
    strength_attack_away: int
    strength_defence_home: int
    strength_defence_away: int

    @classmethod
    def from_bootstrap_team(cls, raw: dict[str, Any]) -> Team:
        return cls(
            id=int(raw["id"]),
            name=str(raw["name"]),
            short_name=str(raw["short_name"]),
            strength_overall_home=int(raw["strength_overall_home"]),
            strength_overall_away=int(raw["strength_overall_away"]),
            strength_attack_home=int(raw["strength_attack_home"]),
            strength_attack_away=int(raw["strength_attack_away"]),
            strength_defence_home=int(raw["strength_defence_home"]),
            strength_defence_away=int(raw["strength_defence_away"]),
        )


class GameweekEvent(BaseModel):
    """One Gameweek's metadata (deadline, status) — FPL calls this an 'event'."""

    id: int
    name: str
    deadline_time: str
    finished: bool
    is_current: bool
    is_next: bool

    @classmethod
    def from_bootstrap_event(cls, raw: dict[str, Any]) -> GameweekEvent:
        return cls(
            id=int(raw["id"]),
            name=str(raw["name"]),
            deadline_time=str(raw["deadline_time"]),
            finished=bool(raw["finished"]),
            is_current=bool(raw["is_current"]),
            is_next=bool(raw["is_next"]),
        )


class Fixture(BaseModel):
    """A single scheduled or completed match between two clubs."""

    id: int
    event: int | None = Field(description="Gameweek number; None if not yet scheduled.")
    team_h: int
    team_a: int
    team_h_difficulty: int | None = None
    team_a_difficulty: int | None = None
    kickoff_time: str | None = None
    finished: bool = False

    @classmethod
    def from_raw_fixture(cls, raw: dict[str, Any]) -> Fixture:
        return cls(
            id=int(raw["id"]),
            event=int(raw["event"]) if raw.get("event") is not None else None,
            team_h=int(raw["team_h"]),
            team_a=int(raw["team_a"]),
            team_h_difficulty=raw.get("team_h_difficulty"),
            team_a_difficulty=raw.get("team_a_difficulty"),
            kickoff_time=raw.get("kickoff_time"),
            finished=bool(raw.get("finished", False)),
        )
