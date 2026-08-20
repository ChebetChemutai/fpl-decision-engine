"""Chip domain model — season 2026/27.

Chip windows sourced directly from the live bootstrap-static `chips` array
(fetched 2026-08-20), not inferred from articles — that payload is the
actual source of truth FPL itself uses to gate chip legality:

  wildcard:        first half start_event=2,  stop_event=19
  free_hit:        first half start_event=2,  stop_event=19
  bench_boost:     first half start_event=1,  stop_event=19
  triple_captain:  first half start_event=1,  stop_event=19
  (all four repeat for the second half: start_event=20, stop_event=38)

Note the asymmetry this corrects for: Wildcard and Free Hit cannot be
played in Gameweek 1 (they only open from GW2), while Bench Boost and
Triple Captain CAN be played in GW1. An earlier draft of this module
assumed all four chips shared one uniform window boundary — wrong, and
caught by going back to the actual API payload instead of the secondary
sources used for the scoring-rules verification.

This module models chip *inventory and legality* only — *when* to play a
chip is a Phase 12 (Chip Engine) strategy decision, not a domain-rules
concern; see architecture.md Sec 19.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Chip(StrEnum):
    WILDCARD = "wildcard"
    FREE_HIT = "free_hit"
    BENCH_BOOST = "bench_boost"
    TRIPLE_CAPTAIN = "triple_captain"


class ChipWindow(StrEnum):
    FIRST_HALF = "first_half"
    SECOND_HALF = "second_half"


# (chip, window) -> (first eligible gameweek, last eligible gameweek), verified
# against the live bootstrap-static `chips` payload.
CHIP_WINDOW_BOUNDS: dict[tuple[Chip, ChipWindow], tuple[int, int]] = {
    (Chip.WILDCARD, ChipWindow.FIRST_HALF): (2, 19),
    (Chip.WILDCARD, ChipWindow.SECOND_HALF): (20, 38),
    (Chip.FREE_HIT, ChipWindow.FIRST_HALF): (2, 19),
    (Chip.FREE_HIT, ChipWindow.SECOND_HALF): (20, 38),
    (Chip.BENCH_BOOST, ChipWindow.FIRST_HALF): (1, 19),
    (Chip.BENCH_BOOST, ChipWindow.SECOND_HALF): (20, 38),
    (Chip.TRIPLE_CAPTAIN, ChipWindow.FIRST_HALF): (1, 19),
    (Chip.TRIPLE_CAPTAIN, ChipWindow.SECOND_HALF): (20, 38),
}


def window_for_gameweek(chip: Chip, gameweek: int) -> ChipWindow:
    """Which window a gameweek falls in, for a specific chip.

    Must be per-chip, not global: GW1 is inside Bench Boost's first-half
    window but outside Wildcard's/Free Hit's (which don't open until GW2).
    """
    for window in ChipWindow:
        start, end = CHIP_WINDOW_BOUNDS[(chip, window)]
        if start <= gameweek <= end:
            return window
    raise ValueError(f"gameweek {gameweek} is outside all {chip.value} windows")


def is_gameweek_eligible(chip: Chip, gameweek: int) -> bool:
    return any(
        start <= gameweek <= end
        for (c, _window), (start, end) in CHIP_WINDOW_BOUNDS.items()
        if c == chip
    )


class ChipUse(BaseModel):
    chip: Chip
    gameweek: int = Field(ge=1)
    window: ChipWindow


class ChipState(BaseModel):
    """A manager's chip inventory as of a point in the season.

    Every chip type has exactly one use per window; using the Gameweek-2
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

        Raises ValueError if `gameweek` is outside every window for this
        chip (e.g. Wildcard in GW1) or if that window's use is already spent.
        """
        window = window_for_gameweek(chip, gameweek)
        if not self.is_available(chip, window=window):
            raise ValueError(f"{chip.value} already used in the {window.value} window")
        new_use = ChipUse(chip=chip, gameweek=gameweek, window=window)
        return ChipState(used=[*self.used, new_use])

    def only_one_chip_per_gameweek(self, gameweek: int) -> bool:
        """True if no chip has already been played in this exact gameweek —
        FPL only allows one chip active per Gameweek, across all four types.
        """
        return not any(u.gameweek == gameweek for u in self.used)
