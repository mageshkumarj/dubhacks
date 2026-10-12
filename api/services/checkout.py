"""Mock checkout: no payment, no real order. Idempotent per (cart, Idempotency-Key)."""

import sqlite3

from ..errors import conflict, invalid
from . import carts, promotions, protection
from .cart_pricing import build_view
from .store import Cart, MemoryStore, new_id

MAX_ECHO = 40


def _applied(conn: sqlite3.Connection, cart: Cart, skus: list[str]) -> list[dict]:
    eligible = {
        p["sku"]: p for p in promotions.evaluate_promotions(conn, cart.account_id, cart) or [] if p["eligible"]
    }
    unique = list(dict.fromkeys(skus))
    missing = [s[:MAX_ECHO] for s in unique if s not in eligible]
    if missing:
        raise invalid("PROMO_NOT_ELIGIBLE", f"Not eligible or unknown: {', '.join(missing)}")
    chosen = [eligible[s] for s in unique]
    devices = sum(1 for i in cart.items if i.kind == "device")
    if sum(1 for p in chosen if p["per"] == "device") > devices:
        raise invalid("PROMO_CONFLICT", "Only one device-credit promotion can apply per device in the cart")
    return chosen


def _traded_in_lines(cart: Cart) -> list[str]:
    return [i.line_id for i in cart.items if i.kind == "tradein"]


def checkout(
    conn: sqlite3.Connection, store: MemoryStore, cart_id: str, idempotency_key: str, promo_skus: list[str]
) -> dict:
    with store.lock:
        fingerprint = tuple(sorted(set(promo_skus)))
        previous = store.get_order(cart_id, idempotency_key)
        if previous is not None:
            if previous[0] != fingerprint:
                raise conflict("IDEMPOTENCY_MISMATCH", "This Idempotency-Key was used with different promo_skus")
            return previous[1]
        cart = carts.load(store, cart_id)
        if cart.status != "open":
            raise conflict("CART_CLOSED", "This cart has already been checked out")
        if not cart.items:
            raise invalid("CART_EMPTY", "Cannot check out an empty cart")
        if any(store.is_traded_in(line_id) for line_id in _traded_in_lines(cart)):
            raise conflict("TRADEIN_ALREADY_USED", "A line in this cart was already traded in on another order")
        protection.validate_cart(conn, cart)
        promos = _applied(conn, cart, promo_skus)
        view = build_view(conn, cart)
        order = {
            "order_id": new_id("ORD", 12), "cart_id": cart_id, "account_id": cart.account_id,
            "status": "confirmed", "items": view["items"], "totals": view["totals"],
            "applied_promotions": [
                {**{k: p[k] for k in ("sku", "name", "kind", "value_cents")},
                 "savings_cents": p["estimated_savings_cents"]}
                for p in promos
            ],
            "promo_savings_cents": sum(p["estimated_savings_cents"] for p in promos),
        }
        store.save(cart.closed())
        store.mark_traded_in(_traded_in_lines(cart))
        store.save_order(cart_id, idempotency_key, fingerprint, order)
    return order
