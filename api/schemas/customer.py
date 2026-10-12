"""Response contracts for the customer and context layer. Money is in cents."""

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccountSummary(Strict):
    account_id: str
    segment: str
    tenure_months: int
    language: str
    line_count: int
    persona_note: str | None


class ServiceItem(Strict):
    sku: str
    name: str
    kind: str
    monthly_cents: int


class HouseholdLine(Strict):
    line_id: str
    member_label: str
    member_role: str
    plan_sku: str
    plan_name: str
    plan_tier: str
    device_sku: str | None
    device_name: str | None
    byod: bool
    addons: list[str]


class Household(Strict):
    account_id: str
    segment: str
    tenure_months: int
    language: str
    contact_preference: str
    credit_tier: str
    autopay: bool
    discount_group: str | None
    persona_note: str | None
    lines: list[HouseholdLine]
    services: list[ServiceItem]


class DeviceInfo(Strict):
    sku: str
    name: str
    tier: str
    purchase_date: str
    age_months: int


class Financing(Strict):
    balance_cents: int
    months_remaining: int
    monthly_installment_cents: int
    paid_off: bool


class ContextLine(Strict):
    line_id: str
    member_label: str
    member_role: str
    plan_sku: str
    plan_name: str
    plan_tier: str
    plan_family: str
    plan_variant: str
    plan_data_cap_gb: int | None
    byod: bool
    device: DeviceInfo | None
    financing: Financing | None
    has_protection: bool
    tradein_eligible: bool
    upgrade_eligible: bool
    estimated_tradein_value_cents: int | None
    usage_3m_avg_gb: float | None


class BillingSummary(Strict):
    latest_total_cents: int
    change_pct_vs_prior_avg: float | None
    months_available: int


class SupportSummary(Strict):
    contacts_90d: int
    unresolved_90d: int
    last_contact_date: str | None
    avg_sentiment: float | None


class Signals(Strict):
    competitor_research_score: float
    port_out_inquiry: bool
    app_sessions_30d: int


class Eligibility(Strict):
    line_count: int
    upgrade_eligible_lines: int
    tradein_eligible_lines: int


class CustomerContext(Strict):
    as_of: str
    account_id: str
    segment: str
    tenure_months: int
    language: str
    contact_preference: str
    credit_tier: str
    autopay: bool
    discount_group: str | None
    persona_note: str | None
    services: list[ServiceItem]
    lines: list[ContextLine]
    billing: BillingSummary | None
    support: SupportSummary
    signals: Signals | None
    eligibility: Eligibility


class UsageMonth(Strict):
    line_id: str
    month: str
    data_gb: float
    voice_minutes: int
    streaming_hours: float
    hotspot_gb: float


class BillingMonth(Strict):
    month: str
    total_cents: int
    change_cents: int
    change_reason: str


class SupportInteraction(Strict):
    interaction_id: str
    interaction_date: str
    channel: str
    topic: str
    sentiment: float
    resolved: bool
