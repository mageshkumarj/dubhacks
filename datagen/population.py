"""Sample random AccountSpecs with a segment-driven household structure."""

from random import Random

from .rows import AccountSpec, LineSpec
from .util import clip, weighted

SEGMENTS = (
    ("student", 0.12), ("single", 0.25), ("couple", 0.18),
    ("family", 0.30), ("smb", 0.08), ("senior", 0.07),
)
ROLE_USAGE = {
    "student": (("light", 0.4), ("moderate", 0.4), ("heavy", 0.2)),
    "primary": (("light", 0.3), ("moderate", 0.5), ("heavy", 0.2)),
    "partner": (("light", 0.35), ("moderate", 0.45), ("heavy", 0.2)),
    "teen": (("light", 0.05), ("moderate", 0.35), ("heavy", 0.6)),
    "child": (("light", 0.7), ("moderate", 0.3), ("heavy", 0.0)),
    "employee": (("light", 0.25), ("moderate", 0.6), ("heavy", 0.15)),
    "senior": (("light", 0.7), ("moderate", 0.28), ("heavy", 0.02)),
}
HOME_INTERNET = (
    ("TMO-STUB-ADD-HINT-BASIC", 0.5), ("TMO-STUB-ADD-HINT-PLUS", 0.35), ("TMO-STUB-ADD-HINT-PREMIUM", 0.15),
)
STREAMING = "TMO-STUB-ADD-STREAM-VIDEO"
WATCH_LINES = (("TMO-STUB-ADD-LINE-WATCH", 0.6), ("TMO-STUB-ADD-LINE-WATCH-PLUS", 0.3),
               ("TMO-STUB-ADD-LINE-CONNECTED-BEYOND", 0.1))
WATCH_LINE_RATE = 0.08


def _roles(rng: Random, segment: str) -> tuple[str, ...]:
    if segment == "student":
        return ("student",)
    if segment == "single":
        return ("primary",)
    if segment == "couple":
        return ("primary", "partner")
    if segment == "senior":
        return ("senior",) * rng.choice((1, 2))
    if segment == "smb":
        return ("primary", *("employee" for _ in range(rng.randint(1, 5))))
    kids = rng.randint(1, 3)
    return ("primary", "partner", *(rng.choice(("teen", "child")) for _ in range(kids)))


def _services(rng: Random, segment: str) -> tuple[str, ...]:
    family = segment == "family"
    services = []
    if rng.random() < (0.3 if family else 0.15):
        services.append(weighted(rng, HOME_INTERNET))
    if rng.random() < (0.45 if family else 0.3):
        services.append(STREAMING)
    if rng.random() < WATCH_LINE_RATE:
        services.append(weighted(rng, WATCH_LINES))
    return tuple(services)


def _discount_group(rng: Random, segment: str) -> str | None:
    roll = rng.random()
    if segment == "senior":
        return "55_plus" if roll < 0.7 else None
    if segment == "student":
        return "student" if roll < 0.7 else None
    return "partner" if roll < 0.03 else "community" if roll < 0.05 else None


def random_account(rng: Random, index: int) -> AccountSpec:
    segment = weighted(rng, SEGMENTS)
    tenure = int(clip(1 + rng.expovariate(1 / 40), 1, 180))
    if segment == "student":
        tenure = min(tenure, 30)
    lines = tuple(
        LineSpec(
            role=role,
            usage_class=weighted(rng, ROLE_USAGE[role]),
            age_months=int(clip(rng.expovariate(1 / 22), 0, 48)),
            byod=rng.random() < (0.35 if segment == "student" else 0.15),
        )
        for role in _roles(rng, segment)
    )
    return AccountSpec(
        discount_group=_discount_group(rng, segment),
        account_id=f"ACC-{index:05d}",
        id_prefix=f"LN-{index:05d}",
        segment=segment,
        tenure_months=tenure,
        unhappiness=round(rng.betavariate(1.3, 4.0), 3),
        lines=lines,
        language=weighted(rng, (("en", 0.85), ("es", 0.12), ("other", 0.03))),
        contact_preference=weighted(rng, (("app", 0.4), ("sms", 0.3), ("email", 0.2), ("call", 0.1))),
        credit_tier=weighted(rng, (("prime", 0.6), ("near_prime", 0.25), ("subprime", 0.15))),
        autopay=rng.random() < 0.7,
        services=_services(rng, segment),
    )
