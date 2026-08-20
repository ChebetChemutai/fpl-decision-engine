import json
from pathlib import Path

import pytest

from fpl_engine.baseline.scoring import availability_multiplier, baseline_score
from fpl_engine.domain.models import Player

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bootstrap_arsenal_sample.json"


@pytest.fixture
def real_players() -> list[Player]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [Player.from_bootstrap_element(e) for e in data["elements"]]


def test_available_player_gets_full_ep_next_as_score(real_players: list[Player]) -> None:
    saka = next(p for p in real_players if p.web_name == "Saka")

    assert availability_multiplier(saka) == 1.0
    assert baseline_score(saka) == saka.ep_next


def test_injured_player_scores_zero_regardless_of_ep_next(real_players: list[Player]) -> None:
    timber = next(p for p in real_players if p.web_name == "J.Timber")

    assert availability_multiplier(timber) == 0.0
    assert baseline_score(timber) == 0.0


def test_doubtful_player_with_no_percentage_gets_conservative_default() -> None:
    doubtful = Player(
        id=999,
        web_name="Test Doubtful",
        team_id=1,
        position=3,  # type: ignore[arg-type]
        price=6.0,
        status="d",  # type: ignore[arg-type]
        chance_of_playing_next_round=None,
        ep_next=5.0,
    )

    assert availability_multiplier(doubtful) == 0.5
    assert baseline_score(doubtful) == 2.5


def test_doubtful_player_with_published_percentage_uses_it() -> None:
    doubtful = Player(
        id=998,
        web_name="Test 75pct",
        team_id=1,
        position=3,  # type: ignore[arg-type]
        price=6.0,
        status="d",  # type: ignore[arg-type]
        chance_of_playing_next_round=75,
        ep_next=4.0,
    )

    assert availability_multiplier(doubtful) == 0.75
    assert baseline_score(doubtful) == 3.0
