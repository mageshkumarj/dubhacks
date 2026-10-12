"""Device protection must cover a real phone: the one on a named line, or an uncovered phone in the cart."""

import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.errors import DomainError  # noqa: E402
from api.services import carts, checkout  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402
from datagen import catalog as dg  # noqa: E402

PROT = "TMO-STUB-ADD-PROT-T{}"


def phone(name: str) -> str:
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


def add(conn, store, cid, kind, sku=None, **kw):
    return carts.add_item(conn, store, cid, kind=kind, sku=sku, **kw)


def code_of(fn, *a, **kw) -> str:
    with pytest.raises(DomainError) as err:
        fn(*a, **kw)
    return err.value.code


def test_tiers_used_by_these_tests_are_what_they_claim():
    names = ("moto g - 2026", "Pixel 10a", "iPhone 13", "iPhone 17")
    assert [dg.device_by_name(n).protection_tier for n in names] == [1, 3, 4, 5]


def test_protection_for_a_phone_in_the_cart(conn, store):
    cid = cart_for(conn, store)
    add(conn, store, cid, "device", phone("Pixel 10a"))
    view = add(conn, store, cid, "addon", PROT.format(3))
    assert next(i for i in view["items"] if i["sku"] == PROT.format(3))["monthly_cents"] == 1300
    assert code_of(add, conn, store, cart_for(conn, store), "addon", PROT.format(3)) == "INVALID_ITEM"


def test_wrong_tier_for_the_phone_in_the_cart_is_refused(conn, store):
    cid = cart_for(conn, store)
    add(conn, store, cid, "device", phone("Pixel 10a"))
    assert code_of(add, conn, store, cid, "addon", PROT.format(5)) == "PROTECTION_TIER_MISMATCH"
    assert carts.get_cart(conn, store, cid)["totals"]["item_count"] == 1  # the refusal left the cart unchanged


def test_protection_with_no_phone_anywhere_is_refused(conn, store):
    message = None
    with pytest.raises(DomainError) as err:
        add(conn, store, cart_for(conn, store), "addon", PROT.format(5))
    message = err.value.message.lower()
    assert err.value.code == "INVALID_ITEM" and "phone" in message and "line_id" in message


def test_two_phones_of_one_tier_take_two_protections_and_no_more(conn, store):
    cid = cart_for(conn, store)
    for _ in range(2):
        add(conn, store, cid, "device", phone("iPhone 17"))
    add(conn, store, cid, "addon", PROT.format(5))
    add(conn, store, cid, "addon", PROT.format(5))
    assert code_of(add, conn, store, cid, "addon", PROT.format(5)) == "DUPLICATE_ITEM"


def test_each_protection_finds_the_phone_of_its_own_tier(conn, store):
    cid = cart_for(conn, store)
    add(conn, store, cid, "device", phone("moto g - 2026"))
    add(conn, store, cid, "device", phone("iPhone 17"))
    add(conn, store, cid, "addon", PROT.format(1))
    add(conn, store, cid, "addon", PROT.format(5))
    assert code_of(add, conn, store, cid, "addon", PROT.format(1)) == "DUPLICATE_ITEM"  # both phones are covered


def test_upgrading_a_line_protects_the_new_phone_not_the_old_one(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-11")  # their current iPhone 14 is tier 4
    add(conn, store, cid, "device", phone("iPhone 18 Pro"), line_id="LN-PERSONA-11-1")  # the new phone is tier 5
    old_tier = code_of(add, conn, store, cid, "addon", PROT.format(4), line_id="LN-PERSONA-11-1")
    assert old_tier == "PROTECTION_TIER_MISMATCH"
    assert add(conn, store, cid, "addon", PROT.format(5), line_id="LN-PERSONA-11-1")


def test_a_line_without_a_new_phone_is_protected_by_its_current_phone(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")  # iPhone 13, tier 4
    wrong = code_of(add, conn, store, cid, "addon", PROT.format(6), line_id="LN-PERSONA-03-1")
    assert wrong == "PROTECTION_TIER_MISMATCH"
    assert add(conn, store, cid, "addon", PROT.format(4), line_id="LN-PERSONA-03-1")


def test_a_line_takes_only_one_protection(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "addon", PROT.format(4), line_id="LN-PERSONA-03-1")
    assert code_of(add, conn, store, cid, "addon", PROT.format(4), line_id="LN-PERSONA-03-1") == "DUPLICATE_ITEM"


def test_checkout_catches_protection_whose_phone_was_removed(conn, store):
    cid = cart_for(conn, store)
    view = add(conn, store, cid, "device", phone("Pixel 10a"))
    device_item = view["items"][0]["item_id"]
    add(conn, store, cid, "addon", PROT.format(3))
    carts.remove_item(conn, store, cid, device_item)
    assert code_of(checkout.checkout, conn, store, cid, "protect-key-01", []) == "PROTECTION_UNMATCHED"
    add(conn, store, cid, "device", phone("Pixel 10a"))  # put the phone back and the same cart checks out
    assert checkout.checkout(conn, store, cid, "protect-key-01", [])["status"] == "confirmed"


def test_checkout_accepts_correctly_matched_protection(conn, store):
    cid = cart_for(conn, store, "ACC-PERSONA-03")
    add(conn, store, cid, "device", phone("iPhone 17"))
    add(conn, store, cid, "addon", PROT.format(5))
    add(conn, store, cid, "addon", PROT.format(4), line_id="LN-PERSONA-03-1")  # the existing phone on the line
    assert checkout.checkout(conn, store, cid, "protect-key-02", [])["totals"]["monthly_cents"] > 0
