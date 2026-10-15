"""Immutable specs (what to generate) and rows (what gets written)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineSpec:
    role: str
    usage_class: str
    age_months: int | None = None
    byod: bool = False
    plan_sku: str | None = None
    device_sku: str | None = None
    protection: bool | None = None
    financed: bool | None = None
    hotspot_user: bool | None = None
    usage_gb: float | None = None  # pin the mean monthly GB (the oldest month's, when usage_growth is set)
    usage_growth: float | None = None  # pin a monthly usage multiplier, e.g. 1.06 for steady growth
    label: str | None = None


@dataclass(frozen=True)
class AccountSpec:
    account_id: str
    segment: str
    tenure_months: int
    unhappiness: float
    lines: tuple[LineSpec, ...]
    language: str = "en"
    contact_preference: str = "app"
    credit_tier: str = "prime"
    autopay: bool = True
    services: tuple[str, ...] = ()
    persona_note: str | None = None
    bill_spike_pct: float | None = None
    plan_mismatch_rate: float = 0.25
    discount_group: str | None = None
    support_recent: int | None = None  # pin the contacts in the last 90 days (personas)
    support_older: int | None = None  # pin the contacts 91-270 days ago
    support_topics: tuple[str, ...] | None = None  # pin what the contacts are about
    support_sentiment: float | None = None  # pin the average mood of contacts (-1 to 1)
    support_resolved: bool | None = None  # pin whether contacts get resolved
    competitor_score: float | None = None  # pin the proxy signals
    port_out: bool | None = None
    app_sessions: int | None = None
    id_prefix: str = "LN"


@dataclass(frozen=True)
class AccountRows:
    account: tuple
    lines: tuple[tuple, ...] = field(default_factory=tuple)
    line_addons: tuple[tuple, ...] = field(default_factory=tuple)
    account_addons: tuple[tuple, ...] = field(default_factory=tuple)
    usage: tuple[tuple, ...] = field(default_factory=tuple)
    billing: tuple[tuple, ...] = field(default_factory=tuple)
    support: tuple[tuple, ...] = field(default_factory=tuple)
    signals: tuple = ()
