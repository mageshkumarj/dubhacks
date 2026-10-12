import sqlite3

from .common import services_for

_SUMMARY_SQL = (
    "SELECT a.account_id, a.segment, a.tenure_months, a.language, a.persona_note, "
    "(SELECT COUNT(*) FROM lines l WHERE l.account_id = a.account_id) AS line_count FROM accounts a"
)


def list_accounts(
    conn: sqlite3.Connection,
    segment: str | None = None,
    persona_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    clauses, params = [], []
    if segment is not None:
        clauses.append("a.segment = ?")
        params.append(segment)
    if persona_only:
        clauses.append("a.persona_note IS NOT NULL")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    total = conn.execute(f"SELECT COUNT(*) FROM accounts a{where}", params).fetchone()[0]  # noqa: S608
    rows = conn.execute(
        f"{_SUMMARY_SQL}{where} ORDER BY a.account_id LIMIT ? OFFSET ?",  # noqa: S608
        (*params, limit, offset),
    )
    return [dict(r) for r in rows], total


def get_household(conn: sqlite3.Connection, account_id: str) -> dict | None:
    account = conn.execute(
        "SELECT account_id, segment, tenure_months, language, contact_preference, credit_tier, "
        "autopay, discount_group, persona_note FROM accounts WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    if account is None:
        return None
    lines = conn.execute(
        "SELECT l.line_id, l.member_label, l.member_role, l.plan_sku, p.name AS plan_name, "
        "p.tier AS plan_tier, l.device_sku, d.name AS device_name, l.byod FROM lines l "
        "JOIN plans p ON p.sku = l.plan_sku LEFT JOIN devices d ON d.sku = l.device_sku "
        "WHERE l.account_id = ? ORDER BY l.line_id",
        (account_id,),
    ).fetchall()
    addons = {}
    for r in conn.execute(
        "SELECT la.line_id, la.addon_sku FROM line_addons la JOIN lines l USING (line_id) "
        "WHERE l.account_id = ? ORDER BY la.addon_sku",
        (account_id,),
    ):
        addons.setdefault(r["line_id"], []).append(r["addon_sku"])
    return {
        **dict(account),
        "autopay": bool(account["autopay"]),
        "lines": [{**dict(r), "byod": bool(r["byod"]), "addons": addons.get(r["line_id"], [])} for r in lines],
        "services": services_for(conn, account_id),
    }

