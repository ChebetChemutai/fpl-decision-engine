from fpl_engine.baseline.scoring import baseline_score, enhanced_score, score_players_enhanced
from fpl_engine.domain.models import Player, Position


def _player(
    pid: int,
    ep_next: float,
    team_id: int = 1,
    status: str = "a",
    chance: int | None = None,
) -> Player:
    return Player(
        id=pid,
        web_name=f"P{pid}",
        team_id=team_id,
        position=Position.MID,
        price=6.0,
        status=status,  # type: ignore[arg-type]
        chance_of_playing_next_round=chance,
        ep_next=ep_next,
    )


def test_enhanced_score_matches_baseline_at_neutral_fixture() -> None:
    player = _player(1, ep_next=5.0)

    assert enhanced_score(player, fixture_multiplier=1.0) == baseline_score(player)


def test_enhanced_score_scales_with_fixture_multiplier() -> None:
    player = _player(1, ep_next=5.0)

    easy = enhanced_score(player, fixture_multiplier=1.15)
    hard = enhanced_score(player, fixture_multiplier=0.85)

    assert easy > baseline_score(player) > hard


def test_enhanced_score_zero_fixture_multiplier_means_blank_gameweek() -> None:
    player = _player(1, ep_next=5.0)

    assert enhanced_score(player, fixture_multiplier=0.0) == 0.0


def test_historical_prior_only_kicks_in_when_ep_next_is_zero() -> None:
    """A player with a real (if low) ep_next keeps FPL's own projection -
    the historical prior must not override a live, current signal."""
    player = _player(1, ep_next=0.5)

    score = enhanced_score(player, fixture_multiplier=1.0, historical_prior=8.0)

    assert score == 0.5  # prior ignored; ep_next=0.5 is a real projection


def test_historical_prior_fills_in_when_ep_next_is_exactly_zero() -> None:
    player = _player(1, ep_next=0.0)

    score = enhanced_score(player, fixture_multiplier=1.0, historical_prior=8.0)

    assert score == 8.0


def test_historical_prior_never_applied_to_unavailable_player() -> None:
    injured = _player(1, ep_next=0.0, status="i", chance=0)

    score = enhanced_score(injured, fixture_multiplier=1.0, historical_prior=8.0)

    assert score == 0.0  # injured stays 0 regardless of a historical prior


def test_score_players_enhanced_combines_fixture_and_prior_per_player() -> None:
    players = [
        _player(1, ep_next=5.0, team_id=10),  # normal ep_next player
        _player(2, ep_next=0.0, team_id=20),  # cold-start, has a prior
    ]
    fixture_multipliers = {10: 1.08, 20: 1.0}
    priors = {2: 6.0}

    scored = score_players_enhanced(players, fixture_multipliers, priors)
    by_id = {sp.player.id: sp.score for sp in scored}

    assert by_id[1] == round(5.0 * 1.08, 4)
    assert by_id[2] == 6.0


def test_score_players_enhanced_missing_team_fixture_means_blank_gameweek() -> None:
    players = [_player(1, ep_next=5.0, team_id=999)]  # team not in fixture map

    scored = score_players_enhanced(players, fixture_multipliers_by_team={})

    assert scored[0].score == 0.0
