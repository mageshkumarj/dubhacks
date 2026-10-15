import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.errors import DomainError  # noqa: E402
from api.services import carts, checkout  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402

FOUR_LINE = "TMO-STUB-PLAN-ESSENTIALS-4LINE"
ESSENTIALS = "TMO-STUB-PLAN-ESSENTIALS"
MORE_55 = "TMO-STUB-PLAN-MORE-55"


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


@pytest.fixture()
def store():
    return MemoryStore()


def _cart(conn, store, account_id):
    return carts.create_cart(conn, store, account_id)["cart_id"]


def _add(conn, store, cid, kind, sku, **kw):
    return carts.add_item(conn, store, cid, kind=kind, sku=sku, **kw)


def _code(fn, *a, **kw):
    with pytest.raises(DomainError) as exc:
        fn(*a, **kw)
    return exc.value.code


def _family_four_line_cart(conn, store):
    cid = _cart(conn, store, "ACC-PERSONA-12")
    view = _add(conn, store, cid, "new_line", FOUR_LINE)
    new_line_item = view["items"][0]["item_id"]
    for n in (1, 2, 3):
        view = _add(conn, store, cid, "plan", FOUR_LINE, line_id=f"LN-PERSONA-12-{n}")
    return cid, new_line_item, view


def test_family_adding_fourth_line_can_switch_to_four_line_offer(conn, store):
    _, _, view = _family_four_line_cart(conn, store)
    assert view["totals"]["monthly_cents"] == 0  # 4th line at no extra monthly cost


def test_plan_switch_without_the_new_line_is_rejected_when_added(conn, store):
    cid = _cart(conn, store, "ACC-PERSONA-12")
    assert _code(_add, conn, store, cid, "plan", FOUR_LINE, line_id="LN-PERSONA-12-1") == "PLAN_LINE_LIMIT"


def test_removing_the_new_line_blocks_checkout(conn, store):
    cid, new_line_item, _ = _family_four_line_cart(conn, store)
    carts.remove_item(conn, store, cid, new_line_item)
    assert _code(checkout.checkout, conn, store, cid, "idem-wp3-plan-limit-1", []) == "PLAN_LINE_LIMIT"


def test_valid_four_line_cart_checks_out(conn, store):
    cid, _, _ = _family_four_line_cart(conn, store)
    assert checkout.checkout(conn, store, cid, "idem-wp3-plan-limit-2", [])["status"] == "confirmed"


def test_adding_a_line_blocks_moving_a_couple_to_the_two_line_cap(conn, store):
    cid = _cart(conn, store, "ACC-PERSONA-38")  # 2 lines, 55+
    _add(conn, store, cid, "new_line", ESSENTIALS)
    assert _code(_add, conn, store, cid, "plan", MORE_55, line_id="LN-PERSONA-38-1") == "PLAN_LINE_LIMIT"


def test_adding_a_line_after_a_capped_plan_switch_blocks_checkout(conn, store):
    cid = _cart(conn, store, "ACC-PERSONA-38")
    _add(conn, store, cid, "plan", MORE_55, line_id="LN-PERSONA-38-1")
    _add(conn, store, cid, "new_line", ESSENTIALS)
    assert _code(checkout.checkout, conn, store, cid, "idem-wp3-plan-limit-3", []) == "PLAN_LINE_LIMIT"
