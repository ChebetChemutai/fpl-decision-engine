"""Player price and selling-price rules — season 2026/27.

The selling-price rule below is verified against the official, long-
standing FPL mechanic (confirmed unchanged for 2026/27 by multiple
independent sources on 2026-08-25, each giving matching worked examples):
a manager keeps only HALF of any price RISE since purchase, rounded DOWN
to the nearest £0.1m; a price FALL is absorbed in full. This is NOT the
hidden day-to-day price-change formula (which FPL does not disclose and
this module makes no attempt to guess) — it is the separate, documented
rule for what a player already in your squad can be sold for.

Worked examples used to verify this implementation (from independent
sources, all consistent):
  bought 5.0m, now 5.1m -> sell 5.0m  (profit 0.1m, halved+floored = 0)
  bought 5.0m, now 5.3m -> sell 5.1m  (profit 0.3m, halved+floored = 0.1m)
  bought 5.0m, now 5.4m -> sell 5.2m  (profit 0.4m, halved+floored = 0.2m)
  bought 6.0m, now 6.3m -> sell 6.1m  (profit 0.3m, halved+floored = 0.1m)
  bought 5.0m, now 4.9m -> sell 4.9m  (full loss, no protection)
"""

from __future__ import annotations


def calculate_selling_price(purchase_cost: int, now_cost: int) -> int:
    """Both arguments and the return value are in FPL's tenths-of-a-million
    integer units (e.g. 50 for £5.0m) — the same units as `now_cost` in
    bootstrap-static, deliberately, so callers never need to convert.

    A price RISE returns half the profit, floor-divided (integer division
    already achieves "rounded down to the nearest £0.1m" in these units).
    A price FALL or no change returns `now_cost` unchanged — full loss,
    no partial protection.
    """
    if now_cost <= purchase_cost:
        return now_cost
    profit = now_cost - purchase_cost
    return purchase_cost + profit // 2
