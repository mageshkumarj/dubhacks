import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import MAX_BODY_BYTES, app  # noqa: E402
from datagen.writer import build_database  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    build_database(tmp_path / "t.db", seed=1, accounts=20)
    monkeypatch.setenv("SANDBOX_DB", str(tmp_path / "t.db"))
    return TestClient(app)


def _chunks(total: int, size: int = 8192):
    sent = 0
    while sent < total:
        piece = min(size, total - sent)
        sent += piece
        yield b"x" * piece


def test_chunked_body_over_the_cap_is_rejected_with_the_envelope(client):
    res = client.post("/v1/cart", content=_chunks(1_000_000), headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert res.headers["X-Data-Source"] == "stub"
    assert res.headers["access-control-allow-origin"] == "*"


def test_chunked_body_under_the_cap_still_reaches_validation(client):
    res = client.post("/v1/cart", content=_chunks(1_000))
    assert res.status_code != 413


def test_declared_oversize_body_is_still_rejected_up_front(client):
    res = client.post("/v1/cart", content=b"x" * (MAX_BODY_BYTES + 1))
    assert res.status_code == 413 and res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_body_exactly_at_the_cap_is_accepted(client):
    res = client.post("/v1/cart", content=b"x" * MAX_BODY_BYTES)
    assert res.status_code != 413
