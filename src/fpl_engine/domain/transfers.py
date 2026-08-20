"""Transfer domain model — season 2026/27.

Free transfers accumulate at 1 per Gameweek, bank up to a maximum of 5
(confirmed unchanged from the prior season's roll-over rule), and every
transfer beyond the free ones costs 4 points ("a hit"). Wildcard and Free
Hit both make transfers free and unlimited for that Gameweek only — that
interaction is modeled here since it changes the point-cost calculation,
not because chip *strategy* belongs in this module (see chips.py).

This module computes legality and cost only. Deciding *whether* a hit is
worth taking is a Phase 10 (Transfer Engine) strategy decision.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fpl_engine.domain.chips import Chip

FREE_TRANSFERS_PER_GAMEWEEK = 1
MAX_BANKED_FREE_TRANSFERS = 5
POINTS_COST_PER_EXTRA_TRANSFER = 4


class TransferState(BaseModel):
    """A manager's transfer position as of a Gameweek deadline."""

    free_transfers_available: int = Field(ge=0, le=MAX_BANKED_FREE_TRANSFERS)
    bank: float = Field(ge=0.0, description="Unspent budget in £m.")

    def advance_gameweek(self, transfers_made: int) -> TransferState:
        """Roll forward free-transfer accrual after a Gameweek's transfers.

        Unused free transfers bank (up to the cap); using more than were
        free does not go negative — those extra ones were paid for as hits.
        """
        unused = max(0, self.free_transfers_available - transfers_made)
        next_available = min(MAX_BANKED_FREE_TRANSFERS, unused + FREE_TRANSFERS_PER_GAMEWEEK)
        return TransferState(free_transfers_available=next_available, bank=self.bank)


def calculate_transfer_cost(
    transfers_made: int,
    free_transfers_available: int,
    *,
    chip_played: Chip | None = None,
) -> int:
    """Points cost of making `transfers_made` transfers this Gameweek.

    Wildcard and Free Hit make all transfers free for the Gameweek they're
    played in, regardless of banked free transfers.
    """
    if chip_played in (Chip.WILDCARD, Chip.FREE_HIT):
        return 0
    extra_transfers = max(0, transfers_made - free_transfers_available)
    return extra_transfers * POINTS_COST_PER_EXTRA_TRANSFER
