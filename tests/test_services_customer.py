import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.schemas.customer import (  # noqa: E402
    AccountSummary,
    BillingMonth,
    CustomerContext,
    Household,
    SupportInteraction,
    UsageMonth,
)
from api.services import accounts, context, history  # noqa: E402

PERSONAS = [f"ACC-PERSONA-{n:02d}" for n in range(1, 43)]


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


def line_by_label(ctx: dict, label: str) -> dict:
    return next(line for line in ctx["lines"] if line["member_label"] == label)


# ---- accounts list ---------------------------------------------------------------------------
def test_list_accounts_paginates_with_total(conn):
    page, total = accounts.list_accounts(conn, limit=10, offset=0)
    assert len(page) == 10 and total == 342
    second, _ = accounts.list_accounts(conn, limit=10, offset=10)
    assert not {a["account_id"] for a in page} & {a["account_id"] for a in second}


def test_list_accounts_persona_only(conn):
    page, total = accounts.list_accounts(conn, persona_only=True, limit=100)
    assert total == 42 and [a["account_id"] for a in page] == PERSONAS


def test_list_accounts_filters_by_segment(conn):
    page, total = accounts.list_accounts(conn, segment="family", limit=500)
    assert total > 0 and {a["segment"] for a in page} == {"family"}


def test_list_accounts_items_match_schema(conn):
    page, _ = accounts.list_accounts(conn, limit=25)
    for item in page:
        AccountSummary.model_validate(item)


# ---- household ------------------------------------------------------------------------------
def test_household_unknown_account_is_none(conn):
    assert accounts.get_household(conn, "ACC-NOPE") is None


def test_household_family_of_five(conn):
    hh = accounts.get_household(conn, "ACC-PERSONA-02")
    assert len(hh["lines"]) == 5
    assert "TMO-STUB-ADD-HINT-BASIC" in {s["sku"] for s in hh["services"]}
    assert all(line["plan_name"] for line in hh["lines"])


@pytest.mark.parametrize("account_id", PERSONAS)
def test_household_matches_schema_for_personas(conn, account_id):
    Household.model_validate(accounts.get_household(conn, account_id))


# ---- context --------------------------------------------------------------------------------
def test_context_unknown_account_is_none(conn):
    assert context.get_context(conn, "ACC-NOPE") is None


def test_context_upgrader_is_eligible_with_trade_in_value(conn):
    line = context.get_context(conn, "ACC-PERSONA-03")["lines"][0]
    assert line["upgrade_eligible"] and line["tradein_eligible"]
    assert line["device"]["age_months"] >= 36
    assert line["estimated_tradein_value_cents"] > 0
    assert line["financing"]["paid_off"] is True


def test_context_just_upgraded_is_not_upgrade_eligible(conn):
    line = context.get_context(conn, "ACC-PERSONA-07")["lines"][0]
    assert line["upgrade_eligible"] is False
    assert line["financing"]["paid_off"] is False
    assert line["financing"]["balance_cents"] > 0
    assert line["device"]["age_months"] <= 4


def test_context_byod_student_has_no_device_or_tradein(conn):
    line = context.get_context(conn, "ACC-PERSONA-01")["lines"][0]
    assert line["byod"] and line["device"] is None
    assert line["tradein_eligible"] is False and line["estimated_tradein_value_cents"] is None


def test_context_at_risk_couple_shows_friction_signals(conn):
    ctx = context.get_context(conn, "ACC-PERSONA-04")
    assert ctx["support"]["contacts_90d"] >= 3
    assert ctx["billing"]["change_pct_vs_prior_avg"] > 0.1
    assert ctx["signals"]["competitor_research_score"] > 0.6


def test_context_overpaying_household_shows_low_usage_on_premium(conn):
    ctx = context.get_context(conn, "ACC-PERSONA-05")
    for line in ctx["lines"]:
        assert line["plan_tier"] == "premium" and line["usage_3m_avg_gb"] < 8


def test_context_summarizes_eligibility_counts(conn):
    ctx = context.get_context(conn, "ACC-PERSONA-02")
    assert ctx["eligibility"]["line_count"] == 5
    assert ctx["eligibility"]["upgrade_eligible_lines"] == sum(
        line["upgrade_eligible"] for line in ctx["lines"]
    )


def test_context_exposes_no_outcome_labels(conn):
    flat = str(context.get_context(conn, "ACC-PERSONA-04")).lower()
    assert "churn" not in flat


def test_context_matches_schema_for_every_persona_and_sample(conn):
    page, _ = accounts.list_accounts(conn, limit=200)
    page += accounts.list_accounts(conn, limit=200, offset=200)[0]
    assert len(page) == 342
    for item in page:
        CustomerContext.model_validate(context.get_context(conn, item["account_id"]))


# ---- history --------------------------------------------------------------------------------
def test_usage_returns_twelve_months_per_line_for_long_tenure(conn):
    rows = history.get_usage(conn, "ACC-PERSONA-02")
    assert len(rows) == 5 * 12
    assert rows == sorted(rows, key=lambda r: (r["line_id"], r["month"]))
    UsageMonth.model_validate(rows[0])


def test_usage_filters_by_line_and_months(conn):
    rows = history.get_usage(conn, "ACC-PERSONA-02", line_id="LN-PERSONA-02-1", months=3)
    assert len(rows) == 3 and {r["line_id"] for r in rows} == {"LN-PERSONA-02-1"}
    assert [r["month"] for r in rows] == ["2026-07", "2026-08", "2026-09"]


def test_usage_for_foreign_or_unknown_line_is_none(conn):
    assert history.get_usage(conn, "ACC-PERSONA-02", line_id="LN-PERSONA-01-1") is None
    assert history.get_usage(conn, "ACC-NOPE") is None


def test_billing_is_chronological_and_consistent(conn):
    rows = history.get_billing(conn, "ACC-PERSONA-04")
    assert [r["month"] for r in rows] == sorted(r["month"] for r in rows)
    assert all(b["total_cents"] - a["total_cents"] == b["change_cents"] for a, b in zip(rows, rows[1:], strict=False))
    BillingMonth.model_validate(rows[0])
    assert history.get_billing(conn, "ACC-NOPE") is None


def test_support_is_newest_first_and_limited(conn):
    rows = history.get_support_interactions(conn, "ACC-PERSONA-04", limit=2)
    assert len(rows) == 2 and rows[0]["interaction_date"] >= rows[1]["interaction_date"]
    SupportInteraction.model_validate(rows[0])
    assert history.get_support_interactions(conn, "ACC-NOPE") is None


def test_sql_injection_attempt_is_inert(conn):
    assert accounts.get_household(conn, "x' OR '1'='1") is None
    page, total = accounts.list_accounts(conn, segment="family' OR '1'='1", limit=5)
    assert total == 0 and page == []


def test_envelope_contract_accepts_success_and_error_shapes(conn):
    from api.envelope import fail, ok
    from api.schemas.common import Envelope

    Envelope[Household].model_validate(ok(accounts.get_household(conn, "ACC-PERSONA-01")))
    Envelope[Household].model_validate(fail("nope", "HTTP_404"))
    Envelope[list[AccountSummary]].model_validate(
        ok(accounts.list_accounts(conn, limit=3)[0], {"total": 310, "limit": 3, "offset": 0})
    )


def test_context_does_not_offer_upgrade_for_a_device_bought_recently(conn):
    page, _ = accounts.list_accounts(conn, limit=200)
    for item in page:
        for line in context.get_context(conn, item["account_id"])["lines"]:
            if line["device"] and line["device"]["age_months"] < 12:
                assert line["upgrade_eligible"] is False


def test_context_tolerates_missing_billing_and_signals(sandbox_db, tmp_path):
    import shutil
    import sqlite3

    copy = tmp_path / "partial.db"
    shutil.copy(sandbox_db, copy)
    raw = sqlite3.connect(copy)
    raw.execute("DELETE FROM billing_history WHERE account_id = 'ACC-PERSONA-01'")
    raw.execute("DELETE FROM account_signals WHERE account_id = 'ACC-PERSONA-01'")
    raw.commit()
    raw.close()
    partial = connect(copy)
    ctx = context.get_context(partial, "ACC-PERSONA-01")
    partial.close()
    assert ctx["billing"] is None and ctx["signals"] is None
    CustomerContext.model_validate(ctx)


def test_single_month_billing_has_no_trend(sandbox_db, tmp_path):
    import shutil
    import sqlite3

    copy = tmp_path / "one.db"
    shutil.copy(sandbox_db, copy)
    raw = sqlite3.connect(copy)
    raw.execute("DELETE FROM billing_history WHERE account_id = 'ACC-PERSONA-01' AND month < '2026-09'")
    raw.commit()
    raw.close()
    one = connect(copy)
    ctx = context.get_context(one, "ACC-PERSONA-01")
    one.close()
    assert ctx["billing"]["change_pct_vs_prior_avg"] is None
