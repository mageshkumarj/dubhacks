import json
import sqlite3


def _persona(row: sqlite3.Row) -> dict:
    return {
        "persona_id": row["persona_id"], "account_id": row["account_id"], "kind": row["kind"],
        "title": row["title"], "primary_theme": row["primary_theme"],
        "secondary_themes": row["secondary_themes"].split(",") if row["secondary_themes"] else [],
        "scenario": row["scenario"], "stated_lines": row["stated_lines"],
        "stated_budget_cents": row["stated_budget_cents"], "stated_usage": row["stated_usage"],
        "stated_notes": row["stated_notes"],
        "starting_cart": json.loads(row["starting_cart"]) if row["starting_cart"] else [],
        "related_account_id": row["related_account_id"],
    }


def list_personas(
    conn: sqlite3.Connection, theme: str | None = None, kind: str | None = None, include_secondary: bool = False,
    limit: int = 50, offset: int = 0,
) -> tuple[list[dict], int]:
    """Personas filtered by theme (primary only, or also those that list it as a secondary theme) and kind."""
    secondary = 1 if include_secondary else 0
    where = (
        "WHERE (:theme IS NULL OR primary_theme = :theme "
        "OR (:secondary = 1 AND instr(',' || IFNULL(secondary_themes, '') || ',', ',' || :theme || ',') > 0)) "
        "AND (:kind IS NULL OR kind = :kind)"
    )
    params = {"theme": theme, "kind": kind, "secondary": secondary}
    total = conn.execute(f"SELECT COUNT(*) FROM personas {where}", params).fetchone()[0]  # noqa: S608
    rows = conn.execute(
        f"SELECT * FROM personas {where} ORDER BY persona_id LIMIT :limit OFFSET :offset",  # noqa: S608
        {**params, "limit": limit, "offset": offset},
    )
    return [_persona(r) for r in rows], total


def get_persona(conn: sqlite3.Connection, persona_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM personas WHERE persona_id = ?", (persona_id,)).fetchone()
    return None if row is None else _persona(row)
