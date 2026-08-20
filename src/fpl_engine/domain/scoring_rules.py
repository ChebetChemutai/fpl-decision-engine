"""FPL scoring engine — season 2026/27.

Converts raw per-match player statistics into FPL points. Values verified
against multiple current sources on 2026-08-20 (see docs/architecture.md
Sec 7 — this must stay independently testable and versioned so a
mid-season rule change only touches this file).

Deliberately excludes Bonus Points System (BPS) computation: BPS is a
proprietary ~32-statistic formula the official docs don't fully publish,
and per architecture.md Sec 13, bonus is a *component to predict*, not a
formula to derive from raw stats we have access to. `bonus` is therefore
an explicit input to `calculate_points`, not something this module
computes — supplied from actual results (post-match) or a future bonus
prediction model (pre-match), never fabricated here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fpl_engine.domain.models import Position

MIN_MINUTES_FOR_APPEARANCE_POINT = 1
MIN_MINUTES_FOR_FULL_APPEARANCE = 60
MIN_MINUTES_FOR_CLEAN_SHEET_ELIGIBILITY = 60

GOALS_CONCEDED_PER_DEDUCTION = 2
SAVES_PER_POINT = 3

GOAL_POINTS: dict[Position, int] = {
    Position.GKP: 10,
    Position.DEF: 6,
    Position.MID: 5,
    Position.FWD: 4,
}
ASSIST_POINTS = 3

CLEAN_SHEET_POINTS: dict[Position, int] = {
    Position.GKP: 4,
    Position.DEF: 4,
    Position.MID: 1,
    Position.FWD: 0,
}

# Defensive contributions ("DEFCON"): +2, capped at 2 regardless of how far
# over the threshold a player goes. Unchanged from 2025/26 into 2026/27.
DEFENSIVE_CONTRIBUTION_POINTS = 2
DEFENSIVE_CONTRIBUTION_THRESHOLD: dict[Position, int] = {
    Position.DEF: 10,  # CBIT: clearances + blocks + interceptions + tackles
    Position.MID: 12,  # CBIRT: CBIT + ball recoveries
    Position.FWD: 12,
    Position.GKP: 0,  # goalkeepers do not earn defensive-contribution points
}

PENALTY_MISS_POINTS = -2
PENALTY_SAVE_POINTS = 5
YELLOW_CARD_POINTS = -1
RED_CARD_POINTS = -3
OWN_GOAL_POINTS = -2


class MatchStats(BaseModel):
    """Raw per-match statistics for one player. Everything the scoring
    function needs and nothing it derives — no points, no BPS.
    """

    position: Position
    minutes: int = Field(ge=0, le=120)
    goals_scored: int = Field(default=0, ge=0)
    assists: int = Field(default=0, ge=0)
    goals_conceded: int = Field(
        default=0, ge=0, description="By the player's team while on the pitch."
    )
    own_goals: int = Field(default=0, ge=0)
    penalties_saved: int = Field(default=0, ge=0)
    penalties_missed: int = Field(default=0, ge=0)
    yellow_cards: int = Field(default=0, ge=0)
    red_cards: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    defensive_contributions: int = Field(
        default=0, ge=0, description="CBIT (DEF) or CBIRT (MID/FWD) combined actions."
    )
    bonus: int = Field(default=0, ge=0, le=3, description="Already-determined BPS bonus, if known.")


def calculate_points(stats: MatchStats) -> int:
    """Compute total FPL points for one player's single-match performance."""
    points = 0

    if stats.minutes >= MIN_MINUTES_FOR_FULL_APPEARANCE:
        points += 2
    elif stats.minutes >= MIN_MINUTES_FOR_APPEARANCE_POINT:
        points += 1

    points += stats.goals_scored * GOAL_POINTS[stats.position]
    points += stats.assists * ASSIST_POINTS

    played_full_appearance = stats.minutes >= MIN_MINUTES_FOR_CLEAN_SHEET_ELIGIBILITY
    kept_clean_sheet = stats.goals_conceded == 0
    if played_full_appearance and kept_clean_sheet:
        points += CLEAN_SHEET_POINTS[stats.position]

    if stats.position in (Position.GKP, Position.DEF) and played_full_appearance:
        points -= (stats.goals_conceded // GOALS_CONCEDED_PER_DEDUCTION)

    if stats.position == Position.GKP:
        points += stats.saves // SAVES_PER_POINT

    threshold = DEFENSIVE_CONTRIBUTION_THRESHOLD[stats.position]
    if threshold and stats.defensive_contributions >= threshold:
        points += DEFENSIVE_CONTRIBUTION_POINTS

    points += stats.penalties_saved * PENALTY_SAVE_POINTS
    points += stats.penalties_missed * PENALTY_MISS_POINTS
    points += stats.yellow_cards * YELLOW_CARD_POINTS
    points += stats.red_cards * RED_CARD_POINTS
    points += stats.own_goals * OWN_GOAL_POINTS
    points += stats.bonus

    return points
