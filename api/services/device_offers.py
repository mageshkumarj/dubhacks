"""Checkout rule: each phone in the cart receives at most one per-device offer."""

import sqlite3

from ..errors import invalid
from .promotions import unit_value_cents


def _allowed_phones(promo: sqlite3.Row, phones: list[str]) -> list[int]:
    skus = promo["device_skus"].split(",") if promo["device_skus"] else []
    return [i for i, sku in enumerate(phones) if not skus or sku in skus]


def _augment(slot: int, allowed: list[list[int]], owner: dict[int, int], seen: set[int]) -> bool:
    """Kuhn's algorithm: give the offer slot a phone, moving other slots to other phones when needed."""
    for phone in allowed[slot]:
        if phone in seen:
            continue
        seen.add(phone)
        if phone not in owner or _augment(owner[phone], allowed, owner, seen):
            owner[phone] = slot
            return True
    return False


def assign(promos: list[sqlite3.Row], phones: list[str]) -> dict[str, int]:
    """Best assignment of phones to the chosen per-device offers: {promo sku: number of phones it covers}.

    Offers are tried by per-unit value (ties keep the caller's order), so the most valuable offers keep their phones.
    Raises PROMO_CONFLICT naming an offer that ends up with no phone.
    """
    ranked = sorted(promos, key=lambda p: -unit_value_cents(p))
    slots: list[tuple[str, list[int]]] = []  # one slot per phone an offer may cover (its max_units caps this)
    for promo in ranked:
        allowed = _allowed_phones(promo, phones)
        slots += [(promo["sku"], allowed)] * min(promo["max_units"] or len(allowed), len(allowed))
    slot_phones = [allowed for _, allowed in slots]
    owner: dict[int, int] = {}
    for slot in range(len(slots)):
        _augment(slot, slot_phones, owner, set())
    covered = {p["sku"]: 0 for p in ranked}
    for slot in owner.values():
        covered[slots[slot][0]] += 1
    for sku, count in covered.items():
        if count == 0:
            raise invalid("PROMO_CONFLICT", f"Only one device offer can apply per phone; {sku} has no phone left")
    return covered
