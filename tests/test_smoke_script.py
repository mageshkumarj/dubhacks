"""The smoke-test script must pass on a healthy sandbox and must catch real problems."""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from scripts import smoke_test  # noqa: E402


class InProcess:
    """Lets the script talk to the app in-process through the same interface as a real HTTP connection."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def request(self, method, target, body=None, headers=None):
        raw_headers = {k: v.encode("latin-1") for k, v in (headers or {}).items()}  # httpx insists on ASCII str values
        response = self.client.request(method, target, content=body, headers=raw_headers)
        return response.status_code, {k.lower(): v for k, v in response.headers.items()}, response.text


class Tampered(InProcess):
    """Returns whatever a test wants for chosen requests, to prove the script notices."""

    def __init__(self, client: TestClient, rule) -> None:
        super().__init__(client)
        self.rule = rule

    def request(self, method, target, body=None, headers=None):
        replaced = self.rule(method, target)
        return replaced if replaced else super().request(method, target, body, headers)


@pytest.fixture()
def client(sandbox_db, monkeypatch):
    monkeypatch.setenv("SANDBOX_DB", str(sandbox_db))
    return TestClient(app, follow_redirects=False)


def run(adapter, fuzz=False, device_limit=6):
    return smoke_test.run(
        adapter, full=False, fuzz=fuzz, workers=1, sample=40, device_limit=device_limit, log=lambda *_: None
    )


def test_a_healthy_sandbox_passes_cleanly(client):
    report = run(InProcess(client), fuzz=True, device_limit=None)  # the hostile-input checks are included only here, to keep tests quick
    assert report.failures == [] and report.coverage_gaps == [] and report.ok
    assert report.requests > 1500 and report.checks > 1500


def test_running_it_twice_on_the_same_server_still_passes(client):
    adapter = InProcess(client)
    assert run(adapter).ok and run(adapter).ok  # state left by the first run (carts, orders) must not break the second


def test_a_server_error_is_reported(client):
    broken = Tampered(client, lambda m, t: (500, {"x-data-source": "stub"}, "boom") if t.startswith("/v1/catalog/plans") else None)
    report = run(broken)
    assert not report.ok and any("SERVER ERROR" in f for f in report.failures)
    assert any("COULD NOT COMPLETE" in f for f in report.failures) or report.requests > 0  # it reported, it did not crash


def test_a_missing_envelope_is_reported(client):
    bare = Tampered(client, lambda m, t: (200, {"x-data-source": "stub"}, json.dumps({"hello": 1})) if t == "/ready" else None)
    assert any("ENVELOPE" in f for f in run(bare).failures)


def test_a_redirect_is_reported(client):
    redirect = Tampered(client, lambda m, t: (307, {"x-data-source": "stub", "location": "/x"}, "") if t.startswith("/v1/personas") else None)
    assert any("REDIRECT" in f for f in run(redirect).failures)


def test_a_missing_stub_header_is_reported(client):
    unmarked = Tampered(client, lambda m, t: (200, {}, json.dumps({"success": True, "data": {}, "error": None, "meta": {}, "data_source": "stub"})) if t == "/health" else None)
    assert any("STUB HEADER" in f for f in run(unmarked).failures)


def test_a_new_documented_parameter_that_is_never_exercised_is_reported(client):
    def add_parameter(method, target):
        if target != "/openapi.json":
            return None
        spec = client.get("/openapi.json").json()
        spec["paths"]["/v1/accounts"]["get"]["parameters"].append({"name": "brand_new_filter", "in": "query", "schema": {}})
        return 200, {"x-data-source": "stub"}, json.dumps(spec)

    report = run(Tampered(client, add_parameter))
    assert any("brand_new_filter" in gap for gap in report.coverage_gaps) and not report.ok


def test_an_endpoint_that_starts_failing_validation_is_reported(client):
    wrong = Tampered(client, lambda m, t: (200, {"x-data-source": "stub"}, json.dumps({"success": True, "data": [], "error": None, "meta": {}, "data_source": "stub"})) if t.startswith("/v1/catalog/addons?kind=protection") else None)
    assert not run(wrong).ok  # an empty list where protection add-ons must exist
