"""Device protection covers exactly one phone: the phone on a named line, or an uncovered phone in the cart."""

import sqlite3

from ..errors import DomainError, conflict, invalid
from . import catalog
from .store import Cart, CartItem

NEEDS_A_PHONE = "Device protection covers a phone: add the phone first, or name its line with line_id"


def _device_tier(conn: sqlite3.Connection, sku: str) -> int:
    return conn.execute("SELECT protection_tier FROM devices WHERE sku = ?", (sku,)).fetchone()[0]


def _cart_phones(conn: sqlite3.Connection, cart: Cart) -> list[tuple[CartItem, int]]:
    return [(i, _device_tier(conn, i.sku)) for i in cart.items if i.kind == "device"]


def _protections(conn: sqlite3.Connection, cart: Cart) -> list[CartItem]:
    kinds = {}
    out = []
    for item in cart.items:
        if item.kind != "addon":
            continue
        if item.sku not in kinds:
            kinds[item.sku] = conn.execute("SELECT kind FROM addons WHERE sku = ?", (item.sku,)).fetchone()[0]
        if kinds[item.sku] == "protection":
            out.append(item)
    return out


def _tier_of(conn: sqlite3.Connection, item: CartItem) -> int:
    return conn.execute("SELECT protection_tier FROM addons WHERE sku = ?", (item.sku,)).fetchone()[0]


def _mismatch(phone_name: str, needs: int, got: int) -> DomainError:
    return invalid("PROTECTION_TIER_MISMATCH", f"{phone_name} needs protection tier {needs}, not {got}")


def _check_line(conn: sqlite3.Connection, cart: Cart, tier: int, line_id: str) -> None:
    """The phone that will be on the line: the one being bought for it, else the one it has today."""
    bought = next((i for i, _ in _cart_phones(conn, cart) if i.line_id == line_id), None)
    sku = bought.sku if bought else conn.execute(
        "SELECT device_sku FROM lines WHERE line_id = ?", (line_id,)
    ).fetchone()[0]
    if sku is None:
        raise invalid("INVALID_ITEM", "Device protection needs a line with a device (BYOD lines have none)")
    device = catalog.get_device(conn, sku)
    if device["protection_tier"] != tier:
        raise _mismatch(device["name"], device["protection_tier"], tier)


def _uncovered_phones(conn: sqlite3.Connection, cart: Cart) -> list[tuple[CartItem, int]]:
    """Phones in the cart that no protection already covers (named lines first, then by tier in cart order)."""
    phones = _cart_phones(conn, cart)
    covered: set[str] = set()
    protections = _protections(conn, cart)
    for p in (p for p in protections if p.line_id):
        covered.update(i.item_id for i, _ in phones if i.line_id == p.line_id)
    for p in (p for p in protections if not p.line_id):
        tier = _tier_of(conn, p)
        match = next((i for i, t in phones if t == tier and i.item_id not in covered), None)
        if match:
            covered.add(match.item_id)
    return [(i, t) for i, t in phones if i.item_id not in covered]


def _check_cart_phone(conn: sqlite3.Connection, cart: Cart, tier: int) -> None:
    if not _cart_phones(conn, cart):
        raise invalid("INVALID_ITEM", NEEDS_A_PHONE)
    uncovered = _uncovered_phones(conn, cart)
    if not uncovered:
        raise conflict("DUPLICATE_ITEM", "Every phone in the cart already has device protection")
    if not any(t == tier for _, t in uncovered):
        needed = sorted({t for _, t in uncovered})
        raise invalid(
            "PROTECTION_TIER_MISMATCH", f"No uncovered phone in the cart needs tier {tier}; they need {needed}"
        )


def check_protection(conn: sqlite3.Connection, cart: Cart, addon: dict, line_id: str | None) -> None:
    """Raise a DomainError unless this protection add-on would cover a real, uncovered phone."""
    tier = addon["protection_tier"]
    if line_id is None:
        _check_cart_phone(conn, cart, tier)
        return
    if any(p.line_id == line_id for p in _protections(conn, cart)):
        raise conflict("DUPLICATE_ITEM", "That line already has device protection in this cart")
    _check_line(conn, cart, tier, line_id)


def validate_cart(conn: sqlite3.Connection, cart: Cart) -> None:
    """At checkout, every protection item must still cover a phone (a phone may have been removed since)."""
    for item in _protections(conn, cart):
        addon = catalog.get_addon(conn, item.sku)
        try:
            check_protection(conn, cart.without_item(item.item_id), addon, item.line_id)
        except DomainError as exc:
            raise invalid(
                "PROTECTION_UNMATCHED", f"{addon['name']} no longer covers a phone in the cart: {exc.message}"
            ) from exc
