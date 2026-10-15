"""Commerce contracts. Money is in cents. All values are stub data."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CreditTier = Literal["prime", "near_prime", "subprime"]
Condition = Literal["good", "fair", "poor"]
ItemKind = Literal["device", "plan", "new_line", "addon", "tradein"]
SKU_PATTERN = r"^[A-Za-z0-9-]{3,60}$"
LINE_PATTERN = r"^[A-Za-z0-9-]{3,40}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Device(Strict):
    sku: str
    name: str
    manufacturer: str
    tier: str
    storage_gb: int | None
    msrp_cents: int
    release_date: str
    status: str
    protection_tier: int
    installment_24_cents: int


class Plan(Strict):
    sku: str
    name: str
    family: str
    variant: str
    tier: str
    line_prices_cents: list[int]
    extra_line_cents: int
    total_for_lines_cents: list[int]
    min_lines: int
    max_lines: int | None
    data_cap_gb: int | None
    hotspot_high_speed_gb: int
    hotspot_unlimited: bool
    canada_mexico_gb: int | None
    intl_data_gb: int | None
    video_quality: str | None
    price_guarantee_years: int | None
    priority_network: bool
    prices_include_autopay: bool
    device_connection_cents: int | None
    eligibility: str | None
    perks: list[str]
    upgrade_note: str | None
    status: str


class Addon(Strict):
    sku: str
    name: str
    kind: str
    monthly_cents: int
    one_time_cents: int
    per: str
    description: str | None
    eligible_families: list[str] | None
    protection_tier: int | None
    compatible_device_skus: list[str] | None
    deductible_screen_cents: int | None
    deductible_damage_cents: int | None
    deductible_loss_theft_cents: int | None


class TradeInValue(Strict):
    device_sku: str
    age_months: int
    condition: str
    base_value_cents: int
    value_cents: int


class TradeInPoint(Strict):
    age_months: int
    value_cents: int


class FinancingQuote(Strict):
    device_sku: str
    credit_tier: str
    msrp_cents: int
    tradein_credit_cents: int
    down_payment_cents: int
    min_down_payment_cents: int
    amount_financed_cents: int
    term_months: int
    apr: float
    monthly_payment_cents: int
    final_payment_cents: int
    total_interest_cents: int
    total_cost_cents: int


class FinancingQuoteRequest(Strict):
    device_sku: str = Field(pattern=SKU_PATTERN)
    account_id: str | None = Field(default=None, pattern=LINE_PATTERN, description="Uses this account's credit tier")
    credit_tier: CreditTier | None = Field(default=None, description="Overrides the account's tier")
    term_months: Literal[12, 24, 36] = 24
    down_payment_cents: int = Field(default=0, ge=0, le=500_000)
    tradein_credit_cents: int = Field(default=0, ge=0, le=500_000)


class PromotionResult(Strict):
    sku: str
    name: str
    kind: str
    value_cents: int
    source: str
    payout_months: int | None
    per: str
    percent_off: int | None
    eligible: bool
    reasons: list[str]
    estimated_savings_cents: int


class PromotionDefinition(Strict):
    sku: str
    name: str
    kind: str
    value_cents: int
    source: str
    payout_months: int | None
    per: str
    max_units: int | None
    requires_new_line: bool
    requires_port_in: bool
    requires_tradein: bool
    new_line_or_tradein: bool
    requires_device: bool
    requires_byod: bool
    device_skus: list[str] | None
    plan_families: list[str] | None
    plan_variants: list[str] | None
    min_plan_cents: int | None
    discount_plan_only: bool
    discount_groups: list[str] | None
    credit_tiers: list[str] | None
    min_lines: int
    min_tenure_months: int | None
    min_device_age_months: int | None
    min_support_contacts_90d: int | None
    requires_addon_kind: str | None
    min_accessories: int | None
    percent_off: int | None
    description: str | None


class CartItemView(Strict):
    item_id: str
    kind: str
    sku: str
    name: str
    line_id: str | None
    quantity: int
    payment: str | None
    condition: str | None
    port_in: bool
    due_today_cents: int
    monthly_cents: int
    credit_earned_cents: int
    credit_applied_cents: int
    balance_owed_cents: int


class CartTotals(Strict):
    item_count: int
    due_today_cents: int
    monthly_cents: int
    tradein_credit_cents: int
    tradein_credit_applied_cents: int
    tradein_credit_unapplied_cents: int
    tradein_balance_owed_cents: int


class CartView(Strict):
    cart_id: str
    account_id: str | None
    status: str
    items: list[CartItemView]
    totals: CartTotals


class CreateCartRequest(Strict):
    account_id: str | None = Field(default=None, pattern=LINE_PATTERN)


class AddItemRequest(Strict):
    kind: ItemKind
    sku: str | None = Field(default=None, pattern=SKU_PATTERN, description="Optional for trade-in")
    line_id: str | None = Field(default=None, pattern=LINE_PATTERN)
    quantity: int = Field(default=1, ge=1, le=5)
    payment: Literal["financed", "full"] = "financed"
    condition: Condition = "good"
    port_in: bool = Field(default=False, description="new_line only: the line brings a number from another carrier")


class CheckoutRequest(Strict):
    cart_id: str = Field(pattern=r"^CART-[a-f0-9]{32}$")
    promo_skus: list[Annotated[str, Field(pattern=SKU_PATTERN)]] = Field(default_factory=list, max_length=5)


class AppliedPromotion(Strict):
    sku: str
    name: str
    kind: str
    value_cents: int
    savings_cents: int


class Order(Strict):
    order_id: str
    cart_id: str
    account_id: str | None
    status: str
    items: list[CartItemView]
    totals: CartTotals
    applied_promotions: list[AppliedPromotion]
    promo_savings_cents: int
