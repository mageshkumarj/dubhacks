"""One device offer per phone, trade-in device age, and the accessory bundle cap."""

from datetime import date

import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.errors import DomainError  # noqa: E402
from api.services import carts, checkout, promotions  # noqa: E402
from api.services.common import as_of, months_between  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402
from datagen import catalog as dg  # noqa: E402

P = "PROMO-STUB-"
IPHONE_OFFER, TRADEIN_ANY = P + "IPHONE18PRO", P + "TRADEIN-ANY"
IPHONE, PIXEL = dg.device_by_name("iPhone 18 Pro").sku, dg.device_by_name("Pixel 11").sku
EARBUDS, CASE = "TMO-STUB-ADD-ACC-EARBUDS", "TMO-STUB-ADD-ACC-CASE-SILICONE-18PRO"


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


@pytest.fixture()
def store():
    return MemoryStore()


def _cart(conn, store, account, items):
    cid = carts.create_cart(conn, store, account)["cart_id"]
    for kind, sku, extra in items:
        carts.add_item(conn, store, cid, kind=kind, sku=sku, **extra)
    return cid


def _checkout(conn, store, cid, promos):
    return checkout.checkout(conn, store, cid, f"idem-wp4-{cid}-{len(promos)}", promos)


def _conflict(conn, store, cid, promos):
    with pytest.raises(DomainError) as exc:
        _checkout(conn, store, cid, promos)
    return exc.value


# ---- B2: one device offer per phone --------------------------------------------------------------------
def _beyond_cart(conn, store, account, line, phones):
    items = [("device", sku, {}) for sku in phones] + [("tradein", None, {"line_id": line})]
    return _cart(conn, store, account, items)


def test_two_offers_cannot_both_apply_to_two_identical_phones(conn, store):
    cid = _beyond_cart(conn, store, "ACC-PERSONA-31", "LN-PERSONA-31-1", [IPHONE, IPHONE])
    err = _conflict(conn, store, cid, [IPHONE_OFFER, TRADEIN_ANY])
    assert err.code == "PROMO_CONFLICT" and TRADEIN_ANY in err.message


def test_each_phone_gets_its_own_offer(conn, store):
    cid = _beyond_cart(conn, store, "ACC-PERSONA-33", "LN-PERSONA-33-1", [IPHONE, PIXEL])
    order = _checkout(conn, store, cid, [IPHONE_OFFER, TRADEIN_ANY])
    assert order["promo_savings_cents"] == 120000
    assert {a["sku"]: a["savings_cents"] for a in order["applied_promotions"]} == {
        IPHONE_OFFER: 100000, TRADEIN_ANY: 20000,
    }


def test_one_offer_can_cover_both_phones(conn, store):
    cid = _beyond_cart(conn, store, "ACC-PERSONA-31", "LN-PERSONA-31-1", [IPHONE, IPHONE])
    assert _checkout(conn, store, cid, [IPHONE_OFFER])["promo_savings_cents"] == 200000


def test_two_offers_cannot_share_a_single_phone(conn, store):
    cid = _beyond_cart(conn, store, "ACC-PERSONA-31", "LN-PERSONA-31-1", [IPHONE])
    assert _conflict(conn, store, cid, [IPHONE_OFFER, TRADEIN_ANY]).code == "PROMO_CONFLICT"


# ---- B3: device age is about the phone being traded in ---------------------------------------------------
def _mixed_age_account(conn):
    today = as_of(conn)
    for (account,) in conn.execute("SELECT account_id FROM accounts WHERE account_id NOT LIKE 'ACC-PERSONA-%'"):
        rows = conn.execute(
            "SELECT line_id, device_purchase_date, tradein_eligible FROM lines "
            "WHERE account_id = ? AND device_sku IS NOT NULL", (account,)
        ).fetchall()
        aged = [
            (r["line_id"], months_between(date.fromisoformat(r["device_purchase_date"]), today), r["tradein_eligible"])
            for r in rows
        ]
        if any(m >= 36 for _, m, _ in aged):
            young = [line for line, m, ok in aged if m < 36 and ok]
            if young:
                return account, young[0]
    pytest.skip("no household with both an old phone and a trade-in-eligible young phone")


def test_old_phone_credit_checks_the_phone_traded_in(conn, store):
    account, young_line = _mixed_age_account(conn)
    cid = _cart(conn, store, account, [("device", PIXEL, {}), ("tradein", None, {"line_id": young_line})])
    promo = next(p for p in promotions.promotions_for(conn, store, None, cid) if p["sku"] == P + "OLD-PHONE-UPGRADE")
    assert not promo["eligible"]
    assert any("36" in r for r in promo["reasons"])


# ---- B5: accessory bundle cap -----------------------------------------------------------------------------
def _bundle_savings(conn, store, items):
    cid = _cart(conn, store, None, items)
    promo = next(p for p in promotions.promotions_for(conn, store, None, cid) if p["sku"] == P + "ACC-BUNDLE")
    assert promo["eligible"]
    return promo["estimated_savings_cents"]


def test_accessory_bundle_discounts_at_most_six_units(conn, store):
    assert _bundle_savings(conn, store, [("addon", EARBUDS, {"quantity": 5})] * 5) == 13499


def test_accessory_bundle_keeps_the_most_expensive_units(conn, store):
    items = [("addon", CASE, {"quantity": 6}), ("addon", EARBUDS, {"quantity": 2})]
    assert _bundle_savings(conn, store, items) == 9499  # 25% of 2 x 8999 + 4 x 4999


def test_accessory_bundle_unchanged_at_or_below_the_cap(conn, store):
    assert _bundle_savings(conn, store, [("addon", EARBUDS, {"quantity": 3})]) == 6749  # 25% of 3 x 8999
