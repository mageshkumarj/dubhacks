import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.errors import DomainError  # noqa: E402
from api.schemas.commerce import (  # noqa: E402
    Addon, Device, FinancingQuote, Plan, TradeInPoint, TradeInValue,
)
from api.services import catalog, pricing  # noqa: E402

from datagen import catalog as dg  # noqa: E402

DEVICE = dg.device_by_name("iPhone 17").sku
PRICE = dg.device_by_name("iPhone 17").msrp_cents  # 929.99


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


# ---- catalog ------------------------------------------------------------------------------
def test_devices_paginate_and_filter(conn):
    page, total = catalog.list_devices(conn, limit=5)
    assert len(page) == 5 and total == 45  # only devices currently for sale by default
    assert {d["status"] for d in page} == {"current"}
    assert catalog.list_devices(conn, status="legacy", limit=1)[1] >= 15
    legacy_total = catalog.list_devices(conn, status="legacy", limit=1)[1]
    assert catalog.list_devices(conn, status=None, limit=1)[1] == 45 + legacy_total
    flagships, n = catalog.list_devices(conn, tier="flagship", limit=50)
    assert n > 0 and {d["tier"] for d in flagships} == {"flagship"}
    assert catalog.list_devices(conn, manufacturer="Nobody", limit=5) == ([], 0)


def test_device_detail_and_schema(conn):
    device = catalog.get_device(conn, DEVICE)
    assert device["msrp_cents"] == PRICE and device["installment_24_cents"] == PRICE // 24
    Device.model_validate(device)
    assert catalog.get_device(conn, "TMO-STUB-DEV-9999") is None


def test_plans_expose_prices_and_benefits(conn):
    plans = catalog.list_plans(conn)
    assert len(plans) == 11 and all(Plan.model_validate(p) for p in plans)
    by_sku = {p["sku"]: p for p in plans}
    beyond = by_sku["TMO-STUB-PLAN-BEYOND"]
    assert beyond["total_for_lines_cents"] == [10500, 18000, 23000, 28000, 33000]
    assert beyond["perks"] == [
        "streaming-video-ads", "streaming-video-bundle", "satellite-connectivity", "streaming-video-offer-3usd"]
    assert by_sku["TMO-STUB-PLAN-ESSENTIALS"]["perks"] == []
    assert by_sku["TMO-STUB-PLAN-MORE-55"]["eligibility"] == "55_plus"
    assert by_sku["TMO-STUB-PLAN-ESSENTIALS-4LINE"]["status"] == "limited_time"
    assert catalog.get_plan(conn, "TMO-STUB-PLAN-MORE")["tier"] == "premium"
    assert catalog.get_plan(conn, "nope") is None


def test_addons_filter_by_kind(conn):
    protection = catalog.list_addons(conn, kind="protection")
    assert {a["kind"] for a in protection} == {"protection"} and len(protection) == 6
    assert [a["protection_tier"] for a in protection] == [1, 2, 3, 4, 5, 6]
    assert protection[0]["deductible_loss_theft_cents"] < protection[-1]["deductible_loss_theft_cents"]
    assert catalog.get_addon(conn, "TMO-STUB-ADD-STREAM-VIDEO")["deductible_damage_cents"] is None
    assert catalog.get_addon(conn, "TMO-STUB-ADD-HINT-BASIC")["per"] == "account"
    assert catalog.get_addon(conn, "TMO-STUB-ADD-STREAM-VIDEO")["eligible_families"] == [
        "experience_more", "experience_beyond"]
    case = catalog.get_addon(conn, "TMO-STUB-ADD-ACC-CASE-SILICONE-18PRO")
    assert case["compatible_device_skus"] == [dg.device_by_name("iPhone 18 Pro").sku]
    assert all(Addon.model_validate(a) for a in catalog.list_addons(conn))


# ---- trade-in -----------------------------------------------------------------------------
def test_tradein_value_applies_condition_multiplier(conn):
    good = pricing.tradein_value(conn, DEVICE, 12, "good")
    fair = pricing.tradein_value(conn, DEVICE, 12, "fair")
    poor = pricing.tradein_value(conn, DEVICE, 12, "poor")
    assert good["value_cents"] > fair["value_cents"] > poor["value_cents"] > 0
    assert good["value_cents"] == good["base_value_cents"]
    TradeInValue.model_validate(good)


def test_tradein_value_decays_with_age(conn):
    values = [pricing.tradein_value(conn, DEVICE, a, "good")["value_cents"] for a in (0, 12, 24, 48)]
    assert values == sorted(values, reverse=True) and values[0] > values[-1]


def test_tradein_unknown_device_and_bad_inputs(conn):
    assert pricing.tradein_value(conn, "nope", 12, "good") is None
    with pytest.raises(DomainError):
        pricing.tradein_value(conn, DEVICE, 12, "shattered")
    with pytest.raises(DomainError):
        pricing.tradein_value(conn, DEVICE, 61, "good")


def test_tradein_curve_is_complete_and_non_increasing(conn):
    curve = pricing.tradein_curve(conn, DEVICE)
    assert len(curve) == 61 and curve[0]["age_months"] == 0
    assert all(a["value_cents"] >= b["value_cents"] for a, b in zip(curve, curve[1:], strict=False))
    TradeInPoint.model_validate(curve[0])
    assert pricing.tradein_curve(conn, "nope") is None


# ---- financing ----------------------------------------------------------------------------
def test_prime_credit_is_zero_apr_split_evenly(conn):
    q = pricing.financing_quote(conn, DEVICE, "prime")
    assert q["apr"] == 0 and q["term_months"] == 24 and q["amount_financed_cents"] == PRICE
    assert q["monthly_payment_cents"] * 23 + q["final_payment_cents"] == PRICE
    assert q["total_interest_cents"] == 0 and q["total_cost_cents"] == PRICE
    FinancingQuote.model_validate(q)


def test_lower_credit_pays_interest_and_more_per_month(conn):
    prime = pricing.financing_quote(conn, DEVICE, "prime")
    near = pricing.financing_quote(conn, DEVICE, "near_prime", down_payment_cents=10000)
    sub = pricing.financing_quote(conn, DEVICE, "subprime", down_payment_cents=20000)
    assert near["apr"] > 0 and near["total_interest_cents"] > 0
    assert sub["apr"] > near["apr"]
    assert sub["total_interest_cents"] > near["total_interest_cents"] > prime["total_interest_cents"]


def test_minimum_down_payment_is_enforced_by_credit_tier(conn):
    with pytest.raises(DomainError) as err:
        pricing.financing_quote(conn, DEVICE, "near_prime", down_payment_cents=0)
    assert err.value.code == "DOWN_PAYMENT_TOO_LOW" and err.value.status_code == 422


def test_tradein_credit_reduces_the_financed_amount(conn):
    base = pricing.financing_quote(conn, DEVICE, "prime")
    credited = pricing.financing_quote(conn, DEVICE, "prime", tradein_credit_cents=30000)
    assert credited["amount_financed_cents"] == base["amount_financed_cents"] - 30000
    assert credited["monthly_payment_cents"] < base["monthly_payment_cents"]


def test_term_options_and_total_cost(conn):
    for term in (12, 24, 36):
        q = pricing.financing_quote(conn, DEVICE, "near_prime", term_months=term, down_payment_cents=10000)
        payments = q["monthly_payment_cents"] * (term - 1) + q["final_payment_cents"]
        assert q["total_cost_cents"] == q["down_payment_cents"] + payments
    with pytest.raises(DomainError):
        pricing.financing_quote(conn, DEVICE, "prime", term_months=18)


def test_credit_cannot_exceed_price_and_unknown_inputs(conn):
    with pytest.raises(DomainError):
        pricing.financing_quote(conn, DEVICE, "prime", down_payment_cents=PRICE, tradein_credit_cents=1)
    with pytest.raises(DomainError):
        pricing.financing_quote(conn, DEVICE, "platinum")
    with pytest.raises(DomainError):
        pricing.financing_quote(conn, DEVICE, "prime", down_payment_cents=-1)
    assert pricing.financing_quote(conn, "nope", "prime") is None


def test_credit_tier_lookup_from_account(conn):
    assert pricing.credit_tier_for(conn, "ACC-PERSONA-01") == "near_prime"
    assert pricing.credit_tier_for(conn, "ACC-NOPE") is None


def test_catalog_installment_matches_the_quote_for_every_device(conn):
    devices, _ = catalog.list_devices(conn, limit=200)
    for device in devices:
        quote = pricing.financing_quote(conn, device["sku"], "prime")
        assert quote["monthly_payment_cents"] == device["installment_24_cents"]
        assert quote["total_interest_cents"] == 0 and quote["total_cost_cents"] == device["msrp_cents"]


def test_devices_expose_their_protection_tier(conn):
    device = catalog.get_device(conn, DEVICE)  # iPhone 17, $929.99
    assert device["protection_tier"] == 5
    Device.model_validate(device)
