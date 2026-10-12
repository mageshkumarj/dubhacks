"""Assemble the full dataset and write it to a SQLite file."""

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from . import catalog
from .personas import PERSONA_META, PERSONAS
from .population import random_account
from .realize import realize
from .rows import AccountRows
from .util import derived_rng

SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_SEED = 2026
DEFAULT_ACCOUNTS = 5000


def _csv(values: tuple[str, ...] | None) -> str | None:
    return ",".join(values) if values else None


def _promotion_row(p: catalog.Promotion) -> tuple:
    return (
        p.sku, p.name, p.kind, p.value_cents, p.source, p.payout_months, p.per, p.max_units,
        int(p.requires_new_line), int(p.requires_port_in), int(p.requires_tradein), int(p.new_line_or_tradein),
        int(p.requires_device), int(p.requires_byod), _csv(p.device_skus), _csv(p.plan_families),
        _csv(p.plan_variants), p.min_plan_cents, int(p.discount_plan_only), _csv(p.discount_groups),
        _csv(p.credit_tiers), p.min_lines, p.min_tenure_months, p.min_device_age_months,
        p.min_support_contacts_90d, p.requires_addon_kind, p.min_accessories, p.percent_off, p.description,
        catalog.DATA_SOURCE,
    )


def _catalog_rows() -> Iterable[tuple[str, list[tuple]]]:
    yield "devices", [(d.sku, d.name, d.manufacturer, d.tier, d.storage_gb, d.msrp_cents,
                       d.release_date.isoformat(), d.status, d.protection_tier,
                       d.sold_until.isoformat() if d.sold_until else None, catalog.DATA_SOURCE)
                      for d in catalog.DEVICES]
    yield "plans", [(
        p.sku, p.name, p.family, p.variant, p.tier, ",".join(map(str, p.line_prices)), p.extra_line_cents,
        p.min_lines, p.max_lines, p.data_cap_gb, p.hotspot_high_speed_gb, int(p.hotspot_unlimited),
        p.canada_mexico_gb, p.intl_data_gb, p.video_quality, p.price_guarantee_years, int(p.priority_network),
        int(p.prices_include_autopay), p.device_connection_cents, p.eligibility, ",".join(p.perks),
        p.upgrade_note, p.status, catalog.DATA_SOURCE,
    ) for p in catalog.PLANS]
    yield "addons", [(
        a.sku, a.name, a.kind, a.monthly_cents, a.one_time_cents, a.per, a.description,
        ",".join(a.eligible_families) if a.eligible_families else None, a.protection_tier,
        ",".join(a.compatible_devices) if a.compatible_devices else None, a.deductible_screen_cents,
        a.deductible_damage_cents, a.deductible_loss_theft_cents, catalog.DATA_SOURCE,
    ) for a in catalog.ADDONS]
    yield "promotions", [_promotion_row(p) for p in catalog.PROMOTIONS]
    yield "tradein_curves", [(d.sku, age, value) for d in catalog.DEVICES
                             for age, value in catalog.tradein_curve(d)]


def _insert(conn: sqlite3.Connection, table: str, rows: list[tuple]) -> None:
    if not rows:
        return
    marks = ",".join("?" * len(rows[0]))
    conn.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)  # noqa: S608 - fixed table names


def _account_rows(seed: int, accounts: int) -> tuple[AccountRows, ...]:
    personas = tuple(realize(p, derived_rng(seed, "persona", p.account_id)) for p in PERSONAS)
    randoms = tuple(
        realize(random_account(derived_rng(seed, "acct", i), i), derived_rng(seed, "rows", i))
        for i in range(1, accounts + 1)
    )
    return personas + randoms


def _write_accounts(conn: sqlite3.Connection, batch: tuple[AccountRows, ...]) -> None:
    _insert(conn, "accounts", [r.account for r in batch])
    for table, attr in (
        ("lines", "lines"), ("line_addons", "line_addons"), ("account_addons", "account_addons"),
        ("usage_monthly", "usage"), ("billing_history", "billing"),
        ("support_interactions", "support"),
    ):
        _insert(conn, table, [row for r in batch for row in getattr(r, attr)])
    _insert(conn, "account_signals", [r.signals for r in batch])


def content_checksum(conn: sqlite3.Connection) -> str:
    """Hash of every data row (not the file bytes), stable across SQLite and Python builds."""
    digest = hashlib.sha256()
    tables = sorted(
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        if r[0] != "metadata"
    )
    for table in tables:
        digest.update(table.encode())
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2"):  # noqa: S608 - names from sqlite_master
            digest.update(repr(tuple(row)).encode())
    return digest.hexdigest()


def _persona_rows() -> list[tuple]:
    return [
        (
            m.persona_id, m.account_id, m.kind, m.title, m.primary_theme, _csv(m.secondary_themes), m.scenario,
            m.stated_lines, m.stated_budget_cents, m.stated_usage, m.stated_notes,
            json.dumps(list(m.starting_cart)) if m.starting_cart else None, m.related_account_id,
        )
        for m in PERSONA_META
    ]


def _build_into(tmp: Path, seed: int, accounts: int) -> None:
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(SCHEMA.read_text())
        for table, rows in _catalog_rows():
            _insert(conn, table, rows)
        _write_accounts(conn, _account_rows(seed, accounts))
        _insert(conn, "personas", _persona_rows())
        _insert(conn, "metadata", [
            ("data_source", "stub"), ("seed", str(seed)), ("as_of", catalog.AS_OF.isoformat()),
            ("brand", "T-Mobile (stub data, not official)"), ("schema_version", "9"),
            ("content_sha256", content_checksum(conn)),
        ])
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


def build_database(path: Path, seed: int = DEFAULT_SEED, accounts: int = DEFAULT_ACCOUNTS) -> Path:
    """Build into a temp file and move it into place, so a failure never leaves a partial database."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        _build_into(tmp, seed, accounts)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path
