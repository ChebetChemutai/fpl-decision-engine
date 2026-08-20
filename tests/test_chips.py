import pytest

from fpl_engine.domain.chips import (
    FIRST_HALF_LAST_GAMEWEEK,
    Chip,
    ChipState,
    ChipWindow,
    window_for_gameweek,
)


def test_gameweek_19_is_first_half_gameweek_20_is_second_half() -> None:
    assert window_for_gameweek(FIRST_HALF_LAST_GAMEWEEK) == ChipWindow.FIRST_HALF
    assert window_for_gameweek(FIRST_HALF_LAST_GAMEWEEK + 1) == ChipWindow.SECOND_HALF
    assert window_for_gameweek(1) == ChipWindow.FIRST_HALF


def test_fresh_state_has_all_chips_available_in_both_windows() -> None:
    state = ChipState()

    for chip in Chip:
        assert state.is_available(chip, window=ChipWindow.FIRST_HALF)
        assert state.is_available(chip, window=ChipWindow.SECOND_HALF)


def test_playing_a_chip_consumes_only_that_windows_use() -> None:
    state = ChipState().play(Chip.WILDCARD, gameweek=1)

    assert not state.is_available(Chip.WILDCARD, window=ChipWindow.FIRST_HALF)
    assert state.is_available(Chip.WILDCARD, window=ChipWindow.SECOND_HALF)


def test_playing_the_same_chip_twice_in_one_window_raises() -> None:
    state = ChipState().play(Chip.BENCH_BOOST, gameweek=1)

    with pytest.raises(ValueError, match="already used"):
        state.play(Chip.BENCH_BOOST, gameweek=5)  # still first-half window


def test_second_half_use_is_independent_of_first_half_use() -> None:
    state = ChipState().play(Chip.TRIPLE_CAPTAIN, gameweek=3)

    state_after_second = state.play(Chip.TRIPLE_CAPTAIN, gameweek=25)

    assert not state_after_second.is_available(Chip.TRIPLE_CAPTAIN, window=ChipWindow.FIRST_HALF)
    assert not state_after_second.is_available(Chip.TRIPLE_CAPTAIN, window=ChipWindow.SECOND_HALF)


def test_play_does_not_mutate_the_original_state() -> None:
    original = ChipState()

    updated = original.play(Chip.FREE_HIT, gameweek=10)

    assert original.is_available(Chip.FREE_HIT, window=ChipWindow.FIRST_HALF)
    assert not updated.is_available(Chip.FREE_HIT, window=ChipWindow.FIRST_HALF)


def test_only_one_chip_per_gameweek() -> None:
    state = ChipState().play(Chip.WILDCARD, gameweek=7)

    assert not state.only_one_chip_per_gameweek(7)
    assert state.only_one_chip_per_gameweek(8)
