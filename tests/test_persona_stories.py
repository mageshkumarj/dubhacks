"""Persona stories must hold in the data at both the test seed (7) and the shipped seed (2026)."""

import sqlite3
from datetime import date
from random import Random

import pytest

from datagen import catalog
from datagen.realize import LineBill, _billing_rows, _history_months
from datagen.rows import AccountSpec
from datagen.writer import build_database

SEEDS = (7, 2026)  # persona rows depend only on the seed, so 10 accounts reproduce them at any account count
AS_OF = "2026-10-01"
CAP_SQL = (
    "SELECT AVG(u.data_gb), p.data_cap_gb FROM usage_monthly u JOIN lines l USING (line_id) "
    "JOIN plans p ON p.sku = l.plan_sku WHERE l.line_id = ?"
)


@pytest.fixture(scope="module", params=SEEDS, ids=lambda s: f"seed{s}")
def conn(request, tmp_path_factory):
    path = build_database(tmp_path_factory.mktemp(f"stories{request.param}") / "s.db", seed=request.param, accounts=10)
    connection = sqlite3.connect(path)
    yield connection
    connection.close()


def q(conn, sql, *args):
    return conn.execute(sql, args).fetchall()


# ---- persona notes -----------------------------------------------------------------------------------------
def test_persona_notes_equal_their_titles(conn):
    notes = dict(q(conn, "SELECT a.account_id, a.persona_note FROM accounts a WHERE a.account_id LIKE 'ACC-PERSONA-%'"))
    titles = dict(q(conn, "SELECT account_id, title FROM personas WHERE kind = 'customer'"))
    assert notes == titles


# ---- usage and support stories -----------------------------------------------------------------------------
def test_persona_04_contacts_are_about_network_and_devices(conn):
    topics = {t for (t,) in q(conn, "SELECT topic FROM support_interactions WHERE account_id = 'ACC-PERSONA-04' "
                                    "AND interaction_date >= date(?, '-90 day')", AS_OF)}
    assert topics and topics <= {"network", "device"}


@pytest.mark.parametrize("line_id", ["LN-PERSONA-09-1", "LN-PERSONA-06-3", "LN-PERSONA-25-1", "LN-PERSONA-19-1"])
def test_heavy_personas_use_more_data_than_their_plan_includes(conn, line_id):
    avg, cap = q(conn, CAP_SQL, line_id)[0]
    assert avg > cap * 1.1, (line_id, avg, cap)


def test_persona_09_is_over_the_cap_most_months(conn):
    over = q(conn, "SELECT COUNT(*) FROM usage_monthly u JOIN lines l USING (line_id) "
                   "JOIN plans p ON p.sku = l.plan_sku WHERE l.line_id = 'LN-PERSONA-09-1' "
                   "AND u.data_gb > p.data_cap_gb")[0][0]
    assert over >= 9


def test_persona_19_usage_has_grown(conn):
    gb = [g for (g,) in q(conn, "SELECT data_gb FROM usage_monthly WHERE line_id = 'LN-PERSONA-19-1' ORDER BY month")]
    assert len(gb) == 12 and sum(gb[-3:]) > 1.5 * sum(gb[:3])


def test_no_phone_bought_before_the_account_opened(conn):
    early = q(conn, "SELECT l.line_id FROM lines l JOIN accounts a USING (account_id) WHERE l.byod = 0 "
                    "AND l.device_purchase_date < date(?, '-' || a.tenure_months || ' months')", AS_OF)
    assert early == []


# ---- billing -----------------------------------------------------------------------------------------------
def _list_price(conn, account_id):
    lines = q(conn, "SELECT plan_sku, financing_months_remaining > 0, monthly_installment_cents FROM lines "
                    "WHERE account_id = ? ORDER BY rowid", account_id)
    total = 0
    for position, (plan, financing, installment) in enumerate(lines):
        prices, extra = q(conn, "SELECT line_prices, extra_line_cents FROM plans WHERE sku = ?", plan)[0]
        table = [int(x) for x in prices.split(",")]
        total += (table[position] if position < len(table) else extra) + (installment if financing else 0)
    total += q(conn, "SELECT IFNULL(SUM(a.monthly_cents), 0) FROM line_addons la JOIN addons a ON a.sku = la.addon_sku "
                     "JOIN lines l USING (line_id) WHERE l.account_id = ?", account_id)[0][0]
    shared = q(conn, "SELECT a.kind, a.monthly_cents FROM account_addons x JOIN addons a ON a.sku = x.addon_sku "
                     "WHERE x.account_id = ?", account_id)
    total += sum(c for _, c in shared)
    if lines and any(k == "home_internet" for k, _ in shared):
        total -= next(p.value_cents for p in catalog.PROMOTIONS if p.sku == "PROMO-STUB-BUNDLE-HINT")
    return total


def test_after_a_promo_expires_the_bill_is_at_list_price(conn):
    spiked = [a for (a,) in q(conn, "SELECT DISTINCT account_id FROM billing_history "
                                    "WHERE change_reason = 'promo_expired' AND account_id LIKE 'ACC-PERSONA-%'")]
    assert "ACC-PERSONA-22" in spiked
    for account in spiked:
        latest = q(conn, "SELECT total_cents FROM billing_history WHERE account_id = ? ORDER BY month DESC LIMIT 1",
                   account)[0][0]
        assert abs(latest / _list_price(conn, account) - 1) <= 0.03, account


def test_a_promo_cannot_expire_on_the_first_bill(conn):
    firsts = q(conn, "SELECT COUNT(*) FROM billing_history b WHERE change_reason = 'promo_expired' AND month = "
                     "(SELECT MIN(month) FROM billing_history x WHERE x.account_id = b.account_id)")
    assert firsts[0][0] == 0


# ---- bill-change reasons (unit level, synthetic accounts) --------------------------------------------------
def _spec(tenure, spike=0.0):
    return AccountSpec("ACC-T", "single", tenure, 0.1, (), bill_spike_pct=spike)


def _bills(tenure, spike, bill):
    return _billing_rows(Random(1), _spec(tenure, spike), 0, [bill], _history_months(tenure))


def test_a_phone_finishing_its_payments_is_labelled_installment_ended():
    rows = _bills(14, 0.0, LineBill(5000, 4000, date(2024, 8, 1), True))
    by_month = {r[1]: r for r in rows}
    assert by_month["2026-08"][4] == "installment_ended" and by_month["2026-08"][3] < -3000
    assert all(r[4] == "stable" for r in rows if r[1] != "2026-08")


def test_new_phone_beats_ended_phone_beats_promo():
    ended = LineBill(5000, 4000, date(2024, 8, 1), True)
    started = LineBill(5000, 6000, date(2026, 8, 1), True)
    rows = _billing_rows(Random(1), _spec(14, 0.2), 0, [ended, started], _history_months(14))
    assert {r[1]: r[4] for r in rows}["2026-08"] == "device_installment"
    only_ended = _billing_rows(Random(1), _spec(14, 0.2), 0, [ended], _history_months(14))
    assert {r[1]: r[4] for r in only_ended}["2026-08"] == "installment_ended"  # 2026-08 is also the first spike month


def test_spike_months_are_at_list_price_and_earlier_months_discounted():
    rows = _bills(14, 0.25, LineBill(10000, 0, None, False))
    totals = [r[2] for r in rows]
    assert all(abs(t / 10000 - 1) <= 0.025 for t in totals[-2:])
    assert all(abs(t / 8000 - 1) <= 0.025 for t in totals[:-2])
    assert rows[-2][4] == "promo_expired"


def test_no_promo_expiry_with_fewer_than_three_months_of_history():
    rows = _bills(2, 0.25, LineBill(10000, 0, None, False))
    assert len(rows) == 2 and all(r[4] == "stable" for r in rows)
    assert all(abs(r[2] / 10000 - 1) <= 0.025 for r in rows)
