import pytest

pytest.importorskip("pydantic")

from api.db import connect  # noqa: E402
from api.services import carts, checkout  # noqa: E402
from api.services.store import MemoryStore  # noqa: E402
from datagen import catalog as dg  # noqa: E402

NEW_PHONE = dg.device_by_name("iPhone 18 Pro").sku


@pytest.fixture(scope="module")
def conn(sandbox_db):
    connection = connect(sandbox_db)
    yield connection
    connection.close()


def _line(conn, line_id):
    return conn.execute(
        "SELECT financing_balance_cents, monthly_installment_cents, financing_months_remaining "
        "FROM lines WHERE line_id = ?", (line_id,)
    ).fetchone()


def _cart(conn, account_id, line_id):
    store = MemoryStore()
    cid = carts.create_cart(conn, store, account_id)["cart_id"]
    carts.add_item(conn, store, cid, kind="device", sku=NEW_PHONE)
    view = carts.add_item(conn, store, cid, kind="tradein", sku=None, line_id=line_id)
    return store, cid, view


def test_tradein_with_balance_charges_payoff_and_drops_old_installment(conn):
    owed, installment, remaining = _line(conn, "LN-PERSONA-07-1")
    assert owed > 0 and remaining > 0
    _, _, view = _cart(conn, "ACC-PERSONA-07", "LN-PERSONA-07-1")
    item = next(i for i in view["items"] if i["kind"] == "tradein")
    assert item["balance_owed_cents"] == owed
    assert item["due_today_cents"] == owed
    assert item["monthly_cents"] == -installment
    assert view["totals"]["tradein_balance_owed_cents"] == owed


def test_totals_still_equal_sum_of_items(conn):
    _, _, view = _cart(conn, "ACC-PERSONA-07", "LN-PERSONA-07-1")
    assert view["totals"]["due_today_cents"] == sum(i["due_today_cents"] for i in view["items"])
    assert view["totals"]["monthly_cents"] == sum(i["monthly_cents"] for i in view["items"])


def test_paid_off_phone_owes_nothing(conn):
    owed, _, remaining = _line(conn, "LN-PERSONA-03-1")
    assert owed == 0 and remaining == 0
    _, _, view = _cart(conn, "ACC-PERSONA-03", "LN-PERSONA-03-1")
    item = next(i for i in view["items"] if i["kind"] == "tradein")
    assert (item["balance_owed_cents"], item["due_today_cents"], item["monthly_cents"]) == (0, 0, 0)
    assert view["totals"]["tradein_balance_owed_cents"] == 0


def test_non_tradein_items_report_zero_balance(conn):
    _, _, view = _cart(conn, "ACC-PERSONA-03", "LN-PERSONA-03-1")
    assert next(i for i in view["items"] if i["kind"] == "device")["balance_owed_cents"] == 0


def test_order_reuses_balance_in_cart_view(conn):
    store, cid, view = _cart(conn, "ACC-PERSONA-07", "LN-PERSONA-07-1")
    order = checkout.checkout(conn, store, cid, "idem-wp2-balance-0001", [])
    assert order["totals"]["tradein_balance_owed_cents"] == view["totals"]["tradein_balance_owed_cents"]
