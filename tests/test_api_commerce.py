"""HTTP-level commerce tests. Run in CI where FastAPI is installed; skipped where it is not."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

from datagen import catalog as dg  # noqa: E402

FLAGSHIP = dg.device_by_name("iPhone 17").sku
PRICE = dg.device_by_name("iPhone 17").msrp_cents
KEY = {"Idempotency-Key": "idem-key-0001"}


@pytest.fixture()
def client(sandbox_db, monkeypatch):
    monkeypatch.setenv("SANDBOX_DB", str(sandbox_db))
    return TestClient(app)


def new_cart(client, account_id=None) -> str:
    res = client.post("/v1/cart", json={"account_id": account_id})
    assert res.status_code == 201
    return res.json()["data"]["cart_id"]


def test_catalog_browsing(client):
    body = client.get("/v1/catalog/devices?tier=flagship&limit=3").json()
    assert body["success"] and len(body["data"]) == 3 and body["meta"]["limit"] == 3
    assert client.get(f"/v1/catalog/devices/{FLAGSHIP}").json()["data"]["msrp_cents"] == PRICE
    assert len(client.get("/v1/catalog/plans").json()["data"]) == 11
    assert client.get("/v1/catalog/addons?kind=protection").json()["data"][0]["kind"] == "protection"
    assert client.get("/v1/catalog/devices/TMO-STUB-DEV-9999").status_code == 404


def test_tradein_value_and_curve(client):
    value = client.get(f"/v1/tradein/value?device_sku={FLAGSHIP}&age_months=12&condition=fair").json()["data"]
    assert value["value_cents"] < value["base_value_cents"]
    assert len(client.get(f"/v1/tradein/curve/{FLAGSHIP}").json()["data"]) == 61
    assert client.get(f"/v1/tradein/value?device_sku={FLAGSHIP}&age_months=99").status_code == 422
    assert client.get(f"/v1/tradein/value?device_sku={FLAGSHIP}&age_months=1&condition=shattered").status_code == 422


def test_financing_quote_uses_account_credit_tier(client):
    prime = client.post("/v1/financing/quote", json={"device_sku": FLAGSHIP}).json()["data"]
    assert prime["apr"] == 0
    res = client.post("/v1/financing/quote", json={"device_sku": FLAGSHIP, "account_id": "ACC-PERSONA-01"})
    assert res.status_code == 422 and res.json()["error"]["code"] == "DOWN_PAYMENT_TOO_LOW"
    ok = client.post("/v1/financing/quote", json={
        "device_sku": FLAGSHIP, "account_id": "ACC-PERSONA-01", "down_payment_cents": 9300})
    assert ok.json()["data"]["apr"] > 0
    assert client.post("/v1/financing/quote", json={"device_sku": FLAGSHIP, "term_months": 18}).status_code == 422
    assert client.post("/v1/financing/quote", json={"device_sku": FLAGSHIP, "extra": 1}).status_code == 422


def test_full_shopping_journey(client):
    cart_id = new_cart(client, "ACC-PERSONA-03")
    client.post(f"/v1/cart/{cart_id}/items", json={"kind": "device", "sku": FLAGSHIP})
    res = client.post(f"/v1/cart/{cart_id}/items", json={"kind": "tradein", "line_id": "LN-PERSONA-03-1"})
    assert res.status_code == 201 and res.json()["data"]["totals"]["tradein_credit_applied_cents"] > 0
    promos = client.get(f"/v1/promotions?cart_id={cart_id}").json()["data"]
    assert next(p for p in promos if p["sku"] == "PROMO-STUB-TRADEIN-ANY")["eligible"] is True
    body = {"cart_id": cart_id, "promo_skus": ["PROMO-STUB-TRADEIN-ANY"]}
    order = client.post("/v1/checkout", json=body, headers=KEY)
    assert order.status_code == 201 and order.json()["data"]["order_id"].startswith("ORD-")
    replay = client.post("/v1/checkout", json=body, headers=KEY)  # same key and same promo codes: same order
    assert replay.json()["data"]["order_id"] == order.json()["data"]["order_id"]
    different = client.post("/v1/checkout", json={"cart_id": cart_id}, headers=KEY)
    assert different.status_code == 409 and different.json()["error"]["code"] == "IDEMPOTENCY_MISMATCH"


def test_checkout_requires_a_valid_idempotency_key(client):
    cart_id = new_cart(client)
    assert client.post("/v1/checkout", json={"cart_id": cart_id}).status_code == 422
    short = {"Idempotency-Key": "short"}
    assert client.post("/v1/checkout", json={"cart_id": cart_id}, headers=short).status_code == 422
    empty = client.post("/v1/checkout", json={"cart_id": cart_id}, headers=KEY)
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "CART_EMPTY"


def test_cart_error_statuses(client):
    assert client.get("/v1/cart/CART-" + "0" * 32).status_code == 404
    assert client.get("/v1/cart/not-a-cart").status_code == 422
    assert client.post("/v1/cart", json={"account_id": "ACC-NOPE-1"}).status_code == 404
    cart_id = new_cart(client, "ACC-PERSONA-03")
    body = {"kind": "device", "sku": FLAGSHIP, "line_id": "LN-PERSONA-03-1"}
    client.post(f"/v1/cart/{cart_id}/items", json=body)
    assert client.post(f"/v1/cart/{cart_id}/items", json=body).status_code == 409
    too_many = {"kind": "addon", "sku": "xxx", "quantity": 9}
    assert client.post(f"/v1/cart/{cart_id}/items", json=too_many).status_code == 422


def test_remove_item_roundtrip(client):
    cart_id = new_cart(client)
    case = {"kind": "addon", "sku": "TMO-STUB-ADD-ACC-CASE-SILICONE-18PRO"}
    view = client.post(f"/v1/cart/{cart_id}/items", json=case).json()["data"]
    item_id = view["items"][0]["item_id"]
    assert client.delete(f"/v1/cart/{cart_id}/items/{item_id}").json()["data"]["items"] == []
    assert client.delete(f"/v1/cart/{cart_id}/items/{item_id}").status_code == 404


def test_cart_can_be_created_without_a_body(client):
    res = client.post("/v1/cart")
    assert res.status_code == 201 and res.json()["data"]["account_id"] is None


def test_checkout_promo_skus_are_validated_and_mismatched_replay_conflicts(client):
    cart_id = new_cart(client)
    client.post(f"/v1/cart/{cart_id}/items", json={"kind": "addon", "sku": "TMO-STUB-ADD-ACC-CASE-SILICONE-18PRO"})
    bad = client.post("/v1/checkout", json={"cart_id": cart_id, "promo_skus": ["x" * 300]}, headers=KEY)
    assert bad.status_code == 422
    assert client.post("/v1/checkout", json={"cart_id": cart_id}, headers=KEY).status_code == 201
    mismatch = client.post("/v1/checkout", json={"cart_id": cart_id, "promo_skus": ["PROMO-STUB-STUDENT"]}, headers=KEY)
    assert mismatch.status_code == 409 and mismatch.json()["error"]["code"] == "IDEMPOTENCY_MISMATCH"


def test_promotions_conflict_when_account_differs_from_cart(client):
    cart_id = new_cart(client)
    res = client.get(f"/v1/promotions?account_id=ACC-PERSONA-01&cart_id={cart_id}")
    assert res.status_code == 409 and res.json()["error"]["code"] == "ACCOUNT_MISMATCH"


def test_oversized_bodies_are_rejected_before_parsing(client):
    res = client.post("/v1/cart", content=b"x" * 200_000, headers={"content-type": "application/json"})
    assert res.status_code == 413 and res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_protection_must_cover_a_phone_in_the_cart(client):
    cart_id = new_cart(client)
    none = client.post(f"/v1/cart/{cart_id}/items", json={"kind": "addon", "sku": "TMO-STUB-ADD-PROT-T5"})
    assert none.status_code == 422 and none.json()["error"]["code"] == "INVALID_ITEM"
    client.post(f"/v1/cart/{cart_id}/items", json={"kind": "device", "sku": FLAGSHIP})  # iPhone 17, tier 5
    wrong = client.post(f"/v1/cart/{cart_id}/items", json={"kind": "addon", "sku": "TMO-STUB-ADD-PROT-T1"})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "PROTECTION_TIER_MISMATCH"
    right = client.post(f"/v1/cart/{cart_id}/items", json={"kind": "addon", "sku": "TMO-STUB-ADD-PROT-T5"})
    assert right.status_code == 201
