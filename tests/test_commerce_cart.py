import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.errors import DomainError  # noqa: E402
from api.schemas.commerce import CartView, Order  # noqa: E402
from api.services import carts, checkout, promotions  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402
from datagen import catalog as dg  # noqa: E402
from datagen.writer import build_database  # noqa: E402

FLAGSHIP = dg.device_by_name("iPhone 17").sku
PRICE = dg.device_by_name("iPhone 17").msrp_cents  # 929.99
OLD_PHONE = dg.device_by_name("iPhone 13").sku
CASE = "TMO-STUB-ADD-ACC-CASE-SILICONE-18PRO"  # 49.99 one time
PROT = "TMO-STUB-ADD-PROT-T3"  # 13.00 monthly
HINT = "TMO-STUB-ADD-HINT-BASIC"  # 50.00 monthly
VIDEO = "TMO-STUB-ADD-STREAM-VIDEO"  # 3.00 monthly, More/Beyond only
MORE, BEYOND = "TMO-STUB-PLAN-MORE", "TMO-STUB-PLAN-BEYOND"


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


@pytest.fixture()
def store():
    return MemoryStore()


def new_cart(conn, store, account_id=None) -> str:
    return carts.create_cart(conn, store, account_id)["cart_id"]


def add(conn, store, cart_id, kind, sku, **kw):
    return carts.add_item(conn, store, cart_id, kind=kind, sku=sku, **kw)


def err(fn, *a, **kw) -> DomainError:
    with pytest.raises(DomainError) as exc:
        fn(*a, **kw)
    return exc.value


# ---- cart basics ---------------------------------------------------------------------------
def test_create_cart_anonymous_and_for_account(conn, store):
    anon = carts.create_cart(conn, store, None)
    assert anon["cart_id"].startswith("CART-") and anon["account_id"] is None and anon["items"] == []
    assert carts.create_cart(conn, store, "ACC-PERSONA-03")["account_id"] == "ACC-PERSONA-03"
    assert err(carts.create_cart, conn, store, "ACC-NOPE").status_code == 404
    CartView.model_validate(anon)


def test_unknown_cart_is_404(conn, store):
    assert err(carts.get_cart, conn, store, "CART-doesnotexist").code == "CART_NOT_FOUND"


def test_accessory_adds_one_time_cost_scaled_by_quantity(conn, store):
    cid = new_cart(conn, store)
    view = add(conn, store, cid, "addon", CASE, quantity=2)
    assert view["totals"]["due_today_cents"] == 2 * 4999 and view["totals"]["monthly_cents"] == 0


def test_protection_adds_monthly_cost_and_stays_single_quantity(conn, store):
    cid = new_cart(conn, store)
    add(conn, store, cid, "device", dg.device_by_name("Pixel 10a").sku)  # a tier-3 phone for the tier-3 protection
    view = add(conn, store, cid, "addon", PROT)
    assert next(i for i in view["items"] if i["sku"] == PROT)["monthly_cents"] == 1300
    assert err(add, conn, store, cid, "addon", PROT, quantity=2).code == "INVALID_ITEM"


def test_financed_device_is_monthly_with_no_money_down_for_prime(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-03")  # prime
    view = add(conn, store, cid, "device", FLAGSHIP)
    assert view["totals"]["due_today_cents"] == 0 and view["totals"]["monthly_cents"] == PRICE // 24


def test_full_pay_device_is_due_today(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-03")
    view = add(conn, store, cid, "device", FLAGSHIP, payment="full")
    assert view["totals"]["due_today_cents"] == PRICE and view["totals"]["monthly_cents"] == 0


def test_down_payment_applies_for_near_prime_customers(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-01")  # near_prime: 10% down
    view = add(conn, store, cid, "device", FLAGSHIP)
    assert view["totals"]["due_today_cents"] == round(PRICE * 0.10)


def test_tradein_credit_reduces_what_the_customer_pays(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", FLAGSHIP, payment="full")
    view = add(conn, store, cid, "tradein", OLD_PHONE, line_id="LN-PERSONA-03-1")
    credit = view["totals"]["tradein_credit_applied_cents"]
    assert credit > 0 and view["totals"]["due_today_cents"] == PRICE - credit


def test_tradein_validations(conn, store):
    anon = new_cart(conn, store)
    assert err(add, conn, store, anon, "tradein", "x", line_id="LN-PERSONA-03-1").code == "ACCOUNT_REQUIRED"
    byod = new_cart(conn, store, "ACC-PERSONA-01")
    assert err(add, conn, store, byod, "tradein", "x", line_id="LN-PERSONA-01-1").code == "NOT_TRADEIN_ELIGIBLE"
    other = new_cart(conn, store, "ACC-PERSONA-03")
    assert err(add, conn, store, other, "tradein", "x", line_id="LN-PERSONA-02-1").code == "LINE_NOT_FOUND"


def test_new_line_is_priced_by_position_in_the_household(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-02")  # already five lines
    view = add(conn, store, cid, "new_line", MORE)
    assert view["totals"]["monthly_cents"] == 3500  # beyond the published table: the last published line price
    solo = new_cart(conn, store, "ACC-PERSONA-03")  # one line: the new one is the second (15000 - 9000)
    assert add(conn, store, solo, "new_line", MORE)["totals"]["monthly_cents"] == 6000
    assert add(conn, store, new_cart(conn, store), "new_line", MORE)["totals"]["monthly_cents"] == 9000


def test_plan_change_charges_only_the_difference(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-09")  # single line on Essentials (60.00)
    view = add(conn, store, cid, "plan", MORE, line_id="LN-PERSONA-09-1")
    assert view["totals"]["monthly_cents"] == 9000 - 6500


def test_invalid_items_are_rejected(conn, store):
    cid = new_cart(conn, store)
    assert err(add, conn, store, cid, "device", "TMO-STUB-DEV-9999").code == "SKU_NOT_FOUND"
    assert err(add, conn, store, cid, "device", CASE).code == "SKU_NOT_FOUND"  # wrong catalog
    assert err(add, conn, store, cid, "plan", MORE).code == "INVALID_ITEM"  # needs a line
    assert err(add, conn, store, cid, "banana", MORE).code == "INVALID_ITEM"


def test_duplicate_device_for_a_line_is_rejected(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", FLAGSHIP, line_id="LN-PERSONA-03-1")
    assert err(add, conn, store, cid, "device", FLAGSHIP, line_id="LN-PERSONA-03-1").code == "DUPLICATE_ITEM"


def test_cart_size_is_capped(conn, store):
    cid = new_cart(conn, store)
    for _ in range(carts.MAX_ITEMS):
        add(conn, store, cid, "addon", CASE)
    assert err(add, conn, store, cid, "addon", CASE).code == "CART_FULL"


def test_remove_item_updates_totals(conn, store):
    cid = new_cart(conn, store)
    view = add(conn, store, cid, "addon", CASE)
    item_id = view["items"][0]["item_id"]
    assert carts.remove_item(conn, store, cid, item_id)["items"] == []
    assert err(carts.remove_item, conn, store, cid, item_id).code == "ITEM_NOT_FOUND"


def test_store_evicts_oldest_carts_beyond_capacity():
    small = MemoryStore(max_carts=3)
    ids = [small.create(None).cart_id for _ in range(5)]
    assert small.get(ids[0]) is None and small.get(ids[4]) is not None


# ---- promotions ---------------------------------------------------------------------------
def promo(results, sku) -> dict:
    return next(p for p in results if p["sku"] == sku)


def test_promotions_unknown_account_is_none(conn):
    assert promotions.evaluate_promotions(conn, "ACC-NOPE", None) is None


# ---- checkout -----------------------------------------------------------------------------
KEY = "idem-key-0001"


def filled_cart(conn, store, account="ACC-PERSONA-03") -> str:
    cid = new_cart(conn, store, account)
    add(conn, store, cid, "device", FLAGSHIP)
    add(conn, store, cid, "addon", CASE)
    return cid


def test_checkout_creates_order_and_closes_cart(conn, store):
    cid = filled_cart(conn, store)
    order = checkout.checkout(conn, store, cid, KEY, [])
    assert order["order_id"].startswith("ORD-") and order["status"] == "confirmed"
    assert order["totals"]["due_today_cents"] == 4999 and len(order["items"]) == 2
    Order.model_validate(order)
    assert carts.get_cart(conn, store, cid)["status"] == "checked_out"
    assert err(add, conn, store, cid, "addon", CASE).code == "CART_CLOSED"


def test_checkout_is_idempotent_per_key_and_cart(conn, store):
    cid = filled_cart(conn, store)
    first = checkout.checkout(conn, store, cid, KEY, [])
    again = checkout.checkout(conn, store, cid, KEY, [])
    assert again["order_id"] == first["order_id"]
    other = filled_cart(conn, store, "ACC-PERSONA-02")  # keys are scoped to a cart, so no cross-cart collisions
    assert checkout.checkout(conn, store, other, KEY, [])["order_id"] != first["order_id"]


def test_checkout_rejects_empty_closed_and_unknown_carts(conn, store):
    assert err(checkout.checkout, conn, store, new_cart(conn, store), KEY, []).code == "CART_EMPTY"
    assert err(checkout.checkout, conn, store, "CART-nope", KEY, []).code == "CART_NOT_FOUND"
    cid = filled_cart(conn, store)
    checkout.checkout(conn, store, cid, "idem-key-aaaa", [])
    assert err(checkout.checkout, conn, store, cid, "idem-key-bbbb", []).code == "CART_CLOSED"


def test_checkout_applies_only_eligible_promotions(conn, store):
    cid = filled_cart(conn, store)
    assert err(checkout.checkout, conn, store, cid, KEY, ["PROMO-STUB-STUDENT"]).code == "PROMO_NOT_ELIGIBLE"
    assert err(checkout.checkout, conn, store, cid, KEY, ["PROMO-STUB-NOPE"]).code == "PROMO_NOT_ELIGIBLE"
    add(conn, store, cid, "addon", HINT)
    order = checkout.checkout(conn, store, cid, KEY, ["PROMO-STUB-BUNDLE-HINT"])
    assert [p["sku"] for p in order["applied_promotions"]] == ["PROMO-STUB-BUNDLE-HINT"]
    assert order["promo_savings_cents"] == 1500 * 12


def test_order_snapshot_survives_later_store_changes(conn, store):
    cid = filled_cart(conn, store)
    order = checkout.checkout(conn, store, cid, KEY, [])
    order["items"].clear()  # a caller mutating its copy must not corrupt the stored order
    assert len(checkout.checkout(conn, store, cid, KEY, [])["items"]) == 2


# ---- review hardening -------------------------------------------------------------------------
def test_replay_with_different_promotions_is_a_mismatch_not_a_silent_replay(conn, store):
    cid = filled_cart(conn, store)
    add(conn, store, cid, "addon", HINT)
    first = checkout.checkout(conn, store, cid, KEY, ["PROMO-STUB-BUNDLE-HINT"])
    assert checkout.checkout(conn, store, cid, KEY, ["PROMO-STUB-BUNDLE-HINT"])["order_id"] == first["order_id"]
    assert err(checkout.checkout, conn, store, cid, KEY, []).code == "IDEMPOTENCY_MISMATCH"


def test_rejected_item_never_corrupts_the_cart(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-03")
    bad = err(add, conn, store, cid, "tradein", None, line_id="LN-PERSONA-03-1", condition="shattered")
    assert bad.code == "INVALID_CONDITION"
    assert err(add, conn, store, cid, "device", FLAGSHIP, payment="bogus").code == "INVALID_ITEM"
    assert carts.get_cart(conn, store, cid)["items"] == []
    assert add(conn, store, cid, "addon", CASE)["totals"]["item_count"] == 1


def test_store_eviction_is_least_recently_used():
    small = MemoryStore(max_carts=2)
    a, b = small.create(None), small.create(None)
    small.save(a)  # touching a makes b the oldest
    c = small.create(None)
    assert small.get(b.cart_id) is None and small.get(a.cart_id) and small.get(c.cart_id)


def test_promotions_reject_an_account_that_does_not_match_the_cart(conn, store):
    anon = new_cart(conn, store)
    assert err(promotions.promotions_for, conn, store, "ACC-PERSONA-01", anon).code == "ACCOUNT_MISMATCH"
    mine = new_cart(conn, store, "ACC-PERSONA-01")
    assert promotions.promotions_for(conn, store, "ACC-PERSONA-01", mine)
    assert promotions.promotions_for(conn, store, None, mine)
    assert err(promotions.promotions_for, conn, store, "ACC-NOPE", None).code == "ACCOUNT_NOT_FOUND"


def test_credit_is_reported_once_per_side_so_items_never_double_count(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", FLAGSHIP, payment="full")
    view = add(conn, store, cid, "tradein", None, line_id="LN-PERSONA-03-1")
    earned = sum(i["credit_earned_cents"] for i in view["items"])
    applied = sum(i["credit_applied_cents"] for i in view["items"])
    assert earned == view["totals"]["tradein_credit_cents"] > 0
    assert applied == view["totals"]["tradein_credit_applied_cents"] == earned


def test_cart_from_a_previous_dataset_is_stale_not_a_500(conn, store, tmp_path):
    other = connect(build_database(tmp_path / "other.db", seed=99, accounts=5))
    cid = new_cart(conn, store, "ACC-PERSONA-03")
    assert err(carts.get_cart, other, store, cid).code == "CART_STALE"
    other.close()


def test_redundant_items_are_rejected(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-09")  # on Essentials
    add(conn, store, cid, "device", dg.device_by_name("Pixel 10a").sku)
    add(conn, store, cid, "addon", PROT)
    assert err(add, conn, store, cid, "addon", PROT).code == "DUPLICATE_ITEM"  # the only phone is already covered
    add(conn, store, cid, "addon", CASE)
    add(conn, store, cid, "addon", CASE)  # accessories may repeat
    same_plan = err(add, conn, store, cid, "plan", "TMO-STUB-PLAN-ESSENTIALS", line_id="LN-PERSONA-09-1")
    assert same_plan.code == "INVALID_ITEM"
    assert err(add, conn, store, cid, "new_line", MORE, line_id="LN-PERSONA-09-1").code == "INVALID_ITEM"


# ---- security hardening -----------------------------------------------------------------------
def test_cart_ids_carry_128_bits_of_randomness(conn, store):
    cid = new_cart(conn, store)
    assert len(cid) == len("CART-") + 32 and len({new_cart(conn, store) for _ in range(50)}) == 50


def test_idempotency_keys_cannot_be_probed_across_carts(conn, store):
    a = filled_cart(conn, store)
    checkout.checkout(conn, store, a, KEY, [])
    b = filled_cart(conn, store, "ACC-PERSONA-02")
    assert checkout.checkout(conn, store, b, KEY, [])["cart_id"] == b


def test_a_line_cannot_be_traded_in_twice_across_orders(conn, store):
    first = new_cart(conn, store, "ACC-PERSONA-03")
    add(conn, store, first, "device", FLAGSHIP)
    add(conn, store, first, "tradein", None, line_id="LN-PERSONA-03-1")
    checkout.checkout(conn, store, first, KEY, [])
    second = new_cart(conn, store, "ACC-PERSONA-03")
    assert err(add, conn, store, second, "tradein", None, line_id="LN-PERSONA-03-1").code == "TRADEIN_ALREADY_USED"


def test_errors_do_not_echo_long_input(conn, store):
    cid = filled_cart(conn, store)
    message = err(checkout.checkout, conn, store, cid, KEY, ["<script>" + "A" * 500]).message
    assert len(message) < 200


def test_discontinued_devices_cannot_be_bought(conn, store):
    assert err(add, conn, store, new_cart(conn, store), "device", OLD_PHONE).code == "DEVICE_DISCONTINUED"


# ---- plan eligibility and line limits ---------------------------------------------------------
def test_discount_plans_require_the_matching_group(conn, store):
    retirees = new_cart(conn, store, "ACC-PERSONA-08")  # 55+ household
    assert add(conn, store, retirees, "plan", "TMO-STUB-PLAN-MORE-55", line_id="LN-PERSONA-08-1")
    family = new_cart(conn, store, "ACC-PERSONA-02")
    wrong_group = err(add, conn, store, family, "plan", "TMO-STUB-PLAN-MORE-55", line_id="LN-PERSONA-02-1")
    assert wrong_group.code == "PLAN_NOT_ELIGIBLE"
    prospect = new_cart(conn, store)  # not an account yet: eligibility is verified after sign-up
    assert add(conn, store, prospect, "new_line", "TMO-STUB-PLAN-BEYOND-PARTNER")


def test_plan_line_limits_are_enforced(conn, store):
    retirees = new_cart(conn, store, "ACC-PERSONA-08")  # already two lines
    assert err(add, conn, store, retirees, "new_line", "TMO-STUB-PLAN-MORE-55").code == "PLAN_LINE_LIMIT"
    assert err(add, conn, store, new_cart(conn, store, "ACC-PERSONA-02"), "plan", "TMO-STUB-PLAN-ESSENTIALS-SAVER",
               line_id="LN-PERSONA-02-1").code == "PLAN_LINE_LIMIT"  # saver allows 2 lines; the family has 5


def test_four_line_offer_needs_four_lines(conn, store):
    offer = "TMO-STUB-PLAN-ESSENTIALS-4LINE"
    assert err(add, conn, store, new_cart(conn, store, "ACC-PERSONA-03"), "new_line", offer).code == "PLAN_LINE_LIMIT"
    smb = new_cart(conn, store, "ACC-PERSONA-06")  # four lines
    assert add(conn, store, smb, "plan", offer, line_id="LN-PERSONA-06-2")


# ---- add-on rules ---------------------------------------------------------------------------
def test_protection_must_match_the_device_tier_of_the_line(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-03")  # iPhone 13 ($799.99): protection tier 4
    wrong = err(add, conn, store, cid, "addon", "TMO-STUB-ADD-PROT-T6", line_id="LN-PERSONA-03-1")
    assert wrong.code == "PROTECTION_TIER_MISMATCH"
    view = add(conn, store, cid, "addon", "TMO-STUB-ADD-PROT-T4", line_id="LN-PERSONA-03-1")
    assert view["totals"]["monthly_cents"] == 1600


def test_byod_lines_cannot_take_device_protection(conn, store):
    cid = new_cart(conn, store, "ACC-PERSONA-01")
    assert err(add, conn, store, cid, "addon", PROT, line_id="LN-PERSONA-01-1").code == "INVALID_ITEM"


def test_streaming_add_on_needs_an_eligible_plan_family(conn, store):
    assert err(add, conn, store, new_cart(conn, store, "ACC-PERSONA-03"), "addon", VIDEO).code == "ADDON_NOT_ELIGIBLE"
    assert err(add, conn, store, new_cart(conn, store), "addon", VIDEO).code == "ADDON_NOT_ELIGIBLE"
    assert add(conn, store, new_cart(conn, store, "ACC-PERSONA-02"), "addon", VIDEO)["totals"]["monthly_cents"] == 300
    anon = new_cart(conn, store)
    add(conn, store, anon, "new_line", MORE)  # picking an eligible plan unlocks it
    assert add(conn, store, anon, "addon", VIDEO)


def test_beyond_only_connected_line(conn, store):
    line = "TMO-STUB-ADD-LINE-CONNECTED-BEYOND"
    assert err(add, conn, store, new_cart(conn, store, "ACC-PERSONA-02"), "addon", line).code == "ADDON_NOT_ELIGIBLE"
    assert add(conn, store, new_cart(conn, store, "ACC-PERSONA-10"), "addon", line)["totals"]["monthly_cents"] == 500
