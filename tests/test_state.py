from pathlib import Path

from fpl_engine.data.state import read_chip_state, write_chip_state
from fpl_engine.domain.chips import Chip, ChipWindow


def test_reading_nonexistent_state_returns_fresh_chip_state(tmp_path: Path) -> None:
    state = read_chip_state(tmp_path)

    assert state.is_available(Chip.WILDCARD, window=ChipWindow.FIRST_HALF)


def test_write_then_read_round_trips_correctly(tmp_path: Path) -> None:
    state = read_chip_state(tmp_path).play(Chip.BENCH_BOOST, gameweek=1)

    write_chip_state(tmp_path, state)
    reloaded = read_chip_state(tmp_path)

    assert not reloaded.is_available(Chip.BENCH_BOOST, window=ChipWindow.FIRST_HALF)
    assert reloaded.is_available(Chip.WILDCARD, window=ChipWindow.FIRST_HALF)


def test_state_file_lives_under_state_not_raw(tmp_path: Path) -> None:
    write_chip_state(tmp_path, read_chip_state(tmp_path))

    assert (tmp_path / "state" / "chips.json").exists()
    assert not (tmp_path / "raw").exists()
