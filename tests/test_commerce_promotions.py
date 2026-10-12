"""Promotion eligibility in the context of different customers (personas) and carts."""

import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.errors import DomainError  # noqa: E402
from api.schemas.commerce import PromotionResult  # noqa: E402
from api.services import carts, checkout, promotions  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402
from datagen import catalog as dg  # noqa: E402

P = "PROMO-STUB-"
MORE, BEYOND = "TMO-STUB-PLAN-MORE", "TMO-STUB-PLAN-BEYOND"
ESSENTIALS, SAVER = "TMO-STUB-PLAN-ESSENTIALS", "TMO-STUB-PLAN-ESSENTIALS-SAVER"
KEY = "idem-key-promo-01"


def sku(name: str) -> str:
    return dg.device_by_name(name).sku


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


@pytest.fixture()
def store():
    return MemoryStore()


def cart_for(conn, store, account=None) -> str:
    return carts.create_cart(conn, store, account)["cart_id"]


def add(conn, store, cid, kind, item_sku=None, **kw):
    return carts.add_item(conn, store, cid, kind=kind, sku=item_sku, **kw)


def evaluate(conn, store, account, cid=None) -> dict:
    results = promotions.promotions_for(conn, store, account, cid)
    return {r["sku"]: r for r in results}


def eligible(results, name) -> bool:
    return results[P + name]["eligible"]


def reasons(results, name) -> str:
    return " | ".join(results[P + name]["reasons"]).lower()


# ---- catalog of promotions ----------------------------------------------------------------------
def test_promotion_catalog_mixes_site_offers_and_labeled_stub_retention():
    promos = {p.sku: p for p in dg.PROMOTIONS}
    assert len(promos) == 21
    assert {p.source for p in promos.values()} == {"site", "stub"}
    stub = {sku for sku, p in promos.items() if p.source == "stub"}
    assert stub == {P + "LOYALTY-CREDIT", P + "CARE-CREDIT", P + "OLD-PHONE-UPGRADE"}
    iphone = promos[P + "IPHONE18PRO"]
    assert (iphone.value_cents, iphone.payout_months, iphone.per, iphone.max_units) == (100000, 36, "device", 4)
    assert promos[P + "KEEP-YOUR-PHONE"].value_cents * promos[P + "KEEP-YOUR-PHONE"].payout_months == 72000
    assert promos[P + "ACC-BUNDLE"].percent_off == 25 and promos[P + "ACC-BUNDLE"].min_accessories == 3


def test_no_proprietary_promotion_names():
    names = " ".join(p.name.lower() for p in dg.PROMOTIONS)
    assert not any(word in names for word in ("freedom", "nothing", "on us", "airpods", "magenta", "t-mobile"))


# ---- customer contexts --------------------------------------------------------------------------
def test_student_credit_only_for_students_and_scales_by_line(conn, store):
    assert eligible(evaluate(conn, store, "ACC-PERSONA-01"), "STUDENT")
    family = evaluate(conn, store, "ACC-PERSONA-02")
    assert not eligible(family, "STUDENT") and "student" in reasons(family, "STUDENT")


def test_bring_your_own_phone_offers_depend_on_the_plan_price(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-01")  # student with their own phone
    add(conn, store, cid, "new_line", SAVER, port_in=True)
    saver = evaluate(conn, store, "ACC-PERSONA-01", cid)
    assert eligible(saver, "KEEP-YOUR-PHONE") and not eligible(saver, "BYOD-CARD")
    assert "$60" in reasons(saver, "BYOD-CARD")  # the saver plan is under the $60 minimum
    other = cart_for(conn, store, "ACC-PERSONA-01")
    add(conn, store, other, "new_line", ESSENTIALS, port_in=True)
    standard = evaluate(conn, store, "ACC-PERSONA-01", other)
    assert eligible(standard, "BYOD-CARD") and not eligible(standard, "KEEP-YOUR-PHONE")


def test_port_in_is_required_for_switcher_offers(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", sku("iPhone 17"))
    add(conn, store, cid, "new_line", MORE)  # no number brought over
    assert "port" in reasons(evaluate(conn, store, "ACC-PERSONA-03", cid), "IPHONE17")
    ported = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, ported, "device", sku("iPhone 17"))
    add(conn, store, ported, "new_line", MORE, port_in=True)
    assert eligible(evaluate(conn, store, "ACC-PERSONA-03", ported), "IPHONE17")


def test_device_offers_are_tied_to_their_device_and_plan_family(conn, store):
    cid = cart_for(conn, store)
    add(conn, store, cid, "device", sku("razr+ 2026"))
    add(conn, store, cid, "new_line", MORE)
    assert "beyond" in reasons(evaluate(conn, store, None, cid), "RAZRPLUS")
    cid2 = cart_for(conn, store)
    add(conn, store, cid2, "device", sku("razr+ 2026"))
    add(conn, store, cid2, "new_line", BEYOND)
    assert eligible(evaluate(conn, store, None, cid2), "RAZRPLUS")
    wrong_device = cart_for(conn, store)
    add(conn, store, wrong_device, "device", sku("iPhone 17"))
    add(conn, store, wrong_device, "new_line", BEYOND)
    assert not eligible(evaluate(conn, store, None, wrong_device), "RAZRPLUS")


def test_new_line_or_trade_in_satisfies_flagship_offers(conn, store):
    upgrade = cart_for(conn, store, "ACC-PERSONA-03")  # existing customer upgrading with a trade-in
    add(conn, store, upgrade, "device", sku("Galaxy Z Flip8"))
    add(conn, store, upgrade, "tradein", None, line_id="LN-PERSONA-03-1")
    assert eligible(evaluate(conn, store, "ACC-PERSONA-03", upgrade), "FLIP8") is False  # Essentials plan: too cheap
    more = cart_for(conn, store, "ACC-PERSONA-02")  # family on Experience More
    add(conn, store, more, "device", sku("Galaxy Z Flip8"))
    add(conn, store, more, "tradein", None, line_id="LN-PERSONA-02-1")
    assert eligible(evaluate(conn, store, "ACC-PERSONA-02", more), "FLIP8")


def test_well_qualified_credit_gates_free_phone_offers(conn, store):
    def result(account):
        cid = cart_for(conn, store, account)
        add(conn, store, cid, "device", sku("moto g - 2026"))
        add(conn, store, cid, "new_line", ESSENTIALS)
        return evaluate(conn, store, account, cid)

    assert eligible(result("ACC-PERSONA-03"), "FREE-SELECT")  # prime
    near_prime = result("ACC-PERSONA-01")
    assert not eligible(near_prime, "FREE-SELECT") and "credit" in reasons(near_prime, "FREE-SELECT")


def test_discount_group_households_get_their_own_phone_offer(conn, store):
    cid = cart_for(conn, store)  # a 55+ prospect switching in (verification happens after sign-up)
    add(conn, store, cid, "device", sku("iPhone 17"))
    add(conn, store, cid, "new_line", "TMO-STUB-PLAN-MORE-55", port_in=True)
    assert eligible(evaluate(conn, store, None, cid), "GROUP-NEW-PHONE")
    family = cart_for(conn, store, "ACC-PERSONA-02")
    add(conn, store, family, "device", sku("iPhone 17"))
    add(conn, store, family, "new_line", MORE, port_in=True)
    assert not eligible(evaluate(conn, store, "ACC-PERSONA-02", family), "GROUP-NEW-PHONE")


def test_upgrade_offers_use_device_age(conn, store):
    def result(account, line):
        cid = cart_for(conn, store, account)
        add(conn, store, cid, "device", sku("iPhone 17"))
        add(conn, store, cid, "tradein", None, line_id=line)
        return evaluate(conn, store, account, cid)

    assert eligible(result("ACC-PERSONA-03", "LN-PERSONA-03-1"), "OLD-PHONE-UPGRADE")  # 3+ year-old phone
    new_phone = result("ACC-PERSONA-07", "LN-PERSONA-07-1")  # upgraded three months ago
    assert not eligible(new_phone, "OLD-PHONE-UPGRADE") and "36" in reasons(new_phone, "OLD-PHONE-UPGRADE")


def test_retention_offers_follow_tenure_and_support_history(conn, store):
    loyal = evaluate(conn, store, "ACC-PERSONA-10")  # ten years with us
    assert eligible(loyal, "LOYALTY-CREDIT") and not eligible(loyal, "CARE-CREDIT")
    newcomer = evaluate(conn, store, "ACC-PERSONA-01")
    assert not eligible(newcomer, "LOYALTY-CREDIT") and "tenure" in reasons(newcomer, "LOYALTY-CREDIT")
    frustrated = evaluate(conn, store, "ACC-PERSONA-04")  # several recent support contacts
    assert eligible(frustrated, "CARE-CREDIT")


def test_bundle_offers_for_connected_lines_and_home_internet(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "addon", "TMO-STUB-ADD-HINT-BASIC")
    home = evaluate(conn, store, "ACC-PERSONA-03", cid)
    assert eligible(home, "BUNDLE-HINT") and eligible(home, "HINT-CARD")
    watch = cart_for(conn, store, "ACC-PERSONA-02")
    add(conn, store, watch, "addon", "TMO-STUB-ADD-LINE-WATCH")
    assert eligible(evaluate(conn, store, "ACC-PERSONA-02", watch), "WATCH-LINE")
    solo = cart_for(conn, store)  # no household lines at all
    add(conn, store, solo, "addon", "TMO-STUB-ADD-LINE-WATCH")
    assert not eligible(evaluate(conn, store, None, solo), "WATCH-LINE")


def test_accessory_bundle_needs_three_accessories(conn, store):
    cid = cart_for(conn, store)
    for accessory in ("ACC-CASE-SILICONE-18PRO", "ACC-LENS-PROTECTOR"):
        add(conn, store, cid, "addon", f"TMO-STUB-ADD-{accessory}")
    assert not eligible(evaluate(conn, store, None, cid), "ACC-BUNDLE")
    assert "3 or more" in reasons(evaluate(conn, store, None, cid), "ACC-BUNDLE")
    add(conn, store, cid, "addon", "TMO-STUB-ADD-ACC-BUNDLE-3IN1-18PRO")
    result = evaluate(conn, store, None, cid)["PROMO-STUB-ACC-BUNDLE"]
    assert result["eligible"] and result["estimated_savings_cents"] == round((4999 + 2499 + 9999) * 0.25)


def test_device_promos_are_capped_per_account(conn, store):
    cid = cart_for(conn, store)
    for _ in range(5):
        add(conn, store, cid, "device", sku("iPhone 17"))
    add(conn, store, cid, "new_line", MORE, port_in=True)
    assert "at most 4" in reasons(evaluate(conn, store, None, cid), "IPHONE17")


# ---- savings and checkout --------------------------------------------------------------------------
def test_savings_scale_with_devices_and_lines(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", sku("iPhone 17"))
    add(conn, store, cid, "device", sku("iPhone 17"))
    add(conn, store, cid, "new_line", MORE, port_in=True)
    results = evaluate(conn, store, "ACC-PERSONA-03", cid)
    assert results[P + "IPHONE17"]["estimated_savings_cents"] == 2 * 83000
    student = evaluate(conn, store, "ACC-PERSONA-01")
    assert student[P + "STUDENT"]["estimated_savings_cents"] == 2000 * 1 * 12  # one line, a year


def test_checkout_records_estimated_savings_per_promotion(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", sku("iPhone 17"))
    add(conn, store, cid, "new_line", MORE, port_in=True)
    order = checkout.checkout(conn, store, cid, KEY, [P + "IPHONE17"])
    assert order["promo_savings_cents"] == 83000
    assert order["applied_promotions"][0]["savings_cents"] == 83000


def test_two_device_credits_conflict_when_there_is_one_device(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", sku("iPhone 17"))
    add(conn, store, cid, "tradein", None, line_id="LN-PERSONA-03-1")
    add(conn, store, cid, "new_line", MORE, port_in=True)
    with pytest.raises(DomainError) as err:
        checkout.checkout(conn, store, cid, KEY, [P + "IPHONE17", P + "TRADEIN-ANY"])
    assert err.value.code == "PROMO_CONFLICT"


def test_promotion_results_match_the_schema(conn, store):
    for result in promotions.promotions_for(conn, store, "ACC-PERSONA-02", None):
        PromotionResult.model_validate(result)


# ---- cart: port-in flag ------------------------------------------------------------------------------
def test_port_in_flag_is_carried_by_new_lines_only(conn, store):
    cid = cart_for(conn, store)
    view = add(conn, store, cid, "new_line", MORE, port_in=True)
    assert view["items"][0]["port_in"] is True
    with pytest.raises(DomainError) as err:
        add(conn, store, cid, "addon", "TMO-STUB-ADD-ACC-LENS-PROTECTOR", port_in=True)
    assert err.value.code == "INVALID_ITEM"


def test_device_credits_ask_for_a_device(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "new_line", MORE, port_in=True)
    assert "device" in reasons(evaluate(conn, store, "ACC-PERSONA-03", cid), "IPHONE17")
