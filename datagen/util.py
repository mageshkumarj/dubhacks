"""Small pure helpers shared by the generator modules."""

import math
from datetime import date
from random import Random


def months_ago(anchor: date, months: int) -> date:
    index = anchor.year * 12 + (anchor.month - 1) - months
    return date(index // 12, index % 12 + 1, 1)


def months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def poisson(rng: Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def weighted(rng: Random, options: tuple[tuple[str, float], ...]) -> str:
    names, weights = zip(*options, strict=True)
    return rng.choices(names, weights=weights, k=1)[0]


def derived_rng(seed: int | str, *parts: object) -> Random:
    return Random("/".join(str(p) for p in (seed, *parts)))
