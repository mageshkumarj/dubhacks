"""HTTP-level tests. Run in CI where FastAPI is installed; skipped where it is not."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


@pytest.fixture()
def client(sandbox_db, monkeypatch):
    monkeypatch.setenv("SANDBOX_DB", str(sandbox_db))
    return TestClient(app)


def test_list_accounts_has_pagination_meta(client):
    body = client.get("/v1/accounts?limit=5").json()
    assert body["success"] and len(body["data"]) == 5
    assert body["meta"] == {"total": 342, "limit": 5, "offset": 0}


def test_persona_only_filter(client):
    assert len(client.get("/v1/accounts?persona_only=true&limit=100").json()["data"]) == 42


def test_household_and_context_roundtrip(client):
    assert len(client.get("/v1/households/ACC-PERSONA-02").json()["data"]["lines"]) == 5
    ctx = client.get("/v1/customers/ACC-PERSONA-03/context").json()["data"]
    assert ctx["lines"][0]["upgrade_eligible"] is True


def test_unknown_account_is_404_with_envelope(client):
    res = client.get("/v1/customers/ACC-NOPE-1/context")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "HTTP_404"


def test_bad_account_id_is_rejected_before_the_database(client):
    res = client.get("/v1/households/x'%20OR%20'1'='1")
    assert res.status_code == 422 and res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "segment=Fam!ly"])
def test_list_accounts_rejects_bad_params(client, query):
    assert client.get(f"/v1/accounts?{query}").status_code == 422


def test_usage_filters_and_validates(client):
    rows = client.get("/v1/customers/ACC-PERSONA-02/usage?line_id=LN-PERSONA-02-1&months=3").json()["data"]
    assert len(rows) == 3
    assert client.get("/v1/customers/ACC-PERSONA-02/usage?months=13").status_code == 422
    assert client.get("/v1/customers/ACC-PERSONA-02/usage?line_id=LN-PERSONA-01-1").status_code == 404


def test_billing_and_support_endpoints(client):
    assert len(client.get("/v1/customers/ACC-PERSONA-04/billing").json()["data"]) == 12
    support = client.get("/v1/customers/ACC-PERSONA-04/support-interactions?limit=2").json()["data"]
    assert len(support) == 2


def test_every_response_is_marked_stub(client):
    res = client.get("/v1/accounts?limit=1")
    assert res.headers["X-Data-Source"] == "stub" and res.json()["data_source"] == "stub"


def test_offset_is_bounded_and_trailing_newline_id_rejected(client):
    assert client.get("/v1/accounts?offset=99999999999999999999").status_code == 422
    assert client.get("/v1/households/ACC-PERSONA-01%0A").status_code == 422


def test_ready_exposes_only_allowlisted_metadata(client):
    keys = set(client.get("/ready").json()["data"]["dataset"])
    assert "seed" not in keys and "data_source" in keys


def test_missing_dataset_is_503_not_500(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_DB", str(tmp_path / "missing.db"))
    res = TestClient(app, raise_server_exceptions=False).get("/v1/accounts")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "DATASET_UNAVAILABLE"
    assert res.headers["X-Data-Source"] == "stub"


def test_openapi_documents_error_envelopes(client):
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/v1/households/{account_id}"]["get"]["responses"]
    assert "404" in responses and "422" in responses


def test_personas_by_theme_and_detail(client):
    body = client.get("/v1/personas?theme=timekeeper").json()
    assert body["meta"]["total"] == 10 and all(p["primary_theme"] == "timekeeper" for p in body["data"])
    prospects = client.get("/v1/personas?kind=prospect").json()["data"]
    assert len(prospects) == 8 and all(p["account_id"] is None for p in prospects)
    detail = client.get("/v1/personas/ACC-PERSONA-11").json()["data"]
    assert detail["starting_cart"][0]["kind"] == "device"
    assert client.get("/v1/personas/NOPE-99").status_code == 404
    assert client.get("/v1/personas?theme=bogus").status_code == 422


EMPTY_PATHS = ["/v1/cart/", "/v1/personas/", "/v1/catalog/devices/", "/v1/catalog/plans/", "/v1/households/"]


@pytest.mark.parametrize("path", EMPTY_PATHS)
def test_empty_path_values_get_the_error_envelope_not_a_redirect(sandbox_db, monkeypatch, path):
    monkeypatch.setenv("SANDBOX_DB", str(sandbox_db))
    res = TestClient(app, follow_redirects=False).get(path)
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False and body["error"]["code"] == "HTTP_404"
    assert res.headers["X-Data-Source"] == "stub"
