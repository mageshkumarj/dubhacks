import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import MAX_BODY_BYTES, app  # noqa: E402
from datagen.writer import build_database  # noqa: E402

ORIGIN = "http://localhost:5173"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    build_database(tmp_path / "t.db", seed=1, accounts=20)
    monkeypatch.setenv("SANDBOX_DB", str(tmp_path / "t.db"))
    return TestClient(app)


def test_preflight_allows_browser_requests(client):
    res = client.options("/v1/cart", headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type, idempotency-key",
    })
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "*"
    allowed = res.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed and "idempotency-key" in allowed


def test_simple_response_carries_allow_origin_and_exposes_stub_header(client):
    res = client.get("/health", headers={"Origin": ORIGIN})
    assert res.headers["access-control-allow-origin"] == "*"
    assert "x-data-source" in res.headers["access-control-expose-headers"].lower()


def test_error_responses_carry_allow_origin(client):
    res = client.get("/v1/does-not-exist", headers={"Origin": ORIGIN})
    assert res.status_code == 404
    assert res.headers["access-control-allow-origin"] == "*"


def test_payload_too_large_carries_allow_origin(client):
    res = client.post("/v1/cart", content=b"x" * (MAX_BODY_BYTES + 1), headers={"Origin": ORIGIN})
    assert res.status_code == 413
    assert res.headers["access-control-allow-origin"] == "*"
