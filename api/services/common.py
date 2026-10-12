import sqlite3
from datetime import date

SUPPORT_WINDOW_DAYS = 90
TRADEIN_MAX_AGE = 60


def as_of(conn: sqlite3.Connection) -> date:
    value = conn.execute("SELECT value FROM metadata WHERE key = 'as_of'").fetchone()
    return date.fromisoformat(value[0])


def months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def account_exists(conn: sqlite3.Connection, account_id: str) -> bool:
    return conn.execute("SELECT 1 FROM accounts WHERE account_id = ?", (account_id,)).fetchone() is not None


def services_for(conn: sqlite3.Connection, account_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT a.sku, a.name, a.kind, a.monthly_cents FROM account_addons aa "
        "JOIN addons a ON a.sku = aa.addon_sku WHERE aa.account_id = ? ORDER BY a.sku",
        (account_id,),
    )
    return [dict(r) for r in rows]


def line_price(prices: str, extra_line_cents: int, position: int) -> int:
    """Marginal monthly price of the line at this 0-based position (prices is stored as '10500,7500,...')."""
    table = [int(p) for p in prices.split(",")]
    return table[position] if position < len(table) else extra_line_cents


def dataset_sha(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM metadata WHERE key = 'content_sha256'").fetchone()
    return "" if row is None else row[0]
