from fpl_engine.domain.chips import Chip
from fpl_engine.domain.transfers import (
    MAX_BANKED_FREE_TRANSFERS,
    TransferState,
    calculate_transfer_cost,
)


def test_using_exactly_your_free_transfers_is_free() -> None:
    assert calculate_transfer_cost(transfers_made=1, free_transfers_available=1) == 0
    assert calculate_transfer_cost(transfers_made=2, free_transfers_available=2) == 0


def test_transfers_beyond_free_ones_cost_four_points_each() -> None:
    assert calculate_transfer_cost(transfers_made=3, free_transfers_available=1) == 8
    assert calculate_transfer_cost(transfers_made=2, free_transfers_available=0) == 8


def test_wildcard_makes_all_transfers_free() -> None:
    cost = calculate_transfer_cost(
        transfers_made=10, free_transfers_available=1, chip_played=Chip.WILDCARD
    )

    assert cost == 0


def test_free_hit_makes_all_transfers_free() -> None:
    cost = calculate_transfer_cost(
        transfers_made=15, free_transfers_available=0, chip_played=Chip.FREE_HIT
    )

    assert cost == 0


def test_bench_boost_does_not_affect_transfer_cost() -> None:
    cost = calculate_transfer_cost(
        transfers_made=3, free_transfers_available=1, chip_played=Chip.BENCH_BOOST
    )

    assert cost == 8  # bench boost has nothing to do with transfers


def test_unused_free_transfer_banks_for_next_gameweek() -> None:
    state = TransferState(free_transfers_available=1, bank=0.0)

    next_state = state.advance_gameweek(transfers_made=0)

    assert next_state.free_transfers_available == 2


def test_free_transfers_cap_at_five() -> None:
    state = TransferState(free_transfers_available=MAX_BANKED_FREE_TRANSFERS, bank=0.0)

    next_state = state.advance_gameweek(transfers_made=0)

    assert next_state.free_transfers_available == MAX_BANKED_FREE_TRANSFERS


def test_using_all_free_transfers_resets_to_one_next_gameweek() -> None:
    state = TransferState(free_transfers_available=2, bank=0.0)

    next_state = state.advance_gameweek(transfers_made=2)

    assert next_state.free_transfers_available == 1


def test_taking_a_hit_does_not_go_negative() -> None:
    state = TransferState(free_transfers_available=1, bank=0.0)

    next_state = state.advance_gameweek(transfers_made=3)  # 1 free + 2 paid hits

    assert next_state.free_transfers_available == 1  # floors at 0 unused, +1 for the GW


def test_advance_gameweek_preserves_bank() -> None:
    state = TransferState(free_transfers_available=1, bank=2.3)

    next_state = state.advance_gameweek(transfers_made=1)

    assert next_state.bank == 2.3
