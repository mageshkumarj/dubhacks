import sqlite3

FINANCING_MONTHS = 24  # 0% APR installment: the regular payment is floored, the final payment absorbs the rest


def _device(row: sqlite3.Row) -> dict:
    return {
        "sku": row["sku"], "name": row["name"], "manufacturer": row["manufacturer"], "tier": row["tier"],
        "storage_gb": row["storage_gb"], "msrp_cents": row["msrp_cents"], "release_date": row["release_date"],
        "status": row["status"], "protection_tier": row["protection_tier"],
        "installment_24_cents": row["msrp_cents"] // FINANCING_MONTHS,
    }


def _plan(row: sqlite3.Row) -> dict:
    prices = [int(p) for p in row["line_prices"].split(",")]
    totals = [sum(prices[: n + 1]) for n in range(len(prices))]
    return {
        "sku": row["sku"], "name": row["name"], "family": row["family"], "variant": row["variant"],
        "tier": row["tier"], "line_prices_cents": prices, "extra_line_cents": row["extra_line_cents"],
        "total_for_lines_cents": totals, "min_lines": row["min_lines"], "max_lines": row["max_lines"],
        "data_cap_gb": row["data_cap_gb"], "hotspot_high_speed_gb": row["hotspot_high_speed_gb"],
        "hotspot_unlimited": bool(row["hotspot_unlimited"]), "canada_mexico_gb": row["canada_mexico_gb"],
        "intl_data_gb": row["intl_data_gb"], "video_quality": row["video_quality"],
        "price_guarantee_years": row["price_guarantee_years"], "priority_network": bool(row["priority_network"]),
        "prices_include_autopay": bool(row["prices_include_autopay"]),
        "device_connection_cents": row["device_connection_cents"], "eligibility": row["eligibility"],
        "perks": row["perks"].split(",") if row["perks"] else [], "upgrade_note": row["upgrade_note"],
        "status": row["status"],
    }


def list_devices(
    conn: sqlite3.Connection, tier: str | None = None, manufacturer: str | None = None,
    limit: int = 50, offset: int = 0, status: str | None = "current",
) -> tuple[list[dict], int]:
    """`status=None` returns current and legacy devices; legacy devices are not for sale."""
    where = "WHERE (? IS NULL OR tier = ?) AND (? IS NULL OR manufacturer = ?) AND (? IS NULL OR status = ?)"
    params = (tier, tier, manufacturer, manufacturer, status, status)
    total = conn.execute(f"SELECT COUNT(*) FROM devices {where}", params).fetchone()[0]  # noqa: S608
    rows = conn.execute(
        f"SELECT * FROM devices {where} ORDER BY sku LIMIT ? OFFSET ?", (*params, limit, offset)  # noqa: S608
    )
    return [_device(r) for r in rows], total


def get_device(conn: sqlite3.Connection, sku: str) -> dict | None:
    row = conn.execute("SELECT * FROM devices WHERE sku = ?", (sku,)).fetchone()
    return None if row is None else _device(row)


def list_plans(conn: sqlite3.Connection) -> list[dict]:
    return [_plan(r) for r in conn.execute("SELECT * FROM plans ORDER BY rowid")]


def get_plan(conn: sqlite3.Connection, sku: str) -> dict | None:
    row = conn.execute("SELECT * FROM plans WHERE sku = ?", (sku,)).fetchone()
    return None if row is None else _plan(row)


_ADDON_COLUMNS = (
    "sku, name, kind, monthly_cents, one_time_cents, per, description, eligible_families, protection_tier, "
    "compatible_device_skus, deductible_screen_cents, deductible_damage_cents, deductible_loss_theft_cents"
)


def _addon(row: sqlite3.Row) -> dict:
    split = lambda value: value.split(",") if value else None  # noqa: E731
    return {
        "sku": row["sku"], "name": row["name"], "kind": row["kind"], "monthly_cents": row["monthly_cents"],
        "one_time_cents": row["one_time_cents"], "per": row["per"], "description": row["description"],
        "eligible_families": split(row["eligible_families"]), "protection_tier": row["protection_tier"],
        "compatible_device_skus": split(row["compatible_device_skus"]),
        "deductible_screen_cents": row["deductible_screen_cents"],
        "deductible_damage_cents": row["deductible_damage_cents"],
        "deductible_loss_theft_cents": row["deductible_loss_theft_cents"],
    }


def list_addons(conn: sqlite3.Connection, kind: str | None = None) -> list[dict]:
    rows = conn.execute(
        f"SELECT {_ADDON_COLUMNS} FROM addons WHERE (? IS NULL OR kind = ?) ORDER BY rowid",  # noqa: S608
        (kind, kind),
    )
    return [_addon(r) for r in rows]


def get_addon(conn: sqlite3.Connection, sku: str) -> dict | None:
    row = conn.execute(f"SELECT {_ADDON_COLUMNS} FROM addons WHERE sku = ?", (sku,)).fetchone()  # noqa: S608
    return None if row is None else _addon(row)


_PROMO_LISTS = ("device_skus", "plan_families", "plan_variants", "discount_groups", "credit_tiers")
_PROMO_FLAGS = (
    "requires_new_line", "requires_port_in", "requires_tradein", "new_line_or_tradein", "requires_device",
    "requires_byod", "discount_plan_only",
)
_PROMO_PLAIN = (
    "sku", "name", "kind", "value_cents", "source", "payout_months", "per", "max_units", "min_plan_cents",
    "min_lines", "min_tenure_months", "min_device_age_months", "min_support_contacts_90d", "requires_addon_kind",
    "min_accessories", "percent_off", "description",
)


def _promotion(row: sqlite3.Row) -> dict:
    out = {key: row[key] for key in _PROMO_PLAIN}
    out.update({key: bool(row[key]) for key in _PROMO_FLAGS})
    out.update({key: row[key].split(",") if row[key] else None for key in _PROMO_LISTS})
    return out


def list_promotions(conn: sqlite3.Connection, source: str | None = None) -> list[dict]:
    rows = conn.execute("SELECT * FROM promotions WHERE (? IS NULL OR source = ?) ORDER BY rowid", (source, source))
    return [_promotion(r) for r in rows]
