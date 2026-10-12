"""Aggregated, low-latency view of a customer: what the website, app, store, care and AI assistants share."""

import sqlite3
from datetime import date

from .common import SUPPORT_WINDOW_DAYS, TRADEIN_MAX_AGE, as_of, months_between, services_for

UPGRADE_MIN_DEVICE_AGE_MONTHS = 12  # stub rule: owned 12+ months (half of a 24-month installment plan)


def _financing(row: sqlite3.Row) -> dict | None:
    if row["byod"]:
        return None
    return {
        "balance_cents": row["financing_balance_cents"],
        "months_remaining": row["financing_months_remaining"],
        "monthly_installment_cents": row["monthly_installment_cents"],
        "paid_off": row["financing_balance_cents"] == 0,
    }


def _tradein_value(conn: sqlite3.Connection, device_sku: str, age: int) -> int | None:
    row = conn.execute(
        "SELECT value_cents FROM tradein_curves WHERE device_sku = ? AND age_months = ?",
        (device_sku, min(age, TRADEIN_MAX_AGE)),
    ).fetchone()
    return row[0] if row else None


def _recent_usage_gb(conn: sqlite3.Connection, line_id: str) -> float | None:
    row = conn.execute(
        "SELECT AVG(data_gb) FROM (SELECT data_gb FROM usage_monthly WHERE line_id = ? "
        "ORDER BY month DESC LIMIT 3)",
        (line_id,),
    ).fetchone()
    return None if row[0] is None else round(row[0], 2)


def _line(conn: sqlite3.Connection, row: sqlite3.Row, today: date, protected: set[str]) -> dict:
    device = None
    age = None
    if row["device_sku"]:
        purchased = date.fromisoformat(row["device_purchase_date"])
        age = months_between(purchased, today)
        device = {
            "sku": row["device_sku"], "name": row["device_name"], "tier": row["device_tier"],
            "purchase_date": row["device_purchase_date"], "age_months": age,
        }
    eligible_tradein = bool(row["tradein_eligible"])
    upgrade = age is not None and age >= UPGRADE_MIN_DEVICE_AGE_MONTHS
    return {
        "line_id": row["line_id"], "member_label": row["member_label"], "member_role": row["member_role"],
        "plan_sku": row["plan_sku"], "plan_name": row["plan_name"], "plan_tier": row["plan_tier"],
        "plan_family": row["plan_family"], "plan_variant": row["plan_variant"],
        "plan_data_cap_gb": row["data_cap_gb"], "byod": bool(row["byod"]), "device": device,
        "financing": _financing(row), "has_protection": row["line_id"] in protected,
        "tradein_eligible": eligible_tradein, "upgrade_eligible": upgrade,
        "estimated_tradein_value_cents": (
            _tradein_value(conn, row["device_sku"], age) if device and eligible_tradein else None
        ),
        "usage_3m_avg_gb": _recent_usage_gb(conn, row["line_id"]),
    }


def _billing_summary(conn: sqlite3.Connection, account_id: str) -> dict | None:
    totals = [r[0] for r in conn.execute(
        "SELECT total_cents FROM billing_history WHERE account_id = ? ORDER BY month", (account_id,)
    )]
    if not totals:
        return None
    prior = totals[:-1]
    prior_avg = sum(prior) / len(prior) if prior else 0
    change = round(totals[-1] / prior_avg - 1, 4) if prior_avg else None
    return {"latest_total_cents": totals[-1], "change_pct_vs_prior_avg": change, "months_available": len(totals)}


def _support_summary(conn: sqlite3.Connection, account_id: str, today: date) -> dict:
    recent = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(1 - resolved), 0) FROM support_interactions "
        "WHERE account_id = ? AND interaction_date >= date(?, ?)",
        (account_id, today.isoformat(), f"-{SUPPORT_WINDOW_DAYS} day"),
    ).fetchone()
    overall = conn.execute(
        "SELECT MAX(interaction_date), AVG(sentiment) FROM support_interactions WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return {
        "contacts_90d": recent[0], "unresolved_90d": recent[1], "last_contact_date": overall[0],
        "avg_sentiment": None if overall[1] is None else round(overall[1], 3),
    }


def get_context(conn: sqlite3.Connection, account_id: str) -> dict | None:
    account = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    if account is None:
        return None
    today = as_of(conn)
    rows = conn.execute(
        "SELECT l.*, p.name AS plan_name, p.tier AS plan_tier, p.family AS plan_family, "
        "p.variant AS plan_variant, p.data_cap_gb, "
        "d.name AS device_name, d.tier AS device_tier FROM lines l JOIN plans p ON p.sku = l.plan_sku "
        "LEFT JOIN devices d ON d.sku = l.device_sku WHERE l.account_id = ? ORDER BY l.line_id",
        (account_id,),
    ).fetchall()
    protected = {r[0] for r in conn.execute(
        "SELECT la.line_id FROM line_addons la JOIN addons a ON a.sku = la.addon_sku "
        "JOIN lines l USING (line_id) WHERE l.account_id = ? AND a.kind = 'protection'", (account_id,)
    )}
    lines = [_line(conn, r, today, protected) for r in rows]
    signal = conn.execute("SELECT * FROM account_signals WHERE account_id = ?", (account_id,)).fetchone()
    signals = None if signal is None else {
        "competitor_research_score": signal["competitor_research_score"],
        "port_out_inquiry": bool(signal["port_out_inquiry"]),
        "app_sessions_30d": signal["app_sessions_30d"],
    }
    return {
        "as_of": today.isoformat(), "account_id": account_id, "segment": account["segment"],
        "tenure_months": account["tenure_months"], "language": account["language"],
        "contact_preference": account["contact_preference"], "credit_tier": account["credit_tier"],
        "autopay": bool(account["autopay"]), "discount_group": account["discount_group"],
        "persona_note": account["persona_note"],
        "services": services_for(conn, account_id), "lines": lines,
        "billing": _billing_summary(conn, account_id),
        "support": _support_summary(conn, account_id, today),
        "signals": signals,
        "eligibility": {
            "line_count": len(lines),
            "upgrade_eligible_lines": sum(line["upgrade_eligible"] for line in lines),
            "tradein_eligible_lines": sum(line["tradein_eligible"] for line in lines),
        },
    }
