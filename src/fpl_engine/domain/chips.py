"""Chip domain model — season 2026/27.

Verified directly against premierleague.com (2026-08-20): four chip types
this season — Wildcard, Free Hit, Bench Boost, Triple Captain — each
usable ONCE PER HALF-SEASON WINDOW (8 chip uses total). The first-half
window closes at the Gameweek 19 deadline; the second half runs from
Gameweek 20 onward. There is no Assistant Manager chip in 2026/27 (it
existed only in 2024/25) — an earlier draft of this file incorrectly
included it based on a lower-quality secondary source; corrected against
the official source before merging.

This module models chip *inventory and legality* only — *when* to play a
chip is a Phase 12 (Chip Engine) strategy decision, not a domain-rules
concern; see architecture.md Sec 19.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

FIRST_HALF_LAST_GAMEWEEK = 19  # last GW the first-half chip set may be played in


class Chip(StrEnum):
    WILDCARD = "wildcard"
    FREE_HIT = "free_hit"
    BENCH_BOOST = "bench_boost"
    TRIPLE_CAPTAIN = "triple_captain"


class ChipWindow(StrEnum):
    FIRST_HALF = "first_half"  # GW1 - GW19 deadline
    SECOND_HALF = "second_half"  # GW20 - season end


class ChipUse(BaseModel):
    chip: Chip
    gameweek: int = Field(ge=1)
    window: ChipWindow


def window_for_gameweek(gameweek: int) -> ChipWindow:
    if gameweek <= FIRST_HALF_LAST_GAMEWEEK:
        return ChipWindow.FIRST_HALF
    return ChipWindow.SECOND_HALF


class ChipState(BaseModel):
    """A manager's chip inventory as of a point in the season.

    Every chip type has exactly one use per window; using the Gameweek-1
    Wildcard does not consume the second-half Wildcard, and vice versa.
    """

    used: list[ChipUse] = Field(default_factory=list)

    def is_available(self, chip: Chip, *, window: ChipWindow) -> bool:
        return not any(u.chip == chip and u.window == window for u in self.used)

    def play(self, chip: Chip, gameweek: int) -> ChipState:
        """Return a new ChipState with `chip` marked used for the window that
        `gameweek` falls in. Does not mutate self — chip state must be as
        immutable/versioned as everything else that feeds a recommendation
        (architecture.md Sec 3).
        """
        window = window_for_gameweek(gameweek)
        if not self.is_available(chip, window=window):
            raise ValueError(f"{chip.value} already used in the {window.value} window")
        new_use = ChipUse(chip=chip, gameweek=gameweek, window=window)
        return ChipState(used=[*self.used, new_use])

    def only_one_chip_per_gameweek(self, gameweek: int) -> bool:
        """True if no chip has already been played in this exact gameweek —
        FPL only allows one chip active per Gameweek, across all four types.
        """
        return not any(u.gameweek == gameweek for u in self.used)
