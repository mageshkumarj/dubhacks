import sqlite3

from ..errors import conflict, invalid, not_found
from . import catalog, pricing, protection
from .cart_pricing import build_view
from .common import dataset_sha
from .store import Cart, CartItem, MemoryStore, new_id

MAX_ITEMS = 25
KINDS = ("device", "plan", "new_line", "addon", "tradein")
ONE_PER_LINE = ("device", "plan", "tradein")
PAYMENTS = ("financed", "full")


def load(store: MemoryStore, cart_id: str) -> Cart:
    cart = store.get(cart_id)
    if cart is None:
        raise not_found("CART_NOT_FOUND", "Cart not found (carts reset when the server restarts)")
    return cart


def create_cart(conn: sqlite3.Connection, store: MemoryStore, account_id: str | None) -> dict:
    if account_id is not None:
        if conn.execute("SELECT 1 FROM accounts WHERE account_id = ?", (account_id,)).fetchone() is None:
            raise not_found("ACCOUNT_NOT_FOUND", "Account not found")
    return build_view(conn, store.create(account_id, dataset_sha(conn)))


def get_cart(conn: sqlite3.Connection, store: MemoryStore, cart_id: str) -> dict:
    return build_view(conn, load(store, cart_id))


def _line_for(conn: sqlite3.Connection, cart: Cart, line_id: str) -> sqlite3.Row:
    if cart.account_id is None:
        raise invalid("ACCOUNT_REQUIRED", "Create the cart with an account_id to use line_id")
    row = conn.execute(
        "SELECT line_id, plan_sku, device_sku, tradein_eligible FROM lines WHERE line_id = ? AND account_id = ?",
        (line_id, cart.account_id),
    ).fetchone()
    if row is None:
        raise not_found("LINE_NOT_FOUND", "Line not found on this account")
    return row


def _existing_lines(conn: sqlite3.Connection, cart: Cart) -> int:
    if cart.account_id is None:
        return 0
    return conn.execute("SELECT COUNT(*) FROM lines WHERE account_id = ?", (cart.account_id,)).fetchone()[0]


def _check_line_limits(plan: sqlite3.Row, lines: int) -> None:
    if plan["max_lines"] is not None and lines > plan["max_lines"]:
        raise invalid("PLAN_LINE_LIMIT", f"{plan['name']} allows at most {plan['max_lines']} lines")
    if lines < plan["min_lines"]:
        raise invalid("PLAN_LINE_LIMIT", f"{plan['name']} requires at least {plan['min_lines']} lines")


def _check_plan_rules(conn: sqlite3.Connection, cart: Cart, kind: str, sku: str) -> None:
    """A plan can be sold only to eligible households with an allowed number of lines (new lines in the cart count)."""
    plan = catalog.get_plan(conn, sku)
    if cart.account_id is not None:
        group = conn.execute(
            "SELECT discount_group FROM accounts WHERE account_id = ?", (cart.account_id,)
        ).fetchone()[0]
        if plan["eligibility"] and plan["eligibility"] != group:
            raise invalid("PLAN_NOT_ELIGIBLE", f"{plan['name']} requires a {plan['eligibility']} account")
    lines = _existing_lines(conn, cart) + sum(1 for i in cart.items if i.kind == "new_line")
    _check_line_limits(plan, lines + (1 if kind == "new_line" else 0))


def validate_line_limits(conn: sqlite3.Connection, cart: Cart) -> None:
    """At checkout, every plan and new_line item must still fit the household's final line count."""
    lines = _existing_lines(conn, cart) + sum(1 for i in cart.items if i.kind == "new_line")
    for item in cart.items:
        if item.kind in ("plan", "new_line"):
            _check_line_limits(catalog.get_plan(conn, item.sku), lines)


def _plan_families(conn: sqlite3.Connection, cart: Cart) -> set[str]:
    """Plan families the household would have: its current lines plus plans in the cart."""
    skus = [i.sku for i in cart.items if i.kind in ("plan", "new_line")]
    if cart.account_id is not None:
        skus += [r[0] for r in conn.execute("SELECT plan_sku FROM lines WHERE account_id = ?", (cart.account_id,))]
    return {p["family"] for p in (catalog.get_plan(conn, s) for s in skus) if p}


def _check_addon_rules(conn: sqlite3.Connection, cart: Cart, addon: dict, line: sqlite3.Row | None) -> None:
    families = addon["eligible_families"]
    if families and not set(families) & _plan_families(conn, cart):
        raise invalid("ADDON_NOT_ELIGIBLE", f"{addon['name']} requires a {' or '.join(families)} plan")
    if addon["kind"] == "protection":
        protection.check_protection(conn, cart, addon, line["line_id"] if line is not None else None)


def _check_sku(conn: sqlite3.Connection, kind: str, sku: str | None) -> str:
    lookup = {"device": catalog.get_device, "plan": catalog.get_plan, "new_line": catalog.get_plan,
              "addon": catalog.get_addon}[kind]
    found = None if sku is None else lookup(conn, sku)
    if found is None:
        raise not_found("SKU_NOT_FOUND", f"No {kind} with that sku")
    if kind == "device" and found["status"] != "current":
        raise invalid("DEVICE_DISCONTINUED", "That device is no longer sold; see GET /v1/catalog/devices")
    return sku


def _validated_item(
    conn: sqlite3.Connection, store: MemoryStore, cart: Cart, kind: str, sku: str | None, line_id: str | None,
    quantity: int, payment: str, condition: str, port_in: bool = False,
) -> CartItem:
    if kind not in KINDS:
        raise invalid("INVALID_ITEM", f"kind must be one of {list(KINDS)}")
    if payment not in PAYMENTS:
        raise invalid("INVALID_ITEM", f"payment must be one of {list(PAYMENTS)}")
    if condition not in pricing.CONDITION_MULTIPLIER:
        raise invalid("INVALID_CONDITION", f"condition must be one of {sorted(pricing.CONDITION_MULTIPLIER)}")
    if port_in and kind != "new_line":
        raise invalid("INVALID_ITEM", "port_in only applies to new_line items")
    if kind == "new_line" and line_id:
        raise invalid("INVALID_ITEM", "new_line items must not name an existing line")
    if kind in ("plan", "tradein") and not line_id:
        raise invalid("INVALID_ITEM", f"{kind} items require line_id")
    line = _line_for(conn, cart, line_id) if line_id else None
    if kind == "tradein":
        if not line["tradein_eligible"]:
            raise invalid("NOT_TRADEIN_ELIGIBLE", "That line has no eligible device to trade in")
        if store.is_traded_in(line_id):
            raise conflict("TRADEIN_ALREADY_USED", "That line's device was already traded in on an order")
        sku = line["device_sku"]
    else:
        sku = _check_sku(conn, kind, sku)
    if quantity > 1 and not _is_accessory(conn, kind, sku):  # cheap input checks before any cart-state rules
        raise invalid("INVALID_ITEM", "quantity above 1 is only allowed for accessories")
    if kind in ("plan", "new_line"):
        _check_plan_rules(conn, cart, kind, sku)
    if kind == "addon":
        _check_addon_rules(conn, cart, catalog.get_addon(conn, sku), line)
    if kind == "plan" and sku == line["plan_sku"]:
        raise invalid("INVALID_ITEM", "That line is already on this plan")
    if kind == "addon" and not _may_repeat(conn, sku) and any(
        i.kind == "addon" and i.sku == sku for i in cart.items
    ):
        raise conflict("DUPLICATE_ITEM", "This cart already has that add-on")
    if kind in ONE_PER_LINE and line_id and any(i.kind == kind and i.line_id == line_id for i in cart.items):
        raise conflict("DUPLICATE_ITEM", f"This cart already has a {kind} item for that line")
    return CartItem(new_id("ITM", 8), kind, sku, line_id, quantity, payment, condition, port_in)


def _may_repeat(conn: sqlite3.Connection, sku: str) -> bool:
    """Accessories repeat freely; protection repeats once per phone (the coverage rule limits it)."""
    return (catalog.get_addon(conn, sku) or {}).get("kind") in ("accessory", "protection")


def _is_accessory(conn: sqlite3.Connection, kind: str, sku: str) -> bool:
    return kind == "addon" and (catalog.get_addon(conn, sku) or {}).get("kind") == "accessory"


def add_item(
    conn: sqlite3.Connection, store: MemoryStore, cart_id: str, kind: str, sku: str | None = None,
    line_id: str | None = None, quantity: int = 1, payment: str = "financed", condition: str = "good",
    port_in: bool = False,
) -> dict:
    with store.lock:
        cart = load(store, cart_id)
        if cart.status != "open":
            raise conflict("CART_CLOSED", "This cart has already been checked out")
        if len(cart.items) >= MAX_ITEMS:
            raise invalid("CART_FULL", f"A cart holds at most {MAX_ITEMS} items")
        item = _validated_item(conn, store, cart, kind, sku, line_id, quantity, payment, condition, port_in)
        updated = cart.with_item(item)
        view = build_view(conn, updated)  # price first: a cart that cannot be priced is never stored
        store.save(updated)
    return view


def remove_item(conn: sqlite3.Connection, store: MemoryStore, cart_id: str, item_id: str) -> dict:
    with store.lock:
        cart = load(store, cart_id)
        if cart.status != "open":
            raise conflict("CART_CLOSED", "This cart has already been checked out")
        if not any(i.item_id == item_id for i in cart.items):
            raise not_found("ITEM_NOT_FOUND", "Item not found in this cart")
        updated = cart.without_item(item_id)
        view = build_view(conn, updated)
        store.save(updated)
    return view
