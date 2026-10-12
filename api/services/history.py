import sqlite3

from .common import account_exists

MAX_MONTHS = 12


def _line_belongs(conn: sqlite3.Connection, account_id: str, line_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM lines WHERE line_id = ? AND account_id = ?", (line_id, account_id)
    ).fetchone() is not None


def get_usage(
    conn: sqlite3.Connection, account_id: str, line_id: str | None = None, months: int = MAX_MONTHS
) -> list[dict] | None:
    if not account_exists(conn, account_id):
        return None
    if line_id is not None and not _line_belongs(conn, account_id, line_id):
        return None
    params = (account_id, line_id, line_id, months)
    rows = conn.execute(
        "SELECT u.line_id, u.month, u.data_gb, u.voice_minutes, u.streaming_hours, u.hotspot_gb "
        "FROM usage_monthly u JOIN lines l USING (line_id) "
        "WHERE l.account_id = ? AND (? IS NULL OR u.line_id = ?) "
        "AND u.month IN (SELECT month FROM usage_monthly WHERE line_id = u.line_id "
        "ORDER BY month DESC LIMIT ?) ORDER BY u.line_id, u.month",
        params,
    )
    return [dict(r) for r in rows]


def get_billing(conn: sqlite3.Connection, account_id: str) -> list[dict] | None:
    if not account_exists(conn, account_id):
        return None
    rows = conn.execute(
        "SELECT month, total_cents, change_cents, change_reason FROM billing_history "
        "WHERE account_id = ? ORDER BY month",
        (account_id,),
    )
    return [dict(r) for r in rows]


def get_support_interactions(conn: sqlite3.Connection, account_id: str, limit: int = 50) -> list[dict] | None:
    if not account_exists(conn, account_id):
        return None
    rows = conn.execute(
        "SELECT interaction_id, interaction_date, channel, topic, sentiment, resolved "
        "FROM support_interactions WHERE account_id = ? ORDER BY interaction_date DESC, interaction_id DESC LIMIT ?",
        (account_id, limit),
    )
    return [{**dict(r), "resolved": bool(r["resolved"])} for r in rows]
