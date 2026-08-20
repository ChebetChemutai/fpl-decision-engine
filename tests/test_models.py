import json
from pathlib import Path

import pytest

from fpl_engine.domain.models import Player, PlayerStatus, Position

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bootstrap_arsenal_sample.json"


@pytest.fixture
def real_elements() -> list[dict[str, object]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["elements"]  # type: ignore[no-any-return]


def test_parses_available_outfield_player(real_elements: list[dict[str, object]]) -> None:
    raw = next(e for e in real_elements if e["web_name"] == "Saka")

    player = Player.from_bootstrap_element(raw)

    assert player.id == 12
    assert player.web_name == "Saka"
    assert player.position == Position.MID
    assert player.price == 9.5  # now_cost 95 -> £9.5m
    assert player.status == PlayerStatus.AVAILABLE
    assert player.ep_next == 3.2


def test_parses_injured_player_with_zero_chance(real_elements: list[dict[str, object]]) -> None:
    raw = next(e for e in real_elements if e["web_name"] == "J.Timber")

    player = Player.from_bootstrap_element(raw)

    assert player.status == PlayerStatus.INJURED
    assert player.chance_of_playing_next_round == 0


def test_parses_goalkeeper_position(real_elements: list[dict[str, object]]) -> None:
    raw = next(e for e in real_elements if e["web_name"] == "Raya")

    player = Player.from_bootstrap_element(raw)

    assert player.position == Position.GKP
    assert player.price == 6.0
