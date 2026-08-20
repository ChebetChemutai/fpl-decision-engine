from fpl_engine.domain.models import Position
from fpl_engine.domain.scoring_rules import MatchStats, calculate_points


def test_appearance_points_scale_with_minutes() -> None:
    # goals_conceded=1 so MID's 90-min case isn't also picking up an
    # (irrelevant to this test) clean sheet point.
    no_show = MatchStats(position=Position.MID, minutes=0, goals_conceded=1)
    cameo = MatchStats(position=Position.MID, minutes=15, goals_conceded=1)
    full_match = MatchStats(position=Position.MID, minutes=90, goals_conceded=1)

    assert calculate_points(no_show) == 0
    assert calculate_points(cameo) == 1
    assert calculate_points(full_match) == 2


def test_goal_points_vary_by_position() -> None:
    # goals_conceded=1: isolates goal points from the separate clean-sheet
    # bonus, which is tested on its own below.
    gk = MatchStats(position=Position.GKP, minutes=90, goals_scored=1, goals_conceded=1)
    defender = MatchStats(position=Position.DEF, minutes=90, goals_scored=1, goals_conceded=1)
    midfielder = MatchStats(position=Position.MID, minutes=90, goals_scored=1, goals_conceded=1)
    forward = MatchStats(position=Position.FWD, minutes=90, goals_scored=1, goals_conceded=1)

    # 2 appearance + goal points - 0 (1 conceded -> floor(1/2)=0 deduction)
    assert calculate_points(gk) == 2 + 10
    assert calculate_points(defender) == 2 + 6
    assert calculate_points(midfielder) == 2 + 5
    assert calculate_points(forward) == 2 + 4


def test_assist_worth_three_points_regardless_of_position() -> None:
    fwd = MatchStats(position=Position.FWD, minutes=90, assists=1, goals_conceded=1)
    gk = MatchStats(position=Position.GKP, minutes=90, assists=1, goals_conceded=1)

    assert calculate_points(fwd) == 2 + 3
    assert calculate_points(gk) == 2 + 3


def test_clean_sheet_requires_60_plus_minutes() -> None:
    played_59 = MatchStats(position=Position.DEF, minutes=59, goals_conceded=0)
    played_60 = MatchStats(position=Position.DEF, minutes=60, goals_conceded=0)

    assert calculate_points(played_59) == 1  # appearance only, no CS credit
    assert calculate_points(played_60) == 2 + 4  # appearance + clean sheet


def test_clean_sheet_points_by_position() -> None:
    gk = MatchStats(position=Position.GKP, minutes=90, goals_conceded=0)
    defender = MatchStats(position=Position.DEF, minutes=90, goals_conceded=0)
    midfielder = MatchStats(position=Position.MID, minutes=90, goals_conceded=0)
    forward = MatchStats(position=Position.FWD, minutes=90, goals_conceded=0)

    assert calculate_points(gk) == 2 + 4
    assert calculate_points(defender) == 2 + 4
    assert calculate_points(midfielder) == 2 + 1
    assert calculate_points(forward) == 2 + 0


def test_goals_conceded_deduction_only_applies_to_gk_and_def() -> None:
    defender = MatchStats(position=Position.DEF, minutes=90, goals_conceded=4)
    midfielder = MatchStats(position=Position.MID, minutes=90, goals_conceded=4)

    # appearance(2) - floor(4/2)=2 deduction, no clean sheet
    assert calculate_points(defender) == 2 - 2
    # midfielders never lose points for goals conceded
    assert calculate_points(midfielder) == 2


def test_saves_worth_one_point_per_three_gk_only() -> None:
    gk = MatchStats(position=Position.GKP, minutes=90, saves=7, goals_conceded=1)

    # appearance(2) + saves(7//3=2) - goals conceded deduction(1//2=0), no CS
    assert calculate_points(gk) == 2 + 2 - 0


def test_defensive_contribution_threshold_by_position() -> None:
    defender_under = MatchStats(
        position=Position.DEF, minutes=90, defensive_contributions=9, goals_conceded=1
    )
    defender_at_threshold = MatchStats(
        position=Position.DEF, minutes=90, defensive_contributions=10, goals_conceded=1
    )
    midfielder_under = MatchStats(
        position=Position.MID, minutes=90, defensive_contributions=11, goals_conceded=1
    )
    midfielder_at_threshold = MatchStats(
        position=Position.MID, minutes=90, defensive_contributions=12, goals_conceded=1
    )

    assert calculate_points(defender_under) == 2  # no DC bonus
    assert calculate_points(defender_at_threshold) == 2 + 2  # appearance + DC (no CS: conceded 1)
    assert calculate_points(midfielder_under) == 2  # no DC bonus, below 12
    assert calculate_points(midfielder_at_threshold) == 2 + 2  # appearance + DC


def test_defensive_contribution_is_capped_at_two_points_regardless_of_volume() -> None:
    huge_volume = MatchStats(
        position=Position.DEF, minutes=90, defensive_contributions=25, goals_conceded=1
    )
    at_threshold = MatchStats(
        position=Position.DEF, minutes=90, defensive_contributions=10, goals_conceded=1
    )

    assert calculate_points(huge_volume) == calculate_points(at_threshold)


def test_goalkeepers_never_earn_defensive_contribution_points() -> None:
    gk_huge_dc = MatchStats(
        position=Position.GKP, minutes=90, defensive_contributions=99, goals_conceded=1
    )

    assert calculate_points(gk_huge_dc) == 2  # appearance only, no CS (conceded 1), no DC


def test_penalty_miss_and_save() -> None:
    misser = MatchStats(position=Position.FWD, minutes=90, penalties_missed=1)
    saver = MatchStats(position=Position.GKP, minutes=90, penalties_saved=1, goals_conceded=1)

    assert calculate_points(misser) == 2 - 2
    assert calculate_points(saver) == 2 + 5


def test_cards_and_own_goals_are_penalized() -> None:
    yellow = MatchStats(position=Position.MID, minutes=90, yellow_cards=1, goals_conceded=1)
    red = MatchStats(position=Position.MID, minutes=90, red_cards=1, goals_conceded=1)
    own_goal = MatchStats(position=Position.DEF, minutes=90, own_goals=1, goals_conceded=1)

    assert calculate_points(yellow) == 2 - 1
    assert calculate_points(red) == 2 - 3
    assert calculate_points(own_goal) == 2 - 2


def test_bonus_is_a_direct_input_not_derived() -> None:
    with_bonus = MatchStats(position=Position.MID, minutes=90, bonus=3, goals_conceded=1)

    assert calculate_points(with_bonus) == 2 + 3


def test_realistic_full_performance() -> None:
    """A defender: full 90, 1 goal, clean sheet, hits DC threshold, 2 bonus."""
    stats = MatchStats(
        position=Position.DEF,
        minutes=90,
        goals_scored=1,
        goals_conceded=0,
        defensive_contributions=11,
        bonus=2,
    )

    # appearance(2) + goal(6) + clean_sheet(4) + DC(2) + bonus(2)
    assert calculate_points(stats) == 2 + 6 + 4 + 2 + 2
