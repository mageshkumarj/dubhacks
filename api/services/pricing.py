"""Financing quotes and trade-in values. Stub economics: not an offer."""

import sqlite3

from ..errors import invalid
from .common import TRADEIN_MAX_AGE
from .money import half_up

CONDITION_MULTIPLIER = {"good": 1.0, "fair": 0.75, "poor": 0.4}
TERMS = (12, 24, 36)
# credit tier -> (APR, minimum down payment as a share of the amount after trade-in credit)
CREDIT_TERMS = {"prime": (0.0, 0.0), "near_prime": (0.049, 0.10), "subprime": (0.099, 0.20)}


def credit_tier_for(conn: sqlite3.Connection, account_id: str) -> str | None:
    row = conn.execute("SELECT credit_tier FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    return None if row is None else row[0]


def _curve_value(conn: sqlite3.Connection, device_sku: str, age: int) -> int | None:
    row = conn.execute(
        "SELECT value_cents FROM tradein_curves WHERE device_sku = ? AND age_months = ?", (device_sku, age)
    ).fetchone()
    return None if row is None else row[0]


def tradein_value(conn: sqlite3.Connection, device_sku: str, age_months: int, condition: str) -> dict | None:
    if condition not in CONDITION_MULTIPLIER:
        raise invalid("INVALID_CONDITION", f"condition must be one of {sorted(CONDITION_MULTIPLIER)}")
    if not 0 <= age_months <= TRADEIN_MAX_AGE:
        raise invalid("INVALID_AGE", f"age_months must be between 0 and {TRADEIN_MAX_AGE}")
    base = _curve_value(conn, device_sku, age_months)
    if base is None:
        return None
    return {
        "device_sku": device_sku, "age_months": age_months, "condition": condition,
        "base_value_cents": base, "value_cents": round(base * CONDITION_MULTIPLIER[condition]),
    }


def tradein_curve(conn: sqlite3.Connection, device_sku: str) -> list[dict] | None:
    rows = conn.execute(
        "SELECT age_months, value_cents FROM tradein_curves WHERE device_sku = ? ORDER BY age_months",
        (device_sku,),
    ).fetchall()
    return [dict(r) for r in rows] or None


def _monthly_payment(principal: int, apr: float, term: int) -> int:
    if principal == 0:
        return 0
    if apr == 0:
        return principal // term
    rate = apr / 12
    return half_up(principal * rate / (1 - (1 + rate) ** -term))


def _validate_quote_inputs(credit_tier: str, term: int, down: int, credit: int) -> None:
    if credit_tier not in CREDIT_TERMS:
        raise invalid("INVALID_CREDIT_TIER", f"credit_tier must be one of {sorted(CREDIT_TERMS)}")
    if term not in TERMS:
        raise invalid("INVALID_TERM", f"term_months must be one of {list(TERMS)}")
    if down < 0 or credit < 0:
        raise invalid("INVALID_AMOUNT", "down_payment_cents and tradein_credit_cents must not be negative")


def min_down_payment(credit_tier: str, price_after_credit: int) -> int:
    return half_up(CREDIT_TERMS[credit_tier][1] * price_after_credit)


def financing_quote(
    conn: sqlite3.Connection, device_sku: str, credit_tier: str, term_months: int = 24,
    down_payment_cents: int = 0, tradein_credit_cents: int = 0,
) -> dict | None:
    row = conn.execute("SELECT msrp_cents FROM devices WHERE sku = ?", (device_sku,)).fetchone()
    if row is None:
        return None
    _validate_quote_inputs(credit_tier, term_months, down_payment_cents, tradein_credit_cents)
    msrp = row[0]
    if down_payment_cents + tradein_credit_cents > msrp:
        raise invalid("CREDIT_EXCEEDS_PRICE", "down payment plus trade-in credit exceeds the device price")
    minimum = min_down_payment(credit_tier, msrp - tradein_credit_cents)
    if down_payment_cents < minimum:
        raise invalid("DOWN_PAYMENT_TOO_LOW", f"{credit_tier} credit requires at least {minimum} cents down")
    apr = CREDIT_TERMS[credit_tier][0]
    financed = msrp - tradein_credit_cents - down_payment_cents
    payment = _monthly_payment(financed, apr, term_months)
    final = financed - payment * (term_months - 1) if apr == 0 else payment
    total_payments = payment * (term_months - 1) + final
    return {
        "device_sku": device_sku, "credit_tier": credit_tier, "msrp_cents": msrp,
        "tradein_credit_cents": tradein_credit_cents, "down_payment_cents": down_payment_cents,
        "min_down_payment_cents": minimum, "amount_financed_cents": financed, "term_months": term_months,
        "apr": apr, "monthly_payment_cents": payment, "final_payment_cents": final,
        "total_interest_cents": total_payments - financed,
        "total_cost_cents": down_payment_cents + total_payments,
    }
