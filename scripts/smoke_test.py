#!/usr/bin/env python3
"""Smoke test for a running sandbox. Standard library only, so nothing needs installing.

    python scripts/smoke_test.py                         # quick check of http://localhost:8000
    python scripts/smoke_test.py --full                  # every account (about a minute)
    python scripts/smoke_test.py --base-url https://host # a hosted instance

It exercises every endpoint with every documented parameter and body field filled in, checks the answers for
consistency, tries hostile input on every parameter (nothing may answer 5xx), and compares what it exercised with the
API's own OpenAPI document, so a parameter added later fails this test until it is covered here.

It is safe on a shared instance: it never checks out a persona's cart (that would use up their trade-ins), and its
one checkout uses a throwaway anonymous cart. Exit code 0 means everything passed.
"""

import argparse
import collections
import http.client
import json
import random
import sys
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

ENVELOPE_KEYS = {"success", "data", "error", "meta", "data_source"}
EVIL = [
    "x" * 5000, "' OR '1'='1", "../../etc/passwd", "%00", "-1", "999999999999999999999999", "null", "[]", "{}",
    "\U0001F600", "<script>alert(1)</script>", "1; DROP TABLE accounts", "", " ",
]
SLOW_SECONDS = 2.0


class HttpClient:
    """A tiny keep-alive HTTP client. Anything with the same `request` method can stand in for it."""

    def __init__(self, base_url: str) -> None:
        parts = urllib.parse.urlsplit(base_url)
        self.https, self.host, self.port = parts.scheme == "https", parts.hostname, parts.port
        self.local = threading.local()

    def _connect(self) -> http.client.HTTPConnection:
        factory = http.client.HTTPSConnection if self.https else http.client.HTTPConnection
        return factory(self.host, self.port, timeout=30)

    def request(self, method: str, target: str, body: bytes | None = None, headers: dict | None = None):
        for _ in range(2):  # one retry if a kept-alive connection was closed by the server
            conn = getattr(self.local, "conn", None) or self._connect()
            self.local.conn = conn
            try:
                conn.request(method, target, body=body, headers=headers or {})
                response = conn.getresponse()
                return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read().decode()
            except (OSError, http.client.HTTPException):
                conn.close()
                self.local.conn = None
        return 0, {}, "connection failed"


@dataclass
class Report:
    requests: int = 0
    checks: int = 0
    failures: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    slow: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.failures and not self.coverage_gaps


class Runner:
    def __init__(self, client, workers: int) -> None:
        self.client, self.workers = client, workers
        self.report, self.lock = Report(), threading.Lock()
        self.covered: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)

    def fail(self, message: str) -> None:
        with self.lock:
            if sum(1 for f in self.report.failures if f.split(":")[0] == message.split(":")[0]) < 25:
                self.report.failures.append(message)

    def expect(self, condition: bool, what: str, *context) -> None:
        with self.lock:
            self.report.checks += 1
        if not condition:
            self.fail(f"CHECK FAILED: {what} {' '.join(str(c)[:80] for c in context)}")

    def call(self, method, template, path, body=None, headers=None, query=None, raw=None):
        """`template` is the OpenAPI path template, used to record which parameters were exercised."""
        with self.lock:
            used = self.covered[(method, template)]
            used.add(("called", ""))
            used.update(("q", k) for k in (query or {}))
            used.update(("b", k) for k in (body or {}))
            used.update(("h", k.lower()) for k in (headers or {}))
        target = path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        started = time.time()
        status, response_headers, text = self.client.request(
            method, target, data, {"Content-Type": "application/json", **(headers or {})}
        )
        with self.lock:
            self.report.requests += 1
            if time.time() - started > SLOW_SECONDS:
                self.report.slow.append(f"{method} {path} took {time.time() - started:.1f}s")
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        self._judge(method, path, status, response_headers, parsed, text)
        return status, parsed

    def _judge(self, method, path, status, headers, parsed, text) -> None:
        where = f"{method} {path[:70]} -> {status}"
        if status == 0 or status >= 500:
            self.fail(f"SERVER ERROR: {where} {text[:100]}")
        elif 300 <= status < 400:
            self.fail(f"UNEXPECTED REDIRECT: {where}")
        elif parsed is None or not isinstance(parsed, dict) or set(parsed) != ENVELOPE_KEYS:
            self.fail(f"BAD ENVELOPE: {where} {text[:100]}")
        elif headers.get("x-data-source") != "stub":
            self.fail(f"MISSING STUB HEADER: {where}")

    def each(self, fn, items) -> None:
        if self.workers <= 1:
            for item in items:
                fn(item)
            return
        with ThreadPoolExecutor(self.workers) as pool:
            list(pool.map(fn, items))


def get(r: Runner, template: str, path: str | None = None, **kw):
    return r.call("GET", template, path or template, **kw)


def data_of(response):
    status, body = response
    return body["data"] if status == 200 and body else []


@dataclass
class Reference:
    devices: list
    plans: list
    addons: list
    personas: list
    account_ids: list


def load_reference(r: Runner, full: bool, sample: int) -> Reference:
    devices = data_of(get(r, "/v1/catalog/devices", query={"limit": 200, "status": "all"}))
    plans, addons = data_of(get(r, "/v1/catalog/plans")), data_of(get(r, "/v1/catalog/addons"))
    personas = data_of(get(r, "/v1/personas", query={"limit": 100}))
    status, first = get(r, "/v1/accounts", query={"limit": 200, "offset": 0})
    ids = [a["account_id"] for a in first["data"]] if status == 200 else []
    total = first["meta"]["total"] if status == 200 else 0
    if full:
        for offset in range(200, total, 200):
            ids += [a["account_id"] for a in data_of(get(r, "/v1/accounts", query={"limit": 200, "offset": offset}))]
    else:
        ids = random.Random(7).sample(ids, min(sample, len(ids)))
    ids += [p["account_id"] for p in personas if p["account_id"] and p["account_id"] not in ids]
    return Reference(devices, plans, addons, personas, ids)


# ------------------------------------------------------------------------------------------------ platform and lists
def check_platform(r: Runner) -> None:
    for path in ("/health", "/ready"):
        r.expect(get(r, path)[0] == 200, f"GET {path} answers 200")
    for segment in ("student", "single", "couple", "family", "smb", "senior"):
        for persona_only in ("true", "false"):
            status, _ = get(r, "/v1/accounts", query={
                "segment": segment, "persona_only": persona_only, "limit": 200, "offset": 0})
            r.expect(status == 200, "accounts list with every filter", segment, persona_only)
    for limit, offset in ((1, 0), (200, 0), (1, 100000), (200, 100000)):
        r.expect(get(r, "/v1/accounts", query={"limit": limit, "offset": offset})[0] == 200, "limit/offset edges")


def check_account(r: Runner, account_id: str) -> None:
    statuses = {}
    household = get(r, "/v1/households/{account_id}", f"/v1/households/{account_id}")
    context = get(r, "/v1/customers/{account_id}/context", f"/v1/customers/{account_id}/context")
    usage = get(r, "/v1/customers/{account_id}/usage", f"/v1/customers/{account_id}/usage", query={"months": 12})
    billing = get(r, "/v1/customers/{account_id}/billing", f"/v1/customers/{account_id}/billing")
    support = get(r, "/v1/customers/{account_id}/support-interactions",
                  f"/v1/customers/{account_id}/support-interactions", query={"limit": 200})
    statuses = [household[0], context[0], usage[0], billing[0], support[0]]
    r.expect(statuses == [200] * 5, "all five customer endpoints answer 200", account_id, statuses)
    if statuses != [200] * 5:
        return
    lines = len(household[1]["data"]["lines"])
    r.expect(context[1]["data"]["eligibility"]["line_count"] == lines, "household and context agree on lines", account_id)
    r.expect(len(usage[1]["data"]) <= 12 * lines, "at most 12 usage months per line", account_id)
    months = [b["month"] for b in billing[1]["data"]]
    r.expect(months == sorted(months), "billing is chronological", account_id)
    dates = [s["interaction_date"] for s in support[1]["data"]]
    r.expect(dates == sorted(dates, reverse=True), "support contacts are newest first", account_id)
    reasons = {"stable", "device_installment", "installment_ended", "promo_expired"}
    r.expect(all(b["change_reason"] in reasons for b in billing[1]["data"]), "billing change reasons are valid", account_id)


def check_usage_filters(r: Runner, ref: Reference) -> None:
    multi = next((p["account_id"] for p in ref.personas if p["account_id"] and p["account_id"].endswith("02")), None)
    if not multi:
        return
    lines = [ln["line_id"] for ln in data_of(get(r, "/v1/households/{account_id}", f"/v1/households/{multi}"))["lines"]]
    for line_id in lines:
        for months in (1, 6, 12):
            status, body = get(r, "/v1/customers/{account_id}/usage", f"/v1/customers/{multi}/usage",
                               query={"line_id": line_id, "months": months})
            rows = body["data"] if status == 200 else []
            r.expect(status == 200 and len(rows) <= months and all(x["line_id"] == line_id for x in rows),
                     "usage honors line_id and months", multi, line_id, months)
    for limit in (1, 5, 200):
        status, body = get(r, "/v1/customers/{account_id}/support-interactions",
                           f"/v1/customers/{multi}/support-interactions", query={"limit": limit})
        r.expect(status == 200 and len(body["data"]) <= limit, "support honors limit", limit)


# ------------------------------------------------------------------------------------------------ catalog and pricing
def check_device(r: Runner, device: dict, full: bool) -> None:
    sku = device["sku"]
    status, body = get(r, "/v1/catalog/devices/{sku}", f"/v1/catalog/devices/{sku}")
    r.expect(status == 200 and body["data"] == device, "device detail equals its list entry", sku)
    curve = data_of(get(r, "/v1/tradein/curve/{sku}", f"/v1/tradein/curve/{sku}"))
    r.expect(len(curve) == 61 and all(a["value_cents"] >= b["value_cents"] for a, b in zip(curve, curve[1:], strict=False)),
             "trade-in curve is complete and never rises", sku)
    ages = (0, 1, 12, 36, 59, 60) if full else (0, 24, 60)
    for age in ages:
        for condition, factor in (("good", 1.0), ("fair", 0.75), ("poor", 0.4)):
            status, body = get(r, "/v1/tradein/value", query={
                "device_sku": sku, "age_months": age, "condition": condition})
            r.expect(status == 200, "trade-in value answers 200", sku, age, condition)
            if status == 200:
                value = body["data"]
                r.expect(abs(value["value_cents"] - round(value["base_value_cents"] * factor)) <= 1
                         and value["value_cents"] <= device["msrp_cents"], "trade-in = base x condition, <= price", sku)
    for tier, apr, min_down in (("prime", 0.0, 0.0), ("near_prime", 0.049, 0.10), ("subprime", 0.099, 0.20)):
        for term in ((12, 24, 36) if full else (24,)):
            credit = min(20000, device["msrp_cents"] // 4)
            down = round(min_down * (device["msrp_cents"] - credit)) + 100
            status, body = r.call("POST", "/v1/financing/quote", "/v1/financing/quote", body={
                "device_sku": sku, "account_id": ref_account(r), "credit_tier": tier, "term_months": term,
                "down_payment_cents": down, "tradein_credit_cents": credit})
            r.expect(status == 200, "financing quote with every field filled", sku, tier, term, status)
            if status == 200:
                q = body["data"]
                paid = q["monthly_payment_cents"] * (term - 1) + q["final_payment_cents"]
                r.expect(q["apr"] == apr and q["amount_financed_cents"] == device["msrp_cents"] - credit - down
                         and q["total_cost_cents"] == down + paid
                         and q["total_interest_cents"] == paid - q["amount_financed_cents"],
                         "financing arithmetic is consistent", sku, tier, term)


def ref_account(r: Runner) -> str | None:
    return getattr(r, "financing_account", None)


def check_catalog(r: Runner, ref: Reference, full: bool, device_limit: int | None = None) -> None:
    r.financing_account = next((p["account_id"] for p in ref.personas if p["account_id"]), None)
    for tier in ("flagship", "mid", "value"):
        for status_filter in ("current", "legacy", "all"):
            for maker in ("Apple", "Samsung", "Google", "Motorola", "TCL", "T-Mobile"):
                status, _ = get(r, "/v1/catalog/devices", query={
                    "tier": tier, "manufacturer": maker, "status": status_filter, "limit": 200, "offset": 0})
                r.expect(status == 200, "devices list with every filter", tier, status_filter, maker)
    r.each(lambda d: check_device(r, d, full), ref.devices[:device_limit])
    for plan in ref.plans:
        status, body = get(r, "/v1/catalog/plans/{sku}", f"/v1/catalog/plans/{plan['sku']}")
        r.expect(status == 200 and body["data"] == plan, "plan detail equals its list entry", plan["sku"])
        prices = plan["line_prices_cents"]
        r.expect(plan["total_for_lines_cents"] == [sum(prices[: i + 1]) for i in range(len(prices))],
                 "plan totals are cumulative line prices", plan["sku"])
    for kind in ("protection", "streaming", "connected_line", "home_internet", "accessory"):
        rows = data_of(get(r, "/v1/catalog/addons", query={"kind": kind}))
        r.expect(bool(rows) and all(a["kind"] == kind for a in rows), "add-ons filter by kind", kind)
    for source in ("site", "stub"):
        rows = data_of(get(r, "/v1/catalog/promotions", query={"source": source}))
        r.expect(bool(rows) and all(p["source"] == source for p in rows), "promotion rules filter by source", source)


# ------------------------------------------------------------------------------------------------ personas and carts
def check_personas(r: Runner, ref: Reference) -> None:
    for theme in ("cart_whisperer", "matchmaker", "next_best_moment", "timekeeper", "household_optimizer"):
        for kind in ("customer", "prospect"):
            for secondary in ("true", "false"):
                status, _ = get(r, "/v1/personas", query={
                    "theme": theme, "kind": kind, "include_secondary": secondary, "limit": 100, "offset": 0})
                r.expect(status == 200, "personas list with every filter", theme, kind, secondary)
    for persona in ref.personas:
        status, body = get(r, "/v1/personas/{persona_id}", f"/v1/personas/{persona['persona_id']}")
        r.expect(status == 200 and body["data"]["persona_id"] == persona["persona_id"], "persona detail", persona["persona_id"])


FULL_FIELDS = {"quantity": 1, "payment": "financed", "condition": "good", "port_in": False}


def build_persona_cart(r: Runner, persona: dict) -> None:
    status, body = r.call("POST", "/v1/cart", "/v1/cart", body={"account_id": persona["account_id"]})
    r.expect(status == 201, "cart created for the persona", persona["persona_id"], status)
    if status != 201:
        return
    cart_id = body["data"]["cart_id"]
    for item in persona["starting_cart"]:
        status, body = r.call("POST", "/v1/cart/{cart_id}/items", f"/v1/cart/{cart_id}/items",
                              body={**FULL_FIELDS, **item})
        r.expect(status == 201 or (status == 409 and body["error"]["code"] == "TRADEIN_ALREADY_USED"),
                 "starting-cart item accepted with every field filled", persona["persona_id"], item["kind"], status)
    status, body = get(r, "/v1/cart/{cart_id}", f"/v1/cart/{cart_id}")
    cart = body["data"]
    r.expect(cart["totals"]["due_today_cents"] == sum(i["due_today_cents"] for i in cart["items"])
             and cart["totals"]["monthly_cents"] == sum(i["monthly_cents"] for i in cart["items"]),
             "cart totals equal the sum of the items", persona["persona_id"])
    query = {"cart_id": cart_id, **({"account_id": persona["account_id"]} if persona["account_id"] else {})}
    status, body = get(r, "/v1/promotions", query=query)
    r.expect(status == 200 and all((not p["eligible"]) == bool(p["reasons"]) for p in body["data"]),
             "ineligible promotions always say why", persona["persona_id"])


def find_fixture(r: Runner, ref: Reference):
    """A customer with a phone on a line, so every item kind can be tried with every field filled in."""
    for persona in ref.personas:
        if not persona["account_id"]:
            continue
        for line in data_of(get(r, "/v1/households/{account_id}", f"/v1/households/{persona['account_id']}"))["lines"]:
            if line["device_sku"]:
                return persona["account_id"], line
    return None, None


def check_item_combinations(r: Runner, ref: Reference) -> None:
    account, line = find_fixture(r, ref)
    r.expect(account is not None, "a customer with a phone exists to build cart cases from")
    if account is None:
        return
    new_phone = next(d for d in ref.devices if d["status"] == "current")
    device = next(d for d in ref.devices if d["sku"] == line["device_sku"])
    other_plan = next(p for p in ref.plans if p["eligibility"] is None and p["max_lines"] is None
                      and p["min_lines"] <= 1 and p["sku"] != line["plan_sku"])
    protection = next(a for a in ref.addons if a["kind"] == "protection" and a["protection_tier"] == device["protection_tier"])
    charger = next(a for a in ref.addons if a["kind"] == "accessory" and a["compatible_device_skus"] is None)
    cases = [
        (account, "device on a line, financed", {"kind": "device", "sku": new_phone["sku"], "line_id": line["line_id"]}),
        (account, "device on a line, paid in full", {"kind": "device", "sku": new_phone["sku"],
                                                     "line_id": line["line_id"], "payment": "full"}),
        (account, "trade-in, fair condition", {"kind": "tradein", "sku": line["device_sku"], "line_id": line["line_id"],
                                              "condition": "fair"}),
        (account, "plan change on a line", {"kind": "plan", "sku": other_plan["sku"], "line_id": line["line_id"]}),
        (account, "five accessories on a line", {"kind": "addon", "sku": charger["sku"], "line_id": line["line_id"],
                                                 "quantity": 5}),
        (account, "protection matching the phone", {"kind": "addon", "sku": protection["sku"], "line_id": line["line_id"]}),
        (account, "new line with a ported number", {"kind": "new_line", "sku": other_plan["sku"], "port_in": True}),
        (None, "new line, anonymous cart", {"kind": "new_line", "sku": other_plan["sku"], "port_in": True}),
    ]
    for cart_account, label, item in cases:
        status, body = r.call("POST", "/v1/cart", "/v1/cart", body={"account_id": cart_account})
        cart_id = body["data"]["cart_id"]
        status, body = r.call("POST", "/v1/cart/{cart_id}/items", f"/v1/cart/{cart_id}/items",
                              body={**FULL_FIELDS, "line_id": None, **item})
        used_up = status == 409 and body["error"]["code"] == "TRADEIN_ALREADY_USED"
        r.expect(status == 201 or used_up, f"every field filled: {label}", status, (body or {}).get("error"))


def check_cart_lifecycle(r: Runner, ref: Reference) -> None:
    """Delete an item, then check out a throwaway anonymous cart (never a persona's cart)."""
    charger = next(a for a in ref.addons if a["kind"] == "accessory" and a["compatible_device_skus"] is None)
    cart_id = r.call("POST", "/v1/cart", "/v1/cart", body={})[1]["data"]["cart_id"]
    add = {**FULL_FIELDS, "kind": "addon", "sku": charger["sku"], "line_id": None}
    view = r.call("POST", "/v1/cart/{cart_id}/items", f"/v1/cart/{cart_id}/items", body=add)[1]["data"]
    status, body = r.call("DELETE", "/v1/cart/{cart_id}/items/{item_id}",
                          f"/v1/cart/{cart_id}/items/{view['items'][0]['item_id']}")
    r.expect(status == 200 and body["data"]["items"] == [], "an item can be removed")
    r.call("POST", "/v1/cart/{cart_id}/items", f"/v1/cart/{cart_id}/items", body=add)
    key = {"Idempotency-Key": f"smoke-{uuid.uuid4().hex[:16]}"}
    status, body = r.call("POST", "/v1/checkout", "/v1/checkout", body={"cart_id": cart_id, "promo_skus": []}, headers=key)
    r.expect(status == 201 and body["data"]["status"] == "confirmed", "checkout confirms an order", status)
    order_id = body["data"]["order_id"] if status == 201 else None
    status, body = r.call("POST", "/v1/checkout", "/v1/checkout", body={"cart_id": cart_id, "promo_skus": []}, headers=key)
    r.expect(status == 201 and body["data"]["order_id"] == order_id, "the same Idempotency-Key returns the same order")
    other = {"cart_id": cart_id, "promo_skus": ["PROMO-STUB-STUDENT"]}
    status, body = r.call("POST", "/v1/checkout", "/v1/checkout", body=other, headers=key)
    r.expect(status == 409 and body["error"]["code"] == "IDEMPOTENCY_MISMATCH", "different promo_skus under one key conflicts")
    status, body = r.call("POST", "/v1/cart/{cart_id}/items", f"/v1/cart/{cart_id}/items", body=add)
    r.expect(status == 409 and body["error"]["code"] == "CART_CLOSED", "a checked-out cart is closed")


def check_promotions(r: Runner, ref: Reference) -> None:
    def one(account_id: str) -> None:
        status, body = get(r, "/v1/promotions", query={"account_id": account_id})
        r.expect(status == 200 and all((not p["eligible"]) == bool(p["reasons"]) for p in body["data"]),
                 "promotions by account explain every refusal", account_id)

    r.each(one, ref.account_ids[:300])


# ------------------------------------------------------------------------------------------------ hostile input
def check_hostile_input(r: Runner, ref: Reference) -> None:
    targets = [
        ("GET", "/v1/accounts", "/v1/accounts", ["segment", "persona_only", "limit", "offset"]),
        ("GET", "/v1/households/{account_id}", "/v1/households/{x}", []),
        ("GET", "/v1/customers/{account_id}/context", "/v1/customers/{x}/context", []),
        ("GET", "/v1/customers/{account_id}/usage", "/v1/customers/ACC-PERSONA-01/usage", ["line_id", "months"]),
        ("GET", "/v1/customers/{account_id}/billing", "/v1/customers/{x}/billing", []),
        ("GET", "/v1/customers/{account_id}/support-interactions", "/v1/customers/ACC-PERSONA-01/support-interactions", ["limit"]),
        ("GET", "/v1/catalog/devices", "/v1/catalog/devices", ["tier", "manufacturer", "limit", "offset", "status"]),
        ("GET", "/v1/catalog/devices/{sku}", "/v1/catalog/devices/{x}", []),
        ("GET", "/v1/catalog/plans/{sku}", "/v1/catalog/plans/{x}", []),
        ("GET", "/v1/catalog/addons", "/v1/catalog/addons", ["kind"]),
        ("GET", "/v1/catalog/promotions", "/v1/catalog/promotions", ["source"]),
        ("GET", "/v1/tradein/value", "/v1/tradein/value", ["device_sku", "age_months", "condition"]),
        ("GET", "/v1/tradein/curve/{sku}", "/v1/tradein/curve/{x}", []),
        ("GET", "/v1/promotions", "/v1/promotions", ["account_id", "cart_id"]),
        ("GET", "/v1/cart/{cart_id}", "/v1/cart/{x}", []),
        ("GET", "/v1/personas", "/v1/personas", ["theme", "kind", "include_secondary", "limit", "offset"]),
        ("GET", "/v1/personas/{persona_id}", "/v1/personas/{x}", []),
        ("POST", "/v1/cart/{cart_id}/items", "/v1/cart/{x}/items", []),
        ("DELETE", "/v1/cart/{cart_id}/items/{item_id}", "/v1/cart/{x}/items/{x}", []),
        ("POST", "/v1/checkout", "/v1/checkout", []),
        ("POST", "/v1/financing/quote", "/v1/financing/quote", []),
    ]

    def fuzz(target) -> None:
        method, template, path, query_keys = target
        for bad in EVIL:
            headers = {"Idempotency-Key": bad.encode("utf-8").decode("latin-1")} if method == "POST" else None
            status, _ = r.call(method, template, path.replace("{x}", urllib.parse.quote(bad, safe="")),
                               headers=headers, raw=b"{}" if method == "POST" else None)
            r.expect(status < 500, f"{method} {template}: hostile path value", bad[:15], status)
            for key in query_keys:
                status, _ = r.call(method, template, path.replace("{x}", "ACC-PERSONA-01"), query={key: bad})
                r.expect(status < 500, f"{method} {template}?{key}: hostile query value", bad[:15], status)

    r.each(fuzz, targets)
    cart_id = r.call("POST", "/v1/cart", "/v1/cart", body={})[1]["data"]["cart_id"]
    bodies = [
        ("/v1/cart/{cart_id}/items", f"/v1/cart/{cart_id}/items", {"kind": "addon", "sku": "TMO-STUB-ADD-ACC-CHARGER-FAST"}),
        ("/v1/financing/quote", "/v1/financing/quote", {"device_sku": ref.devices[0]["sku"]}),
        ("/v1/cart", "/v1/cart", {}),
    ]
    fields = ["quantity", "payment", "condition", "port_in", "line_id", "account_id", "term_months",
              "down_payment_cents", "tradein_credit_cents", "credit_tier"]
    for template, path, base in bodies:
        for name in [*base, *fields]:
            for bad in (None, "text", 1.5, -1, [], {}, True, 10**30, "x" * 5000):
                status, _ = r.call("POST", template, path, body={**base, name: bad})
                r.expect(status < 500, "body field with a wrong type or value", template, name, str(bad)[:12], status)
        status, _ = r.call("POST", template, path, body={**base, "unknown_field": 1})
        r.expect(status == 422, "an unknown body field is rejected", template, status)
        for broken in (b"{not json", b"[1,2,3]"):
            status, _ = r.call("POST", template, path, raw=broken)
            r.expect(status in (400, 422), "malformed JSON is a 4xx", template, status)


# ------------------------------------------------------------------------------------------------ coverage and entry
def check_coverage(r: Runner) -> None:
    status, text = r.client.request("GET", "/openapi.json", None, {})[0::2]
    if status != 200:
        r.report.failures.append("OPENAPI UNAVAILABLE: could not read /openapi.json")
        return
    spec = json.loads(text)

    def properties(schema: dict) -> set[str]:
        if "$ref" in schema:
            schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
        return set(schema.get("properties", {}))

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            used = r.covered.get((method.upper(), path), set())
            if ("called", "") not in used:
                r.report.coverage_gaps.append(f"{method.upper()} {path}: endpoint never called")
            for parameter in operation.get("parameters", []):
                kind = {"query": "q", "header": "h"}.get(parameter["in"])
                if kind and (kind, parameter["name"].lower()) not in used:
                    r.report.coverage_gaps.append(f"{method.upper()} {path}: {parameter['in']} parameter '{parameter['name']}' never sent")
            body = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            for name in properties(body) if body else ():
                if ("b", name) not in used:
                    r.report.coverage_gaps.append(f"{method.upper()} {path}: body field '{name}' never sent")


def run(
    client, *, full: bool = False, fuzz: bool = True, workers: int = 8, sample: int = 150, device_limit: int | None = None,
    log=print,
) -> Report:
    runner, started = Runner(client, workers), time.time()
    log("loading reference data ...")
    ref = load_reference(runner, full, sample)
    log(f"  {len(ref.devices)} devices, {len(ref.plans)} plans, {len(ref.addons)} add-ons, "
        f"{len(ref.personas)} personas, {len(ref.account_ids)} accounts to check")
    steps = [
        ("platform and account lists", lambda: check_platform(runner)),
        ("every account through all five customer endpoints", lambda: runner.each(lambda a: check_account(runner, a), ref.account_ids)),
        ("usage and support filters", lambda: check_usage_filters(runner, ref)),
        ("catalog, trade-in values and financing quotes", lambda: check_catalog(runner, ref, full, device_limit)),
        ("personas", lambda: check_personas(runner, ref)),
        ("every persona's starting cart", lambda: runner.each(lambda p: build_persona_cart(runner, p), [p for p in ref.personas if p["starting_cart"]])),
        ("every cart item kind with every field filled", lambda: check_item_combinations(runner, ref)),
        ("cart lifecycle and idempotent checkout", lambda: check_cart_lifecycle(runner, ref)),
        ("promotions for many accounts", lambda: check_promotions(runner, ref)),
    ]
    if fuzz:
        steps.append(("hostile input on every parameter and body field", lambda: check_hostile_input(runner, ref)))
    for label, step in steps:
        log(f"checking {label} ...")
        try:
            step()
        except Exception as error:  # a broken endpoint must produce a report, never a crash
            runner.fail(f"STEP COULD NOT COMPLETE: {label}: {type(error).__name__}: {str(error)[:100]}")
    check_coverage(runner)
    runner.report.slow = runner.report.slow[:5]
    runner.report.elapsed = time.time() - started
    return runner.report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test for a running sandbox (see the module docstring).")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--full", action="store_true", help="check every account and more trade-in ages and terms")
    parser.add_argument("--no-fuzz", action="store_true", help="skip the hostile-input checks")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--sample", type=int, default=150, help="accounts to check in quick mode")
    args = parser.parse_args(argv)
    report = run(HttpClient(args.base_url), full=args.full, fuzz=not args.no_fuzz, workers=args.workers, sample=args.sample)
    print(f"\n{report.requests:,} requests, {report.checks:,} checks in {report.elapsed:.0f}s")
    for message in report.failures + report.coverage_gaps + report.slow:
        print("  -", message)
    print("PASS: everything works" if report.ok else f"FAIL: {len(report.failures)} problems, {len(report.coverage_gaps)} coverage gaps")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
