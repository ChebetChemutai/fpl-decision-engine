from fpl_engine.domain.pricing import calculate_selling_price


def test_no_price_change_sells_at_purchase_price() -> None:
    assert calculate_selling_price(purchase_cost=50, now_cost=50) == 50


def test_rise_of_one_tenth_gives_no_profit_on_sale() -> None:
    """Bought 5.0m, now 5.1m -> sell 5.0m (0.1m profit halved+floored = 0)."""
    assert calculate_selling_price(purchase_cost=50, now_cost=51) == 50


def test_rise_of_two_tenths_gives_one_tenth_profit() -> None:
    """"You need a £0.2m rise just to bank £0.1m profit" - a direct
    quote from one of the verified sources. profit=2 tenths, floor(2/2)=1.
    (An earlier version of this test wrongly asserted 0 profit here,
    extrapolating past what any source actually stated — fixed after
    re-checking against the quote directly.)
    """
    assert calculate_selling_price(purchase_cost=50, now_cost=52) == 51


def test_rise_of_three_tenths_gives_one_tenth_profit() -> None:
    """Bought 5.0m, now 5.3m -> sell 5.1m."""
    assert calculate_selling_price(purchase_cost=50, now_cost=53) == 51


def test_rise_of_four_tenths_gives_two_tenths_profit() -> None:
    """Bought 5.0m, now 5.4m -> sell 5.2m."""
    assert calculate_selling_price(purchase_cost=50, now_cost=54) == 52


def test_rise_from_six_million_matches_independent_worked_example() -> None:
    """Bought 6.0m, now 6.3m -> sell 6.1m (a second source's example,
    cross-checking against a different base price than the 5.0m examples)."""
    assert calculate_selling_price(purchase_cost=60, now_cost=63) == 61


def test_price_fall_absorbs_full_loss_no_protection() -> None:
    """Bought 5.0m, now 4.9m -> sell 4.9m - the full drop, not halved."""
    assert calculate_selling_price(purchase_cost=50, now_cost=49) == 49


def test_large_price_fall_still_absorbs_full_loss() -> None:
    assert calculate_selling_price(purchase_cost=100, now_cost=70) == 70


def test_large_price_rise_still_only_returns_half_profit() -> None:
    # bought 10.0m, now 15.9m -> profit 5.9m, halved+floored = 2.9m -> sell 12.9m
    assert calculate_selling_price(purchase_cost=100, now_cost=159) == 129
