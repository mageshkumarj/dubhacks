"""One rounding rule for every cents amount, so the catalog, quotes and carts always agree."""

import math


def half_up(value: float) -> int:
    return math.floor(value + 0.5)
