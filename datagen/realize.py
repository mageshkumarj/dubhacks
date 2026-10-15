"""Turn an AccountSpec into concrete rows. Pure given the spec and rng."""

from datetime import date
from random import Random
from typing import NamedTuple

from . import catalog
from .rows import AccountRows, AccountSpec, LineSpec
from .util import clip, months_ago, months_between, poisson, weighted

FINANCING_MONTHS = 24
HISTORY_MONTHS = 12
MIN_SPIKE_HISTORY = 3
USAGE_MEAN_GB = {"light": 3.0, "moderate": 15.0, "heavy": 55.0}
PLAN = "TMO-STUB-PLAN-"
FIT_PLANS = {
    "light": (PLAN + "ESSENTIALS-SAVER", PLAN + "ESSENTIALS"),
    "moderate": (PLAN + "ESSENTIALS", PLAN + "MORE"),
    "heavy": (PLAN + "MORE", PLAN + "BEYOND"),
}
MISMATCH_POOL = (PLAN + "ESSENTIALS-SAVER", PLAN + "ESSENTIALS", PLAN + "MORE", PLAN + "BEYOND")
GROUP_SUFFIX = {"partner": "PARTNER", "community": "COMMUNITY", "55_plus": "55"}
FOUR_LINE_OFFER = PLAN + "ESSENTIALS-4LINE"
FOUR_LINE_TAKE_RATE = 0.35
DEVICE_TIER_WEIGHTS = {
    "heavy": (("flagship", 0.7), ("mid", 0.25), ("value", 0.05)),
    "moderate": (("flagship", 0.35), ("mid", 0.4), ("value", 0.25)),
    "light": (("flagship", 0.15), ("mid", 0.35), ("value", 0.5)),
}
TOPICS_CALM = (("billing", 0.3), ("device", 0.3), ("plan_change", 0.25), ("network", 0.15))
TOPICS_UNHAPPY = (
    ("billing", 0.35), ("network", 0.25), ("cancellation_inquiry", 0.25), ("device", 0.15),
)
CHANNELS = (("phone", 0.4), ("chat", 0.3), ("app", 0.2), ("store", 0.1))
DEVICES_BY_SKU = {d.sku: d for d in catalog.DEVICES}
PLANS_BY_SKU = {p.sku: p for p in catalog.PLANS}
ADDONS_BY_SKU = {a.sku: a for a in catalog.ADDONS}
OLDEST_DEVICE = min(catalog.DEVICES, key=lambda d: d.release_date)
BUNDLE_CREDIT_CENTS = next(p.value_cents for p in catalog.PROMOTIONS if p.sku == "PROMO-STUB-BUNDLE-HINT")
PROTECTION_RATE = {"flagship": 0.45, "mid": 0.3, "value": 0.15}


class Financing(NamedTuple):
    balance: int
    months_remaining: int
    installment: int
    financed: bool


class LineBill(NamedTuple):
    """What a line adds to the monthly bill, and when its installment applies."""

    fixed_cents: int
    installment: int
    purchase: date | None
    financed: bool


def _history_months(tenure_months: int) -> tuple[str, ...]:
    count = max(1, min(HISTORY_MONTHS, tenure_months))
    return tuple(months_ago(catalog.AS_OF, count - i).strftime("%Y-%m") for i in range(count))


def _max_device_age(device: catalog.Device) -> int:
    """Oldest age at which the purchase month still falls after the release date."""
    return months_between(device.release_date, catalog.AS_OF) - int(device.release_date.day > 1)


def _pick_device(rng: Random, spec: LineSpec, age: int) -> tuple[catalog.Device, int]:
    if spec.device_sku:
        device = DEVICES_BY_SKU[spec.device_sku]
    else:
        purchase = months_ago(catalog.AS_OF, age)
        released = [d for d in catalog.DEVICES if d.release_date <= purchase <= (d.sold_until or catalog.AS_OF)]
        tier = weighted(rng, DEVICE_TIER_WEIGHTS[spec.usage_class])
        pool = [d for d in released if d.tier == tier] or released or [OLDEST_DEVICE]
        device = rng.choice(pool)
    return device, min(age, _max_device_age(device))


def _apply_account_rules(rng: Random, acct: AccountSpec, sku: str) -> str:
    """Respect line limits and eligibility: savers cap at 2 lines, groups get their variant, 4-line offer."""
    lines = len(acct.lines)
    if sku.endswith("SAVER") and lines > 2:
        sku = PLAN + "ESSENTIALS"
    if acct.discount_group:
        variant = PLANS_BY_SKU.get(f"{sku}-{GROUP_SUFFIX.get(acct.discount_group, '-')}")
        if variant and (variant.max_lines is None or lines <= variant.max_lines):
            return variant.sku
    if sku == PLAN + "ESSENTIALS" and lines >= 4 and rng.random() < FOUR_LINE_TAKE_RATE:
        return FOUR_LINE_OFFER
    return sku


USAGE_ORDER = ("light", "moderate", "heavy")


def _account_plan(rng: Random, acct: AccountSpec) -> str:
    """One plan per household, chosen for its heaviest user (so lighter users may overpay), sometimes mismatched."""
    heaviest = max((spec.usage_class for spec in acct.lines), key=USAGE_ORDER.index)
    if rng.random() < acct.plan_mismatch_rate:
        return _apply_account_rules(rng, acct, rng.choice(MISMATCH_POOL))
    return _apply_account_rules(rng, acct, rng.choice(FIT_PLANS[heaviest]))


def _financing(rng: Random, spec: LineSpec, device: catalog.Device, age: int) -> Financing:
    financed = spec.financed if spec.financed is not None else rng.random() < 0.85
    installment = round(device.msrp_cents / FINANCING_MONTHS)
    if not financed:
        return Financing(0, 0, 0, False)
    if age >= FINANCING_MONTHS:
        return Financing(0, 0, 0, True)  # paid off, but it did appear on past bills
    remaining = FINANCING_MONTHS - age
    return Financing(installment * remaining, remaining, installment, True)


def _device_state(rng: Random, acct: AccountSpec, spec: LineSpec):
    if spec.byod:
        return None, None, Financing(0, 0, 0, False)
    requested = spec.age_months if spec.age_months is not None else 12
    if spec.device_sku is None:
        requested = min(requested, acct.tenure_months)  # bought from us, so no older than the account
    device, age = _pick_device(rng, spec, requested)
    return device, age, _financing(rng, spec, device, age)


def _protection_addons(rng: Random, spec: LineSpec, device, line_id: str) -> tuple[tuple, ...]:
    wanted = spec.protection
    if wanted is None:
        wanted = device is not None and rng.random() < PROTECTION_RATE[device.tier]
    if not (wanted and device):
        return ()
    sku = f"TMO-STUB-ADD-PROT-T{device.protection_tier}"
    return ((line_id, sku),)


def _line_rows(rng: Random, acct: AccountSpec, index: int, spec: LineSpec, line_id: str, account_plan: str):
    plan_sku = spec.plan_sku or account_plan
    device, age, fin = _device_state(rng, acct, spec)
    purchase = months_ago(catalog.AS_OF, age) if device else None
    row = (
        line_id, acct.account_id, spec.label or f"Line {index + 1}", spec.role, plan_sku,
        device.sku if device else None, int(spec.byod),
        purchase.isoformat() if purchase else None,
        fin.balance, fin.months_remaining, fin.installment, int(device is not None and age >= 1),
    )
    addons = _protection_addons(rng, spec, device, line_id)
    addon_cents = sum(a.monthly_cents for a in catalog.ADDONS if (line_id, a.sku) in addons)
    fixed = catalog.plan_price_cents(PLANS_BY_SKU[plan_sku], index) + addon_cents
    installment = round(device.msrp_cents / FINANCING_MONTHS) if device else 0
    return row, addons, LineBill(fixed, installment, purchase, fin.financed)


def _usage_rows(
    rng: Random, line_id: str, spec: LineSpec, months: tuple[str, ...]
) -> tuple[tuple, ...]:
    drawn_base = USAGE_MEAN_GB[spec.usage_class] * rng.lognormvariate(0, 0.25)  # always drawn, so RNG use is stable
    base = spec.usage_gb if spec.usage_gb is not None else drawn_base
    drawn_hotspot = spec.usage_class == "heavy" and rng.random() < 0.4
    hotspot_user = spec.hotspot_user if spec.hotspot_user is not None else drawn_hotspot
    streamer = 1.8 if spec.role == "teen" else 1.0
    rows = []
    for i, month in enumerate(months):
        trend = spec.usage_growth**i if spec.usage_growth else 1.0
        gb = round(base * trend * rng.lognormvariate(0, 0.15), 2)
        rows.append((
            line_id, month, gb, max(0, round(rng.gauss(220, 90))),
            round(gb * 0.35 * streamer * rng.uniform(0.8, 1.2), 1),
            round(rng.uniform(1, 12), 1) if hotspot_user else 0.0,
        ))
    return tuple(rows)


def _installment_due(bill: LineBill, month: str) -> int:
    if not (bill.financed and bill.purchase):
        return 0
    start = date(int(month[:4]), int(month[5:]), 1)
    end = months_ago(bill.purchase, -FINANCING_MONTHS)
    return bill.installment if bill.purchase <= start < end else 0


def _change_reason(i: int, installments: int, previous: int, spike_starts: bool) -> str:
    """Why the bill changed: a new phone, a phone paid off, or a promotion ending, in that order of precedence."""
    if i > 0 and installments > previous:
        return "device_installment"
    if i > 0 and installments < previous:
        return "installment_ended"
    return "promo_expired" if spike_starts else "stable"


def _billing_rows(
    rng: Random, acct: AccountSpec, shared_cents: int, bills: list[LineBill], months: tuple[str, ...]
) -> tuple[tuple, ...]:
    spike = acct.bill_spike_pct
    if spike is None:
        likely = acct.unhappiness > 0.55 or rng.random() < 0.08
        spike = rng.uniform(0.08, 0.25) if likely else 0.0
    if len(months) < MIN_SPIKE_HISTORY:
        spike = 0.0  # drawn above so RNG use is stable, but a promo cannot expire on the first bill
    spike_start = len(months) - 2
    totals, reasons, previous_installments = [], [], 0
    for i, month in enumerate(months):
        installments = sum(_installment_due(b, month) for b in bills)
        base = shared_cents + sum(b.fixed_cents for b in bills) + installments
        factor = 1 + rng.uniform(-0.02, 0.02)
        if spike and i < spike_start:
            factor /= 1 + spike  # the promotion was still running; the last two months are at list price
        totals.append(round(base * factor))
        reasons.append(_change_reason(i, installments, previous_installments, bool(spike) and i == spike_start))
        previous_installments = installments
    changes = (0, *(b - a for a, b in zip(totals, totals[1:], strict=False)))
    return tuple(
        (acct.account_id, m, t, c, why) for m, t, c, why in zip(months, totals, changes, reasons, strict=True)
    )


def _support_rows(rng: Random, acct: AccountSpec) -> tuple[tuple, ...]:
    u = acct.unhappiness
    reach = max(1, acct.tenure_months) * 30
    recent_cap, older_cap = min(90, reach), min(270, reach)
    recent = acct.support_recent if acct.support_recent is not None else poisson(rng, 0.15 + 7.0 * u)
    older = acct.support_older if acct.support_older is not None else (poisson(rng, 0.4) if older_cap > 90 else 0)
    offsets = [rng.randint(1, recent_cap) for _ in range(recent)]
    offsets += [rng.randint(91, older_cap) for _ in range(older)]
    topics = TOPICS_UNHAPPY if u > 0.5 else TOPICS_CALM
    rows = []
    for n, offset in enumerate(sorted(offsets)):
        day = date.fromordinal(catalog.AS_OF.toordinal() - offset)
        topic = rng.choice(acct.support_topics) if acct.support_topics else weighted(rng, topics)
        mood = acct.support_sentiment if acct.support_sentiment is not None else 0.4 - 1.1 * u
        spread = 0.15 if acct.support_sentiment is not None else 0.3
        resolved = acct.support_resolved if acct.support_resolved is not None else rng.random() < 0.9 - 0.5 * u
        rows.append((
            f"{acct.account_id}-S{n + 1:02d}", acct.account_id, day.isoformat(),
            weighted(rng, CHANNELS), topic, round(clip(mood + rng.gauss(0, spread), -1, 1), 2), int(resolved),
        ))
    return tuple(rows)


def _signal_row(rng: Random, acct: AccountSpec) -> tuple:
    u = acct.unhappiness
    competitor = round(clip(0.1 + 0.75 * u + rng.gauss(0, 0.15), 0, 1), 2)
    port_out = int(rng.random() < 0.02 + 0.25 * u * u)
    sessions = poisson(rng, 12 * (1 - 0.6 * u))
    return (
        acct.account_id,
        acct.competitor_score if acct.competitor_score is not None else competitor,
        int(acct.port_out) if acct.port_out is not None else port_out,
        acct.app_sessions if acct.app_sessions is not None else sessions,
    )


def _eligible_services(services: tuple[str, ...], plan_skus: list[str]) -> tuple[str, ...]:
    """Drop account services whose plan-family restriction none of the household's lines meet."""
    families = {PLANS_BY_SKU[sku].family for sku in plan_skus}
    allowed = (ADDONS_BY_SKU[s].eligible_families for s in services)
    return tuple(s for s, fams in zip(services, allowed, strict=True) if fams is None or families & set(fams))


def realize(acct: AccountSpec, rng: Random) -> AccountRows:
    months = _history_months(acct.tenure_months)
    account_plan = _account_plan(rng, acct)
    lines, line_addons, usage, bills = [], [], [], []
    for index, spec in enumerate(acct.lines):
        line_id = f"{acct.id_prefix}-{index + 1}"
        row, addons, bill = _line_rows(rng, acct, index, spec, line_id, account_plan)
        lines.append(row)
        line_addons.extend(addons)
        bills.append(bill)
        usage.extend(_usage_rows(rng, line_id, spec, months))
    services = _eligible_services(acct.services, [row[4] for row in lines])
    shared = sum(ADDONS_BY_SKU[s].monthly_cents for s in services)
    if lines and any(ADDONS_BY_SKU[s].kind == "home_internet" for s in services):
        shared -= BUNDLE_CREDIT_CENTS  # Home Internet is discounted when the household has a phone line
    account = (
        acct.account_id, acct.segment, acct.tenure_months, acct.language, acct.contact_preference,
        acct.credit_tier, int(acct.autopay), acct.discount_group, acct.persona_note,
    )
    return AccountRows(
        account=account,
        lines=tuple(lines),
        line_addons=tuple(line_addons),
        account_addons=tuple((acct.account_id, sku) for sku in services),
        usage=tuple(usage),
        billing=_billing_rows(rng, acct, shared, bills, months),
        support=_support_rows(rng, acct),
        signals=_signal_row(rng, acct),
    )
