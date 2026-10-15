"""Is the sandbox set up well enough for each of the five hackathon themes? These tests are the answer."""

import json
import sqlite3

import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.services import carts, catalog, pricing, promotions  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402

THEMES = ("cart_whisperer", "matchmaker", "next_best_moment", "timekeeper", "household_optimizer")


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


def personas(conn, theme=None, kind=None) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM personas WHERE (? IS NULL OR primary_theme = ?) AND (? IS NULL OR kind = ?) ORDER BY persona_id",
        (theme, theme, kind, kind),
    ).fetchall()


# ---- the cast --------------------------------------------------------------------------------------------
def test_fifty_personas_ten_for_each_theme(conn):
    assert len(personas(conn)) == 50
    for theme in THEMES:
        assert len(personas(conn, theme)) == 10, theme


def test_customers_have_accounts_and_prospects_do_not(conn):
    assert len(personas(conn, kind="customer")) == 42 and len(personas(conn, kind="prospect")) == 8
    for p in personas(conn, kind="customer"):
        assert p["account_id"] == p["persona_id"]
        assert conn.execute("SELECT 1 FROM accounts WHERE account_id = ?", (p["account_id"],)).fetchone()
    assert all(p["account_id"] is None for p in personas(conn, kind="prospect"))


def test_every_persona_tells_a_story_without_giving_the_answer(conn):
    for p in personas(conn):
        assert len(p["title"]) >= 12 and len(p["scenario"]) >= 60, p["persona_id"]
        assert p["primary_theme"] in THEMES
    banned = ("the right answer", "correct answer", "should recommend", "best answer", "the honest answer")
    text = " ".join((p["scenario"] + " " + p["title"]).lower() for p in personas(conn))
    assert [b for b in banned if b in text] == []
    account_notes = " ".join((r[0] or "").lower() for r in conn.execute("SELECT persona_note FROM accounts"))
    assert [b for b in banned if b in account_notes] == []
    notes = dict(conn.execute("SELECT account_id, persona_note FROM accounts WHERE persona_note IS NOT NULL"))
    titles = {p["account_id"]: p["title"] for p in personas(conn, kind="customer")}
    assert notes == titles  # the notes served by /context describe the situation, never the diagnosis


def test_persona_titles_are_unique(conn):
    titles = [p["title"] for p in personas(conn)]
    assert len(titles) == len(set(titles))


# ---- Cart Whisperer ----------------------------------------------------------------------------------------
def build_cart(conn, persona) -> tuple[MemoryStore, str]:
    store = MemoryStore()
    cart_id = carts.create_cart(conn, store, persona["account_id"])["cart_id"]
    for item in json.loads(persona["starting_cart"] or "[]"):
        carts.add_item(conn, store, cart_id, **item)
    return store, cart_id


def test_every_starting_cart_can_be_built(conn):
    with_carts = [p for p in personas(conn) if p["starting_cart"]]
    assert len(with_carts) >= 12
    for p in with_carts:
        store, cart_id = build_cart(conn, p)
        assert carts.get_cart(conn, store, cart_id)["items"], p["persona_id"]


def test_cart_whisperer_personas_all_arrive_with_a_cart_and_have_things_to_suggest(conn):
    for p in personas(conn, "cart_whisperer"):
        assert p["starting_cart"], p["persona_id"]
        store, cart_id = build_cart(conn, p)
        view = carts.get_cart(conn, store, cart_id)
        devices = [i for i in view["items"] if i["kind"] == "device"]
        for device in devices:
            compatible = conn.execute(
                "SELECT COUNT(*) FROM addons WHERE kind = 'accessory' AND "
                "(compatible_device_skus IS NULL OR instr(compatible_device_skus, ?) > 0)", (device["sku"],)
            ).fetchone()[0]
            assert compatible >= 3, f"{p['persona_id']}: only {compatible} accessories fit {device['name']}"
            tier = conn.execute("SELECT protection_tier FROM devices WHERE sku = ?", (device["sku"],)).fetchone()[0]
            assert conn.execute("SELECT 1 FROM addons WHERE protection_tier = ?", (tier,)).fetchone()


def test_accessories_exist_for_every_current_phone(conn):
    for device in catalog.list_devices(conn, limit=200)[0]:
        fit = conn.execute(
            "SELECT COUNT(*) FROM addons WHERE kind = 'accessory' AND "
            "(compatible_device_skus IS NULL OR instr(compatible_device_skus, ?) > 0)", (device["sku"],)
        ).fetchone()[0]
        assert fit >= 3, f"only {fit} accessories fit {device['name']}"


def test_cart_whisperer_has_a_spread_of_situations(conn):
    kinds = set()
    for p in personas(conn, "cart_whisperer"):
        kinds |= {i["kind"] for i in json.loads(p["starting_cart"])}
    assert kinds >= {"device", "new_line", "tradein", "addon"}
    assert any(p["account_id"] is None for p in personas(conn, "cart_whisperer"))  # at least one new customer
    assert any(p["account_id"] for p in personas(conn, "cart_whisperer"))


# ---- Matchmaker ------------------------------------------------------------------------------------------
def test_matchmaker_has_prospects_with_stated_needs(conn):
    prospects = [p for p in personas(conn, "matchmaker") if p["kind"] == "prospect"]
    assert len(prospects) >= 6
    for p in prospects:
        assert p["stated_lines"] >= 1 and p["stated_budget_cents"] >= 3000
        assert p["stated_usage"] in ("light", "moderate", "heavy") and p["stated_notes"]


def test_matchmaker_needs_cover_budgets_from_cheap_to_flexible_and_every_usage_level(conn):
    prospects = [p for p in personas(conn, "matchmaker") if p["kind"] == "prospect"]
    budgets = [p["stated_budget_cents"] / max(p["stated_lines"], 1) for p in prospects]
    assert min(budgets) <= 5500 and max(budgets) >= 15000  # per-line budget: Saver-level up to premium
    assert {p["stated_usage"] for p in prospects} == {"light", "moderate", "heavy"}


def test_matchmaker_has_a_plan_that_fits_every_stated_budget_or_a_real_tradeoff(conn):
    plans = catalog.list_plans(conn)
    for p in [p for p in personas(conn, "matchmaker") if p["kind"] == "prospect"]:
        affordable = [
            pl for pl in plans
            if pl["eligibility"] is None and pl["status"] == "current" and pl["min_lines"] <= p["stated_lines"]
            and (pl["max_lines"] is None or p["stated_lines"] <= pl["max_lines"])
            and sum(pl["line_prices_cents"][: p["stated_lines"]]) <= p["stated_budget_cents"]
        ]
        assert affordable, f"{p['persona_id']}: nothing fits the budget"


# ---- Next Best Moment ----------------------------------------------------------------------------------------
def signals(conn, account_id) -> dict:
    row = conn.execute(
        "SELECT s.competitor_research_score comp, s.port_out_inquiry port, "
        "(SELECT COUNT(*) FROM support_interactions i WHERE i.account_id = s.account_id "
        "AND i.interaction_date >= '2026-07-03') recent, "
        "(SELECT AVG(sentiment) FROM support_interactions i WHERE i.account_id = s.account_id) sentiment, "
        "(SELECT AVG(resolved) FROM support_interactions i WHERE i.account_id = s.account_id) resolved "
        "FROM account_signals s WHERE s.account_id = ?", (account_id,)
    ).fetchone()
    return dict(row)


def test_next_best_moment_personas_show_different_kinds_of_risk(conn):
    rows = [signals(conn, p["account_id"]) for p in personas(conn, "next_best_moment")]
    assert any(r["port"] for r in rows)  # already asked to port out
    assert sum(r["comp"] >= 0.7 for r in rows) >= 3  # researching competitors
    assert any(r["comp"] < 0.3 for r in rows)  # a calm one
    quiet_but_shopping = [r for r in rows if r["recent"] == 0 and r["comp"] >= 0.7]
    assert quiet_but_shopping  # risk with no support noise
    noisy_but_fine = [
        r for r in rows
        if r["recent"] >= 4 and r["comp"] < 0.3 and (r["sentiment"] or 0) > 0 and r["resolved"] >= 0.8
    ]
    assert noisy_but_fine  # a false alarm


def test_next_best_moment_has_a_bill_shock_with_a_reason(conn):
    shocks = 0
    for p in personas(conn, "next_best_moment"):
        reasons = [r[0] for r in conn.execute(
            "SELECT change_reason FROM billing_history WHERE account_id = ? AND change_cents > 0", (p["account_id"],))]
        shocks += "promo_expired" in reasons
    assert shocks >= 2


def test_every_bill_change_has_a_reason(conn):
    reasons = {r[0] for r in conn.execute("SELECT DISTINCT change_reason FROM billing_history")}
    assert reasons <= {"stable", "device_installment", "installment_ended", "promo_expired"}
    assert {"device_installment", "installment_ended"} <= reasons
    assert conn.execute("SELECT COUNT(*) FROM billing_history WHERE change_reason IS NULL").fetchone()[0] == 0


def test_retention_actions_exist_at_several_price_points(conn):
    stubs = [r for r in promotions.evaluate_promotions(conn, "ACC-PERSONA-04", None)]
    values = sorted(r["estimated_savings_cents"] for r in stubs if r["eligible"])
    assert len(values) >= 2 and values[0] < values[-1]  # a cheap action and a costlier one


# ---- Timekeeper -------------------------------------------------------------------------------------------------
def test_timekeeper_personas_span_device_ages_and_financing_states(conn):
    ages, owing, paid = [], 0, 0
    for p in personas(conn, "timekeeper"):
        for line in conn.execute(
            "SELECT device_purchase_date d, financing_balance_cents b FROM lines "
            "WHERE account_id = ? AND device_sku IS NOT NULL",
            (p["account_id"],),
        ):
            months = (2026 - int(line["d"][:4])) * 12 + (10 - int(line["d"][5:7]))
            ages.append(months)
            owing += line["b"] > 0
            paid += line["b"] == 0
    assert min(ages) <= 6 and max(ages) >= 48 and owing >= 3 and paid >= 5


def test_timekeeper_devices_all_have_a_value_curve(conn):
    for p in personas(conn, "timekeeper"):
        query = "SELECT device_sku FROM lines WHERE account_id = ? AND device_sku IS NOT NULL"
        for row in conn.execute(query, (p["account_id"],)):
            assert pricing.tradein_curve(conn, row[0]) is not None


# ---- Household Mix Optimizer -------------------------------------------------------------------------------------
def household_cost(conn, account_id, plan: dict) -> int:
    n = conn.execute("SELECT COUNT(*) FROM lines WHERE account_id = ?", (account_id,)).fetchone()[0]
    prices = plan["line_prices_cents"]
    return sum(prices[i] if i < len(prices) else plan["extra_line_cents"] for i in range(n))


def cheaper_options(conn, account_id) -> list[tuple[str, int]]:
    account = conn.execute("SELECT discount_group FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    n = conn.execute("SELECT COUNT(*) FROM lines WHERE account_id = ?", (account_id,)).fetchone()[0]
    current = conn.execute("SELECT plan_sku FROM lines WHERE account_id = ? LIMIT 1", (account_id,)).fetchone()[0]
    plans = {p["sku"]: p for p in catalog.list_plans(conn)}
    now = household_cost(conn, account_id, plans[current])
    found = []
    for plan in plans.values():
        if plan["eligibility"] not in (None, account["discount_group"]) or n < plan["min_lines"]:
            continue
        if plan["max_lines"] is not None and n > plan["max_lines"]:
            continue
        saving = now - household_cost(conn, account_id, plan)
        if saving > 0:
            found.append((plan["sku"], saving))
    return found


def test_household_optimizer_personas_have_money_to_save_or_a_reason_not_to(conn):
    cast = personas(conn, "household_optimizer")
    with_savings = [p["persona_id"] for p in cast if cheaper_options(conn, p["account_id"])]
    assert len(with_savings) >= 6


def test_linked_accounts_save_money_when_consolidated(conn):
    pairs = [p for p in personas(conn, "household_optimizer") if p["related_account_id"]]
    assert len(pairs) == 2
    a, b = pairs
    assert a["related_account_id"] == b["account_id"] and b["related_account_id"] == a["account_id"]
    plans = {p["sku"]: p for p in catalog.list_plans(conn)}
    query = "SELECT plan_sku FROM lines WHERE account_id = ? LIMIT 1"
    first_plan = conn.execute(query, (a["account_id"],)).fetchone()[0]
    plan_a = plans[first_plan]
    separate = household_cost(conn, a["account_id"], plan_a) + household_cost(conn, b["account_id"], plan_a)
    count = "SELECT COUNT(*) FROM lines WHERE account_id = ?"
    lines = sum(conn.execute(count, (x["account_id"],)).fetchone()[0] for x in pairs)
    prices = plan_a["line_prices_cents"]
    together = sum(prices[i] if i < len(prices) else plan_a["extra_line_cents"] for i in range(lines))
    assert together < separate


def test_household_optimizer_has_every_kind_of_saving_to_find(conn):
    found = set()
    for p in personas(conn, "household_optimizer"):
        for sku, _ in cheaper_options(conn, p["account_id"]):
            plan = conn.execute("SELECT variant, family FROM plans WHERE sku = ?", (sku,)).fetchone()
            found.add(plan["variant"])
    assert {"senior_55", "partner", "four_line_offer"} <= found  # discount variants and the 4-line offer


# ---- the whole dataset still tells each story ------------------------------------------------------------------
def test_there_are_many_more_ordinary_accounts_than_personas(conn):
    assert conn.execute("SELECT COUNT(*) FROM accounts WHERE persona_note IS NULL").fetchone()[0] >= 300
