"""Promotion eligibility with reasons, and savings estimates, in the context of a customer and a cart."""

import sqlite3
from dataclasses import dataclass
from datetime import date

from ..errors import conflict, not_found
from .common import SUPPORT_WINDOW_DAYS, as_of, months_between
from .money import half_up
from .store import Cart, MemoryStore

ONGOING_HORIZON_MONTHS = 12  # an open-ended monthly credit is valued over one year in savings estimates
DEVICE_ATTACHED = ("device_credit", "prepaid_card")


@dataclass(frozen=True)
class Facts:
    """Everything a promotion rule can look at: the account, its history, and the cart."""

    account: sqlite3.Row | None
    lines: int  # household lines including new lines and connected lines in the cart
    new_lines: int
    port_in: bool
    devices: tuple[str, ...]
    tradein: bool
    addon_kinds: frozenset[str]
    accessories: int
    accessory_cents: int
    plans: tuple[sqlite3.Row, ...]  # plans that would qualify: the cart's plans, else the account's
    oldest_device_age: int | None
    support_contacts: int


def _split(value: str | None) -> list[str]:
    return value.split(",") if value else []


def _plans_for(conn: sqlite3.Connection, skus: list[str]) -> list[sqlite3.Row]:
    return [r for sku in skus for r in conn.execute("SELECT * FROM plans WHERE sku = ?", (sku,))]


def _account_history(
    conn: sqlite3.Connection, account_id: str, today: date
) -> tuple[list[sqlite3.Row], int | None, int]:
    plans = conn.execute(
        "SELECT p.* FROM lines l JOIN plans p ON p.sku = l.plan_sku WHERE l.account_id = ? ORDER BY l.rowid",
        (account_id,),
    ).fetchall()
    dates = [r[0] for r in conn.execute(
        "SELECT device_purchase_date FROM lines WHERE account_id = ? AND device_sku IS NOT NULL", (account_id,)
    )]
    oldest = max((months_between(date.fromisoformat(d), today) for d in dates), default=None)
    contacts = conn.execute(
        "SELECT COUNT(*) FROM support_interactions WHERE account_id = ? AND interaction_date >= date(?, ?)",
        (account_id, today.isoformat(), f"-{SUPPORT_WINDOW_DAYS} day"),
    ).fetchone()[0]
    return plans, oldest, contacts


def _cart_addons(conn: sqlite3.Connection, cart: Cart | None) -> tuple[set[str], int, int, int]:
    kinds: set[str] = set()
    accessories = accessory_cents = connected = 0
    for item in (i for i in (cart.items if cart else ()) if i.kind == "addon"):
        row = conn.execute("SELECT kind, one_time_cents FROM addons WHERE sku = ?", (item.sku,)).fetchone()
        kinds.add(row["kind"])
        connected += item.quantity if row["kind"] == "connected_line" else 0
        if row["kind"] == "accessory":
            accessories += item.quantity
            accessory_cents += row["one_time_cents"] * item.quantity
    return kinds, accessories, accessory_cents, connected


def gather_facts(conn: sqlite3.Connection, account: sqlite3.Row | None, cart: Cart | None) -> Facts:
    today = as_of(conn)
    items = cart.items if cart else ()
    new_lines = [i for i in items if i.kind == "new_line"]
    cart_plan_skus = [i.sku for i in items if i.kind in ("new_line", "plan")]
    plans, oldest, contacts, existing = [], None, 0, 0
    if account is not None:
        plans, oldest, contacts = _account_history(conn, account["account_id"], today)
        existing = len(plans)
    kinds, accessories, accessory_cents, connected = _cart_addons(conn, cart)
    return Facts(
        account=account, lines=existing + len(new_lines) + connected, new_lines=len(new_lines),
        port_in=any(i.port_in for i in new_lines), devices=tuple(i.sku for i in items if i.kind == "device"),
        tradein=any(i.kind == "tradein" for i in items), addon_kinds=frozenset(kinds), accessories=accessories,
        accessory_cents=accessory_cents, plans=tuple(_plans_for(conn, cart_plan_skus) or plans),
        oldest_device_age=oldest, support_contacts=contacts,
    )


def _plan_matches(promo: sqlite3.Row, plan: sqlite3.Row) -> bool:
    families, variants = _split(promo["plan_families"]), _split(promo["plan_variants"])
    first_line = int(plan["line_prices"].split(",")[0])
    return (
        (not families or plan["family"] in families)
        and (not variants or plan["variant"] in variants)
        and (promo["min_plan_cents"] is None or first_line >= promo["min_plan_cents"])
        and (not promo["discount_plan_only"] or plan["eligibility"] is not None)
    )


def _plan_reason(promo: sqlite3.Row) -> str:
    parts = []
    if promo["plan_families"]:
        parts.append(" or ".join(f.replace("_", " ") for f in _split(promo["plan_families"])) + " plan")
    if promo["plan_variants"]:
        parts.append(f"the {' or '.join(_split(promo['plan_variants']))} variant")
    if promo["discount_plan_only"]:
        parts.append("a 55+, partner or community plan")
    if promo["min_plan_cents"]:
        parts.append(f"at least ${promo['min_plan_cents'] / 100:.0f}/month for the first line")
    return "Needs " + ", ".join(parts)


def _device_names(conn: sqlite3.Connection, skus: list[str]) -> str:
    names = [conn.execute("SELECT name FROM devices WHERE sku = ?", (s,)).fetchone()[0] for s in skus]
    return ", ".join(names)


def _qualifying_devices(promo: sqlite3.Row, facts: Facts) -> int:
    allowed = _split(promo["device_skus"])
    return sum(1 for d in facts.devices if not allowed or d in allowed)


def _account_reasons(promo: sqlite3.Row, facts: Facts) -> list[str]:
    reasons, account = [], facts.account
    groups = _split(promo["discount_groups"])
    chosen = account is None and any(p["eligibility"] in groups for p in facts.plans)  # a prospect's chosen plan
    if groups and not chosen and (account is None or account["discount_group"] not in groups):
        reasons.append(f"Only for {' / '.join(groups)} accounts")
    tiers = _split(promo["credit_tiers"])
    tier = account["credit_tier"] if account else "prime"
    if tiers and tier not in tiers:
        reasons.append(f"Requires well-qualified credit ({' or '.join(tiers)}); this account is {tier}")
    tenure = account["tenure_months"] if account else 0
    if promo["min_tenure_months"] and tenure < promo["min_tenure_months"]:
        reasons.append(f"Needs {promo['min_tenure_months']}+ months of tenure (has {tenure})")
    if promo["min_support_contacts_90d"] and facts.support_contacts < promo["min_support_contacts_90d"]:
        reasons.append(f"Needs {promo['min_support_contacts_90d']}+ support contacts in the last 90 days")
    age = promo["min_device_age_months"]
    if age and (facts.oldest_device_age is None or facts.oldest_device_age < age):
        reasons.append(f"Needs a device owned {age}+ months")
    return reasons


def _line_reasons(promo: sqlite3.Row, facts: Facts) -> list[str]:
    reasons = []
    new_line_ok = facts.new_lines > 0 and (not promo["requires_port_in"] or facts.port_in)
    if promo["new_line_or_tradein"]:
        if not (new_line_ok or facts.tradein):
            reasons.append("Add a new line (with a ported-in number) or a trade-in")
    else:
        if promo["requires_new_line"] and facts.new_lines == 0:
            reasons.append("Add a new line to the cart")
        elif promo["requires_port_in"] and not facts.port_in:
            reasons.append("The new line must port in a number from another carrier")
        if promo["requires_tradein"] and not facts.tradein:
            reasons.append("Add a trade-in to the cart")
    if promo["requires_byod"] and facts.new_lines > 0 and facts.devices:
        reasons.append("The new line must use your own phone (no device in the cart)")
    if promo["min_lines"] > facts.lines:
        reasons.append(f"Needs {promo['min_lines']} lines; this household would have {facts.lines}")
    return reasons


def _cart_reasons(conn: sqlite3.Connection, promo: sqlite3.Row, facts: Facts) -> list[str]:
    reasons = []
    allowed = _split(promo["device_skus"])
    if allowed and not _qualifying_devices(promo, facts):
        reasons.append(f"Add one of these devices: {_device_names(conn, allowed)}")
    elif promo["requires_device"] and not facts.devices:
        reasons.append("Add a device to the cart")
    if promo["per"] == "device" and promo["max_units"] and _qualifying_devices(promo, facts) > promo["max_units"]:
        reasons.append(f"At most {promo['max_units']} devices can receive this offer")
    if promo["requires_addon_kind"] and promo["requires_addon_kind"] not in facts.addon_kinds:
        reasons.append(f"Add a {promo['requires_addon_kind'].replace('_', ' ')} add-on to the cart")
    if promo["min_accessories"] and facts.accessories < promo["min_accessories"]:
        reasons.append(f"Add {promo['min_accessories']} or more accessories (the cart has {facts.accessories})")
    if (promo["plan_families"] or promo["plan_variants"] or promo["min_plan_cents"] or promo["discount_plan_only"]) \
            and not any(_plan_matches(promo, p) for p in facts.plans):
        reasons.append(_plan_reason(promo))
    return reasons


def savings_cents(promo: sqlite3.Row, facts: Facts) -> int:
    """Estimated value of an eligible promotion. Open-ended monthly credits count for one year."""
    if promo["kind"] == "accessory_discount":
        return half_up(promo["percent_off"] * facts.accessory_cents / 100)
    cap = promo["max_units"]
    if promo["per"] == "device":
        units = min(_qualifying_devices(promo, facts), cap or 99)
    elif promo["per"] == "line":
        units = min(facts.new_lines or facts.lines, cap or 99)
    else:
        units = 1
    months = (promo["payout_months"] or ONGOING_HORIZON_MONTHS) if promo["kind"] == "bill_credit" else 1
    return promo["value_cents"] * units * months


def _result(promo: sqlite3.Row, reasons: list[str], facts: Facts) -> dict:
    return {
        "sku": promo["sku"], "name": promo["name"], "kind": promo["kind"], "value_cents": promo["value_cents"],
        "source": promo["source"], "payout_months": promo["payout_months"], "per": promo["per"],
        "percent_off": promo["percent_off"], "eligible": not reasons, "reasons": reasons,
        "estimated_savings_cents": 0 if reasons else savings_cents(promo, facts),
    }


def evaluate_promotions(
    conn: sqlite3.Connection, account_id: str | None, cart: Cart | None
) -> list[dict] | None:
    account = None
    if account_id is not None:
        account = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
        if account is None:
            return None
    facts = gather_facts(conn, account, cart)
    results = []
    for promo in conn.execute("SELECT * FROM promotions ORDER BY rowid"):
        reasons = _account_reasons(promo, facts) + _line_reasons(promo, facts) + _cart_reasons(conn, promo, facts)
        results.append(_result(promo, reasons, facts))
    return results


def promotions_for(
    conn: sqlite3.Connection, store: MemoryStore, account_id: str | None, cart_id: str | None
) -> list[dict]:
    """Promotions for an account, a cart, or both. A cart's account always wins; a different one is rejected."""
    from . import carts  # local import: carts depends on pricing, not on promotions

    cart = carts.load(store, cart_id) if cart_id else None
    if cart is not None and account_id is not None and account_id != cart.account_id:
        raise conflict("ACCOUNT_MISMATCH", "account_id does not match the cart's account")
    results = evaluate_promotions(conn, account_id or (cart.account_id if cart else None), cart)
    if results is None:
        raise not_found("ACCOUNT_NOT_FOUND", "Account not found")
    return results
