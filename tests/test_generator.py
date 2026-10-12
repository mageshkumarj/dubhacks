import sqlite3
from pathlib import Path

import pytest

from datagen import catalog
from datagen.personas import PERSONA_IDS
from datagen.writer import build_database

SEED = 7
ACCOUNTS = 600


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("db") / "sandbox.db"
    build_database(path, seed=SEED, accounts=ACCOUNTS)
    return path


@pytest.fixture()
def conn(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def test_same_seed_yields_identical_database(tmp_path, db_path):
    other = tmp_path / "other.db"
    build_database(other, seed=SEED, accounts=ACCOUNTS)
    dump = lambda p: "\n".join(sqlite3.connect(p).iterdump())  # noqa: E731
    assert dump(db_path) == dump(other)


def test_different_seed_yields_different_data(tmp_path, db_path):
    other = tmp_path / "other.db"
    build_database(other, seed=SEED + 1, accounts=ACCOUNTS)
    dump = lambda p: "\n".join(sqlite3.connect(p).iterdump())  # noqa: E731
    assert dump(db_path) != dump(other)


def test_account_and_persona_counts(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM accounts") == ACCOUNTS + len(PERSONA_IDS)
    ids = {r[0] for r in conn.execute("SELECT account_id FROM accounts")}
    assert set(PERSONA_IDS) <= ids


def test_every_account_has_at_least_one_line(conn):
    orphans = scalar(
        conn,
        "SELECT COUNT(*) FROM accounts a LEFT JOIN lines l USING(account_id) "
        "WHERE l.line_id IS NULL",
    )
    assert orphans == 0


def test_referential_integrity(conn):
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_lines_reference_catalog_skus(conn):
    plan_skus = {p.sku for p in catalog.PLANS}
    device_skus = {d.sku for d in catalog.DEVICES}
    for row in conn.execute("SELECT plan_sku, device_sku FROM lines"):
        assert row["plan_sku"] in plan_skus
        assert row["device_sku"] is None or row["device_sku"] in device_skus


def test_usage_history_never_predates_the_account(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT u.line_id, COUNT(*) c, MIN(a.tenure_months, 12) want "
        "FROM usage_monthly u JOIN lines l USING(line_id) JOIN accounts a USING(account_id) "
        "GROUP BY u.line_id HAVING c != want)",
    )
    assert bad == 0


def test_billing_history_never_predates_the_account(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT b.account_id, COUNT(*) c, MIN(a.tenure_months, 12) want "
        "FROM billing_history b JOIN accounts a USING(account_id) "
        "GROUP BY b.account_id HAVING c != want)",
    )
    assert bad == 0


def test_support_contacts_never_predate_the_account(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM support_interactions s JOIN accounts a USING(account_id) "
        "WHERE julianday('2026-10-01') - julianday(s.interaction_date) > a.tenure_months * 31",
    )
    assert bad == 0


def test_installments_appear_only_after_purchase(conn):
    """A phone bought 2 months ago must not inflate the bill 6 months ago."""
    rows = conn.execute(
        "SELECT l.line_id, l.account_id, l.device_purchase_date, l.monthly_installment_cents "
        "FROM lines l WHERE l.account_id = 'ACC-PERSONA-07'"
    ).fetchall()
    bills = {r["month"]: r["total_cents"] for r in conn.execute(
        "SELECT month, total_cents FROM billing_history WHERE account_id = 'ACC-PERSONA-07' ORDER BY month")}
    months = sorted(bills)
    assert rows[0]["monthly_installment_cents"] > 0
    jump = bills[months[-1]] - bills[months[0]]
    assert jump > rows[0]["monthly_installment_cents"] * 0.8


def test_purchase_never_precedes_device_release(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM lines l JOIN devices d ON d.sku = l.device_sku "
        "WHERE l.device_purchase_date < d.release_date",
    )
    assert bad == 0


def test_persona_power_user_has_hotspot_usage(conn):
    assert scalar(
        conn, "SELECT SUM(hotspot_gb) FROM usage_monthly WHERE line_id LIKE 'LN-PERSONA-09%'"
    ) > 0


def test_content_checksum_is_stored_and_reproducible(conn):
    from datagen.writer import content_checksum

    assert scalar(conn, "SELECT value FROM metadata WHERE key = 'content_sha256'") == content_checksum(conn)


def test_failed_build_leaves_no_partial_database(tmp_path, monkeypatch):
    import datagen.writer as writer

    target = tmp_path / "x.db"
    monkeypatch.setattr(writer, "_write_accounts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        writer.build_database(target, seed=1, accounts=5)
    assert not target.exists()
    assert not list(tmp_path.iterdir())


def test_financing_is_consistent(conn):
    rows = conn.execute(
        "SELECT financing_balance_cents, financing_months_remaining FROM lines"
    ).fetchall()
    for r in rows:
        assert (r[0] == 0) == (r[1] == 0)
        assert r[0] >= 0


def test_byod_lines_have_no_device_or_financing(conn):
    rows = conn.execute(
        "SELECT device_sku, financing_balance_cents FROM lines WHERE byod = 1"
    ).fetchall()
    assert rows and all(r[0] is None and r[1] == 0 for r in rows)


def test_all_tables_carry_stub_marker(conn):
    for table in ("devices", "plans", "addons", "promotions"):
        assert scalar(conn, f"SELECT COUNT(*) FROM {table} WHERE data_source != 'stub'") == 0
    assert scalar(conn, "SELECT value FROM metadata WHERE key = 'data_source'") == "stub"


def test_metadata_records_generation_inputs(conn):
    assert scalar(conn, "SELECT value FROM metadata WHERE key = 'seed'") == str(SEED)
    assert scalar(conn, "SELECT value FROM metadata WHERE key = 'as_of'") == "2026-10-01"


def test_promotions_are_persisted_with_their_rules(conn):
    row = conn.execute("SELECT * FROM promotions WHERE sku = 'PROMO-STUB-IPHONE18PRO'").fetchone()
    assert row["value_cents"] == 100000 and row["payout_months"] == 36 and row["per"] == "device"
    assert row["min_plan_cents"] == 10000 and row["plan_families"] == "experience_beyond"
    assert row["device_skus"].count(",") == 1 and row["source"] == "site"
    assert scalar(conn, "SELECT COUNT(*) FROM promotions") == 21
    assert scalar(conn, "SELECT COUNT(*) FROM promotions WHERE source = 'stub'") == 3
    assert scalar(conn, "SELECT value FROM metadata WHERE key = 'schema_version'") == "9"
def test_trade_in_curves_are_loaded(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM tradein_curves") == len(catalog.DEVICES) * 61


def test_no_labels_table_in_public_dataset(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not any("label" in t or "churn_outcome" in t for t in tables)


def test_planted_pattern_support_friction_tracks_competitor_research(conn):
    hi = scalar(
        conn,
        "SELECT AVG(s.competitor_research_score) FROM account_signals s WHERE s.account_id IN "
        "(SELECT account_id FROM support_interactions WHERE interaction_date >= '2026-07-01' "
        "GROUP BY account_id HAVING COUNT(*) >= 3)",
    )
    lo = scalar(
        conn,
        "SELECT AVG(s.competitor_research_score) FROM account_signals s WHERE s.account_id NOT IN "
        "(SELECT account_id FROM support_interactions WHERE interaction_date >= '2026-07-01' "
        "GROUP BY account_id HAVING COUNT(*) >= 3)",
    )
    assert hi > lo + 0.10


def test_planted_pattern_mismatched_plans_exist(conn):
    heavy_on_small = scalar(
        conn,
        "SELECT COUNT(*) FROM lines l JOIN plans p ON p.sku = l.plan_sku "
        "JOIN (SELECT line_id, AVG(data_gb) g FROM usage_monthly GROUP BY line_id) u USING(line_id) "
        "WHERE p.data_cap_gb IS NOT NULL AND u.g > p.data_cap_gb",
    )
    light_on_premium = scalar(
        conn,
        "SELECT COUNT(*) FROM lines l JOIN plans p ON p.sku = l.plan_sku "
        "JOIN (SELECT line_id, AVG(data_gb) g FROM usage_monthly GROUP BY line_id) u USING(line_id) "
        "WHERE p.tier = 'premium' AND u.g < 5",
    )
    assert heavy_on_small > 0 and light_on_premium > 0


def test_persona_upgrader_has_old_paid_off_device(conn):
    row = conn.execute(
        "SELECT device_purchase_date, financing_balance_cents FROM lines WHERE account_id = 'ACC-PERSONA-03'"
    ).fetchone()
    assert row["financing_balance_cents"] == 0
    assert row["device_purchase_date"] <= "2023-10-01"


def test_persona_recent_upgrader_still_financing(conn):
    row = conn.execute(
        "SELECT device_purchase_date, financing_balance_cents FROM lines WHERE account_id = 'ACC-PERSONA-07'"
    ).fetchone()
    assert row["financing_balance_cents"] > 0
    assert row["device_purchase_date"] >= "2026-06-01"


def test_persona_family_has_five_lines(conn):
    assert scalar(conn, "SELECT COUNT(*) FROM lines WHERE account_id = 'ACC-PERSONA-02'") == 5


def test_discount_plans_only_go_to_eligible_accounts(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM lines l JOIN plans p ON p.sku = l.plan_sku JOIN accounts a USING (account_id) "
        "WHERE p.eligibility IS NOT NULL AND IFNULL(a.discount_group, '') != p.eligibility",
    )
    assert bad == 0
    assert scalar(conn, "SELECT COUNT(DISTINCT discount_group) FROM accounts") == 4


def test_plan_line_limits_hold_in_the_data(conn):
    over = scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT a.account_id, COUNT(*) n, MIN(p.max_lines) cap, MAX(p.min_lines) floor "
        "FROM lines l JOIN plans p ON p.sku = l.plan_sku JOIN accounts a USING (account_id) "
        "GROUP BY a.account_id) WHERE (cap IS NOT NULL AND n > cap) OR n < floor",
    )
    assert over == 0


def test_eligible_households_exist_that_are_not_on_their_discount_plan(conn):
    missed = scalar(
        conn,
        "SELECT COUNT(DISTINCT a.account_id) FROM accounts a JOIN lines l USING (account_id) "
        "JOIN plans p ON p.sku = l.plan_sku WHERE a.discount_group IS NOT NULL AND p.eligibility IS NULL",
    )
    assert missed > 0  # a planted optimization opportunity


def test_persona_retirees_qualify_for_55_plus_pricing(conn):
    assert scalar(conn, "SELECT discount_group FROM accounts WHERE account_id = 'ACC-PERSONA-08'") == "55_plus"


def test_line_protection_matches_the_device_tier(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM line_addons la JOIN addons a ON a.sku = la.addon_sku JOIN lines l USING (line_id) "
        "JOIN devices d ON d.sku = l.device_sku WHERE a.kind = 'protection' AND a.protection_tier != d.protection_tier",
    )
    assert bad == 0 and scalar(conn, "SELECT COUNT(*) FROM line_addons") > 0


def test_account_services_respect_plan_family_eligibility(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM account_addons aa JOIN addons a ON a.sku = aa.addon_sku "
        "WHERE a.eligible_families IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM lines l JOIN plans p ON p.sku = l.plan_sku "
        "WHERE l.account_id = aa.account_id AND instr(a.eligible_families, p.family) > 0)",
    )
    assert bad == 0


def test_every_add_on_category_appears_in_customer_data(conn):
    kinds = {r[0] for r in conn.execute(
        "SELECT DISTINCT a.kind FROM addons a WHERE a.sku IN "
        "(SELECT addon_sku FROM line_addons UNION SELECT addon_sku FROM account_addons)")}
    assert {"protection", "home_internet", "streaming", "connected_line"} <= kinds


def test_protection_deductibles_are_persisted(conn):
    row = conn.execute(
        "SELECT deductible_screen_cents s, deductible_damage_cents d, deductible_loss_theft_cents l "
        "FROM addons WHERE sku = 'TMO-STUB-ADD-PROT-T6'"
    ).fetchone()
    assert 0 < row["s"] < row["d"] < row["l"]
    stray = "SELECT COUNT(*) FROM addons WHERE kind != 'protection' AND deductible_damage_cents IS NOT NULL"
    assert scalar(conn, stray) == 0


def test_customers_only_own_phones_that_were_on_sale_when_they_bought_them(conn):
    bad = scalar(
        conn,
        "SELECT COUNT(*) FROM lines l JOIN devices d ON d.sku = l.device_sku "
        "WHERE l.device_purchase_date < d.release_date "
        "OR (d.sold_until IS NOT NULL AND l.device_purchase_date > d.sold_until)",
    )
    assert bad == 0


def test_a_household_shares_one_plan_across_its_lines(conn):
    split = conn.execute(
        "SELECT account_id FROM lines GROUP BY account_id HAVING COUNT(DISTINCT plan_sku) > 1"
    ).fetchall()
    assert split == []


def test_households_still_have_plans_that_do_not_fit_their_usage(conn):
    # one plan per household means light lines can sit on a premium plan chosen for a heavy user
    mixed = scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT l.account_id FROM lines l JOIN plans p ON p.sku = l.plan_sku "
        "JOIN (SELECT line_id, AVG(data_gb) g FROM usage_monthly GROUP BY line_id) u USING (line_id) "
        "GROUP BY l.account_id HAVING p.tier = 'premium' AND MIN(u.g) < 5 AND MAX(u.g) > 30)",
    )
    assert mixed > 0


PERSONA_RECENT_SUPPORT = {1: 0, 2: 1, 3: 0, 4: 5, 5: 1, 6: 1, 7: 0, 8: 0, 9: 2, 10: 0}


@pytest.mark.parametrize("number,expected", sorted(PERSONA_RECENT_SUPPORT.items()))
def test_persona_support_history_is_pinned_to_its_story(conn, number, expected):
    recent = scalar(
        conn,
        "SELECT COUNT(*) FROM support_interactions WHERE account_id = ? AND interaction_date >= '2026-07-03'",
        (f"ACC-PERSONA-{number:02d}",),
    )
    assert recent == expected


def test_home_internet_bundle_credit_is_in_the_bill():
    from dataclasses import replace
    from random import Random

    from datagen.personas import PERSONAS
    from datagen.realize import realize

    loyal = next(p for p in PERSONAS if p.account_id == "ACC-PERSONA-10")  # has Home Internet
    without = replace(loyal, services=tuple(s for s in loyal.services if "HINT" not in s))
    with_hint = realize(loyal, Random(5)).billing[-1][2]
    plain = realize(without, Random(5)).billing[-1][2]
    # Home Internet costs $50 and the bundle credit takes $15 off: about $35 more, within the +/-2% monthly wobble
    assert 3300 <= with_hint - plain <= 3700
