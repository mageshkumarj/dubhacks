import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from datagen.writer import build_database  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    build_database(tmp_path / "t.db", seed=1, accounts=20)
    monkeypatch.setenv("SANDBOX_DB", str(tmp_path / "t.db"))
    return TestClient(app)


def test_health_uses_envelope_and_stub_header(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.headers["X-Data-Source"] == "stub"


def test_ready_reports_dataset_metadata(client):
    body = client.get("/ready").json()
    assert body["data"]["dataset"]["data_source"] == "stub"


def test_ready_returns_503_when_dataset_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_DB", str(tmp_path / "missing.db"))
    res = TestClient(app).get("/ready")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "DATASET_UNAVAILABLE"


def test_openapi_docs_available(client):
    assert client.get("/openapi.json").status_code == 200


def test_ready_503_when_metadata_table_missing(monkeypatch, tmp_path):
    import sqlite3

    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    monkeypatch.setenv("SANDBOX_DB", str(empty))
    assert TestClient(app).get("/ready").status_code == 503


def test_404_and_validation_errors_use_envelope(client):
    body = client.get("/nope").json()
    assert body["success"] is False and body["error"]["code"] == "HTTP_404"
