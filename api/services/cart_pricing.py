"""Price a cart: what is due today, what is added monthly, and how trade-in credit is applied.

Rules (stub, documented in the README): trade-in credit is applied to the first device in the cart; a
financed device pays the minimum down payment for the customer's credit tier today and the rest monthly
over 24 months; a plan change charges the difference; a new line is priced by its position in the household.
"""

import sqlite3
from datetime import date

from ..errors import conflict
from . import pricing
from .common import TRADEIN_MAX_AGE, as_of, dataset_sha, line_price, months_between
from .store import Cart, CartItem

TERM = 24


def _lines(conn: sqlite3.Connection, account_id: str | None) -> list[sqlite3.Row]:
    if account_id is None:
        return []
    return conn.execute(
        "SELECT line_id, plan_sku, device_sku, device_purchase_date, tradein_eligible FROM lines "
        "WHERE account_id = ? ORDER BY rowid",
        (account_id,),
    ).fetchall()


def _plan_price(conn: sqlite3.Connection, sku: str, position: int) -> int:
    row = conn.execute("SELECT line_prices, extra_line_cents FROM plans WHERE sku = ?", (sku,)).fetchone()
    return line_price(row["line_prices"], row["extra_line_cents"], position)


def _name(conn: sqlite3.Connection, item: CartItem) -> str:
    table = {"device": "devices", "plan": "plans", "new_line": "plans", "addon": "addons", "tradein": "devices"}
    return conn.execute(f"SELECT name FROM {table[item.kind]} WHERE sku = ?", (item.sku,)).fetchone()[0]  # noqa: S608


def _tradein_value(conn: sqlite3.Connection, item: CartItem, line: sqlite3.Row, today: date) -> int:
    age = months_between(date.fromisoformat(line["device_purchase_date"]), today)
    value = pricing.tradein_value(conn, line["device_sku"], max(0, min(age, TRADEIN_MAX_AGE)), item.condition)
    return 0 if value is None else value["value_cents"]


def _financed_device(conn: sqlite3.Connection, sku: str, tier: str, credit: int) -> tuple[int, int]:
    msrp = conn.execute("SELECT msrp_cents FROM devices WHERE sku = ?", (sku,)).fetchone()[0]
    down = pricing.min_down_payment(tier, msrp - credit)
    quote = pricing.financing_quote(conn, sku, tier, TERM, down, credit)
    return down, quote["monthly_payment_cents"]


def _device_amounts(conn: sqlite3.Connection, item: CartItem, tier: str, credit: int) -> tuple[int, int]:
    if item.payment == "full":
        msrp = conn.execute("SELECT msrp_cents FROM devices WHERE sku = ?", (item.sku,)).fetchone()[0]
        return msrp - credit, 0
    return _financed_device(conn, item.sku, tier, credit)


def _addon_amounts(conn: sqlite3.Connection, item: CartItem) -> tuple[int, int]:
    row = conn.execute("SELECT monthly_cents, one_time_cents FROM addons WHERE sku = ?", (item.sku,)).fetchone()
    return row["one_time_cents"] * item.quantity, row["monthly_cents"] * item.quantity


def _view_item(item: CartItem, name: str, due: int, monthly: int, earned: int, applied: int) -> dict:
    is_device = item.kind == "device"
    return {
        "item_id": item.item_id, "kind": item.kind, "sku": item.sku, "name": name, "line_id": item.line_id,
        "quantity": item.quantity, "payment": item.payment if is_device else None,
        "condition": item.condition if item.kind == "tradein" else None, "port_in": item.port_in,
        "due_today_cents": due, "monthly_cents": monthly,
        "credit_earned_cents": earned, "credit_applied_cents": applied,
    }


def build_view(conn: sqlite3.Connection, cart: Cart) -> dict:
    if cart.dataset_sha and cart.dataset_sha != dataset_sha(conn):
        raise conflict("CART_STALE", "The dataset changed since this cart was created; create a new cart")
    today = as_of(conn)
    lines = _lines(conn, cart.account_id)
    by_id = {r["line_id"]: (i, r) for i, r in enumerate(lines)}
    tier = (pricing.credit_tier_for(conn, cart.account_id) if cart.account_id else None) or "prime"
    credits = {
        i.item_id: _tradein_value(conn, i, by_id[i.line_id][1], today) for i in cart.items if i.kind == "tradein"
    }
    total_credit = sum(credits.values())
    first_device = next((i.item_id for i in cart.items if i.kind == "device"), None)
    new_lines, applied, views = 0, 0, []
    for item in cart.items:
        due = monthly = earned = applied_here = 0
        if item.kind == "device":
            msrp = conn.execute("SELECT msrp_cents FROM devices WHERE sku = ?", (item.sku,)).fetchone()[0]
            applied_here = min(total_credit, msrp) if item.item_id == first_device else 0
            applied += applied_here
            due, monthly = _device_amounts(conn, item, tier, applied_here)
        elif item.kind == "addon":
            due, monthly = _addon_amounts(conn, item)
        elif item.kind == "new_line":
            monthly = _plan_price(conn, item.sku, len(lines) + new_lines)
            new_lines += 1
        elif item.kind == "plan":
            position, line = by_id[item.line_id]
            monthly = _plan_price(conn, item.sku, position) - _plan_price(conn, line["plan_sku"], position)
        else:
            earned = credits[item.item_id]
        views.append(_view_item(item, _name(conn, item), due, monthly, earned, applied_here))
    return {
        "cart_id": cart.cart_id, "account_id": cart.account_id, "status": cart.status, "items": views,
        "totals": {
            "item_count": len(views),
            "due_today_cents": sum(v["due_today_cents"] for v in views),
            "monthly_cents": sum(v["monthly_cents"] for v in views),
            "tradein_credit_cents": total_credit,
            "tradein_credit_applied_cents": applied,
            "tradein_credit_unapplied_cents": total_credit - applied,
        },
    }
