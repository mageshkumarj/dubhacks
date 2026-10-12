"""Stub T-Mobile-branded catalog. Every SKU, price and promo here is synthetic."""

from dataclasses import dataclass
from datetime import date
from dataclasses import replace
from math import exp

DATA_SOURCE = "stub"
AS_OF = date(2026, 10, 1)
MAX_TRADEIN_AGE_MONTHS = 60


@dataclass(frozen=True)
class Device:
    sku: str
    name: str
    manufacturer: str
    tier: str
    storage_gb: int | None
    msrp_cents: int
    release_date: date
    decay_rate: float
    status: str
    protection_tier: int
    sold_until: date | None = None  # None: still on sale


@dataclass(frozen=True)
class Plan:
    sku: str
    name: str
    family: str
    variant: str
    tier: str
    line_prices: tuple[int, ...]  # marginal monthly price of line 1, 2, 3... (cents)
    extra_line_cents: int  # price of every line beyond the published table
    min_lines: int
    max_lines: int | None
    data_cap_gb: int | None  # premium data cap; None means unlimited premium data
    hotspot_high_speed_gb: int
    hotspot_unlimited: bool  # unlimited hotspot at reduced speed once high-speed data is used
    canada_mexico_gb: int | None  # None: not published
    intl_data_gb: int | None  # data in 215+ countries; None: not published
    video_quality: str | None
    price_guarantee_years: int | None
    priority_network: bool
    prices_include_autopay: bool
    device_connection_cents: int | None
    eligibility: str | None  # None: anyone; otherwise partner, community or 55_plus
    perks: tuple[str, ...]
    upgrade_note: str | None
    status: str


@dataclass(frozen=True)
class Addon:
    sku: str
    name: str
    kind: str
    monthly_cents: int
    one_time_cents: int
    per: str  # device, line, account or item: what one unit of the add-on covers
    description: str | None = None
    eligible_families: tuple[str, ...] | None = None  # plan families that may buy it; None: any
    protection_tier: int | None = None
    compatible_devices: tuple[str, ...] | None = None  # device SKUs; None: not published / universal
    deductible_screen_cents: int | None = None  # protection only
    deductible_damage_cents: int | None = None
    deductible_loss_theft_cents: int | None = None


@dataclass(frozen=True)
class Promotion:
    """An offer and the conditions a customer and cart must meet. None / False means "no such condition"."""

    sku: str
    name: str
    kind: str  # device_credit, prepaid_card, bill_credit, line_credit, accessory_discount
    value_cents: int  # total (device_credit, prepaid_card, line_credit) or per month (bill_credit)
    source: str  # site: modeled on a published offer; stub: invented (retention)
    payout_months: int | None = None  # months a credit is spread over; None for bill_credit means ongoing
    per: str = "cart"  # cart, device or line: what one unit of value attaches to
    max_units: int | None = None  # devices or lines that can receive it
    requires_new_line: bool = False
    requires_port_in: bool = False  # the new line brings a number from another carrier
    requires_tradein: bool = False
    new_line_or_tradein: bool = False  # satisfy (new line [+ port-in]) OR a trade-in
    requires_device: bool = False
    requires_byod: bool = False  # new line with the customer's own phone (no device in the cart)
    device_skus: tuple[str, ...] | None = None
    plan_families: tuple[str, ...] | None = None
    plan_variants: tuple[str, ...] | None = None
    min_plan_cents: int | None = None  # single-line price of the qualifying plan
    discount_plan_only: bool = False  # the qualifying plan must be a 55+, partner or community plan
    discount_groups: tuple[str, ...] | None = None
    credit_tiers: tuple[str, ...] | None = None
    min_lines: int = 0
    min_tenure_months: int | None = None
    min_device_age_months: int | None = None
    min_support_contacts_90d: int | None = None
    requires_addon_kind: str | None = None
    min_accessories: int | None = None
    percent_off: int | None = None
    description: str | None = None


# Device protection is priced by tier (1-6) of the device. The site does not publish which devices fall in
# which tier, so tiers are derived from price (approximation).
PROTECTION_TIER_CEILINGS_CENTS = (25_000, 45_000, 65_000, 85_000, 120_000)


def protection_tier_for(msrp_cents: int) -> int:
    return 1 + sum(msrp_cents >= ceiling for ceiling in PROTECTION_TIER_CEILINGS_CENTS)


FLAGSHIP_MIN_CENTS = 79_900
MID_MIN_CENTS = 40_000
DECAY_BY_TIER = {"flagship": 0.028, "mid": 0.031, "value": 0.036}
FOLDABLE_DECAY = 0.034
FOLDABLE_MARKERS = ("Fold", "Flip", "razr")


LEGACY_SALE_YEARS = 2  # approximation: a phone stays on sale for about two years after release


def _sold_until(released: str, status: str) -> date | None:
    if status == "current":
        return None
    start = date.fromisoformat(released)
    return start.replace(year=start.year + LEGACY_SALE_YEARS)


def _device(n: int, name: str, mfr: str, dollars: float, released: str, status: str) -> Device:
    cents = round(dollars * 100)
    tier = "flagship" if cents >= FLAGSHIP_MIN_CENTS else "mid" if cents >= MID_MIN_CENTS else "value"
    foldable = any(marker in name for marker in FOLDABLE_MARKERS) and cents >= 69_900
    decay = FOLDABLE_DECAY if foldable else DECAY_BY_TIER[tier]
    return Device(f"TMO-STUB-DEV-{n:04d}", name, mfr, tier, None, cents, date.fromisoformat(released), decay, status,
                  protection_tier_for(cents), _sold_until(released, status))


# Names and starting prices of "current" devices were taken from t-mobile.com/cell-phones on 2026-10-08
# (full retail price, base storage; storage is not shown on that page, so it is left unspecified).
# Release dates are approximate. "legacy" devices are no longer sold: they exist so customers can own older
# phones; their names and launch prices come from general knowledge and are approximate.
_CURRENT = (
    ("iPhone 18 Pro Max", "Apple", 1299.99, "2026-09-18"), ("iPhone 18 Pro", "Apple", 1199.99, "2026-09-18"),
    ("iPhone 17 Pro Max", "Apple", 1199.99, "2025-09-19"), ("iPhone 17 Pro", "Apple", 1099.99, "2025-09-19"),
    ("iPhone Air", "Apple", 1099.99, "2025-09-19"), ("iPhone 17", "Apple", 929.99, "2025-09-19"),
    ("iPhone 16 Plus", "Apple", 829.99, "2024-09-20"), ("iPhone 16", "Apple", 829.99, "2024-09-20"),
    ("iPhone 17e", "Apple", 699.99, "2026-02-27"), ("iPhone 15", "Apple", 629.99, "2023-09-22"),
    ("Pixel 11 Pro Fold", "Google", 1899.99, "2026-08-20"), ("Pixel 11 Pro XL", "Google", 1299.99, "2026-08-20"),
    ("Pixel 11 Pro", "Google", 1099.99, "2026-08-20"), ("Pixel 11", "Google", 899.99, "2026-08-20"),
    ("Pixel 10 Pro XL", "Google", 1199.99, "2025-08-28"), ("Pixel 10 Pro", "Google", 999.99, "2025-08-28"),
    ("Pixel 10", "Google", 699.99, "2025-08-28"), ("Pixel 9", "Google", 799.99, "2024-08-22"),
    ("Pixel 10a", "Google", 499.99, "2026-03-05"), ("Pixel 9a", "Google", 299.99, "2025-04-10"),
    ("Galaxy Z Fold8 Ultra", "Samsung", 2099.99, "2026-07-24"), ("Galaxy Z Fold8", "Samsung", 1899.99, "2026-07-24"),
    ("Galaxy Z Flip8", "Samsung", 1199.99, "2026-07-24"), ("Galaxy Z Fold7", "Samsung", 1999.99, "2025-07-25"),
    ("Galaxy S26 Ultra", "Samsung", 1399.99, "2026-03-11"), ("Galaxy S26+", "Samsung", 1199.99, "2026-03-11"),
    ("Galaxy S26", "Samsung", 999.99, "2026-03-11"), ("Galaxy S26 FE", "Samsung", 799.99, "2026-09-04"),
    ("Galaxy S25 Ultra", "Samsung", 1299.99, "2025-02-07"), ("Galaxy S25 Edge", "Samsung", 1099.99, "2025-05-30"),
    ("Galaxy S25+", "Samsung", 999.99, "2025-02-07"), ("Galaxy S25 FE", "Samsung", 649.99, "2025-09-04"),
    ("Galaxy A57 5G", "Samsung", 609.99, "2026-03-25"), ("Galaxy A37 5G", "Samsung", 449.99, "2026-03-25"),
    ("Galaxy A36 5G", "Samsung", 399.99, "2025-03-26"), ("Galaxy A17 5G", "Samsung", 229.99, "2025-08-14"),
    ("razr fold - 2026", "Motorola", 1699.99, "2026-04-24"), ("razr+ 2026", "Motorola", 999.99, "2026-04-24"),
    ("razr ultra - 2025", "Motorola", 999.99, "2025-05-08"), ("razr - 2026", "Motorola", 769.99, "2026-04-24"),
    ("razr+ 2025", "Motorola", 699.99, "2025-05-08"), ("moto g stylus - 2026", "Motorola", 309.99, "2026-04-10"),
    ("moto g - 2026", "Motorola", 229.99, "2026-01-15"), ("TCL NXTPAPER 70 Pro", "TCL", 199.99, "2026-05-01"),
    ("Revvl 8 Pro", "T-Mobile", 249.99, "2026-02-10"),
)
_LEGACY = (
    ("iPhone 16 Pro Max", "Apple", 1199.99, "2024-09-20"), ("iPhone 16 Pro", "Apple", 999.99, "2024-09-20"),
    ("iPhone 15 Pro", "Apple", 999.99, "2023-09-22"), ("iPhone 14", "Apple", 799.99, "2022-09-16"),
    ("iPhone 13", "Apple", 799.99, "2021-09-24"), ("iPhone 12", "Apple", 799.99, "2020-10-23"),
    ("Galaxy S24 Ultra", "Samsung", 1299.99, "2024-01-31"), ("Galaxy S24", "Samsung", 799.99, "2024-01-31"),
    ("Galaxy S23", "Samsung", 799.99, "2023-02-17"), ("Galaxy S22", "Samsung", 799.99, "2022-02-25"),
    ("Galaxy Z Fold6", "Samsung", 1899.99, "2024-07-24"), ("Galaxy Z Flip6", "Samsung", 1099.99, "2024-07-24"),
    ("Galaxy A14 5G", "Samsung", 199.99, "2023-01-13"), ("Galaxy A13 5G", "Samsung", 179.99, "2022-03-25"),
    ("Pixel 8", "Google", 699.99, "2023-10-12"), ("Pixel 8a", "Google", 499.99, "2024-05-14"),
    ("Pixel 7", "Google", 599.99, "2022-10-13"),
)

DEVICES: tuple[Device, ...] = tuple(
    _device(n, name, mfr, price, released, status)
    for n, (name, mfr, price, released, status) in enumerate(
        (*((*row, "current") for row in _CURRENT), *((*row, "legacy") for row in _LEGACY)), start=1
    )
)
_DEVICES_BY_NAME = {d.name: d for d in DEVICES}


def device_by_name(name: str) -> Device:
    return _DEVICES_BY_NAME[name]


def _marginal(totals: tuple[int, ...]) -> tuple[int, ...]:
    return (totals[0], *(later - earlier for earlier, later in zip(totals, totals[1:], strict=False)))


# Source: t-mobile.com/cell-phone-plans (2026-10-08), prices per month for 1..5 lines with AutoPay.
# Where the page shows nothing (marked None) the value is left unspecified. Assumptions: a variant
# (Community, Partner, 55+) shares its base plan's benefits; lines beyond the published table cost
# the same as the last published line (Essentials publishes its 6th line at $20).
_ESSENTIALS = Plan(
    sku="TMO-STUB-PLAN-ESSENTIALS", name="Essentials 2.0", family="essentials", variant="standard", tier="standard",
    line_prices=_marginal((6500, 10000, 12000, 14000, 16000)), extra_line_cents=2000, min_lines=1, max_lines=None,
    data_cap_gb=50, hotspot_high_speed_gb=0, hotspot_unlimited=True, canada_mexico_gb=None, intl_data_gb=None,
    video_quality=None, price_guarantee_years=None, priority_network=False, prices_include_autopay=True,
    device_connection_cents=3500, eligibility=None, perks=(), upgrade_note=None, status="current",
)
_MORE = Plan(
    sku="TMO-STUB-PLAN-MORE", name="Experience More 2.0", family="experience_more", variant="standard",
    tier="premium", line_prices=_marginal((9000, 15000, 18500, 22000, 25500)), extra_line_cents=3500, min_lines=1,
    max_lines=None, data_cap_gb=None, hotspot_high_speed_gb=60, hotspot_unlimited=False, canada_mexico_gb=15,
    intl_data_gb=5, video_quality="4k", price_guarantee_years=5, priority_network=False, prices_include_autopay=True,
    device_connection_cents=3500, eligibility=None, perks=("streaming-video-ads", "streaming-video-offer-3usd"),
    upgrade_note="Upgrade-ready every three years, with new-customer deals", status="current",
)
_BEYOND = replace(
    _MORE, sku="TMO-STUB-PLAN-BEYOND", name="Experience Beyond 2.0", family="experience_beyond",
    line_prices=_marginal((10500, 18000, 23000, 28000, 33000)), extra_line_cents=5000, hotspot_high_speed_gb=250,
    hotspot_unlimited=True, canada_mexico_gb=30, intl_data_gb=15,
    perks=("streaming-video-ads", "streaming-video-bundle", "satellite-connectivity", "streaming-video-offer-3usd"),
    upgrade_note="Early upgrade with the same deals as new customers",
)


def _variant(base: Plan, suffix: str, label: str, variant: str, totals: tuple[int, ...], **changes) -> Plan:
    prices = _marginal(totals)
    return replace(
        base, sku=f"{base.sku}-{suffix}", name=f"{base.name.rsplit(' ', 1)[0]} {label} 2.0", variant=variant,
        line_prices=prices, extra_line_cents=changes.pop("extra_line_cents", prices[-1]), **changes,
    )


PLANS: tuple[Plan, ...] = (
    replace(
        _ESSENTIALS, sku="TMO-STUB-PLAN-ESSENTIALS-SAVER", name="Essentials Saver 2.0", variant="saver", tier="basic",
        line_prices=_marginal((5500, 9000)), extra_line_cents=3500, max_lines=2, device_connection_cents=None,
    ),
    _ESSENTIALS,
    replace(
        _ESSENTIALS, sku="TMO-STUB-PLAN-ESSENTIALS-4LINE", name="Essentials 4 Line Offer 2.0",
        variant="four_line_offer", line_prices=(3000,) * 5, extra_line_cents=3000, min_lines=4,
        device_connection_cents=None, status="limited_time",
    ),
    _MORE,
    _variant(_MORE, "COMMUNITY", "w/ Community Savings", "community", (7500, 11000, 13500, 16000, 18500),
             eligibility="community", priority_network=True),
    _variant(_MORE, "PARTNER", "w/ Partner Savings", "partner", (7500, 11000, 13500, 16000, 18500),
             eligibility="partner"),
    _variant(_MORE, "55", "w/ 55+ Savings", "senior_55", (7500, 11000), eligibility="55_plus", max_lines=2),
    _BEYOND,
    _variant(_BEYOND, "COMMUNITY", "w/ Community Savings", "community", (9000, 14000, 18000, 22000, 26000),
             eligibility="community", priority_network=True),
    _variant(_BEYOND, "PARTNER", "w/ Partner Savings", "partner", (9000, 14000, 18000, 22000, 26000),
             eligibility="partner"),
    _variant(_BEYOND, "55", "w/ 55+ Savings", "senior_55", (9000, 14000), eligibility="55_plus", max_lines=2),
)


_PROTECTION_MONTHLY_CENTS = (700, 900, 1300, 1600, 1900, 2600)
_CONNECTION_CHARGE_CENTS = 3500
_MORE_AND_BEYOND = ("experience_more", "experience_beyond")


# Per-claim fees (cents) by tier: screen damage, other damage, loss or theft. INVENTED stub values: the site says
# the fee depends on device model and claim type but does not publish amounts. They rise with the tier.
_DEDUCTIBLES_CENTS = (
    (1900, 2900, 4900), (2900, 4900, 6900), (2900, 7900, 9900),
    (4900, 9900, 14900), (4900, 12900, 19900), (9900, 19900, 24900),
)


def _protection(tier: int, monthly: int) -> Addon:
    screen, damage, loss = _DEDUCTIBLES_CENTS[tier - 1]
    return Addon(
        f"TMO-STUB-ADD-PROT-T{tier}", f"Device Protection Tier {tier}", "protection", monthly, 0, "device",
        "Accidental damage, loss and theft coverage; the monthly price and per-claim fees depend on the device's tier",
        protection_tier=tier, deductible_screen_cents=screen, deductible_damage_cents=damage,
        deductible_loss_theft_cents=loss,
    )


def _accessory(sku: str, name: str, cents: int, device_names: tuple[str, ...] | None = None) -> Addon:
    devices = None if device_names is None else tuple(device_by_name(n).sku for n in device_names)
    return Addon(f"TMO-STUB-ADD-{sku}", name, "accessory", 0, cents, "item", compatible_devices=devices)


# The site's accessory page only shows examples for the newest iPhones, so these cover every other phone. They are
# INVENTED stub products (generic names and prices) so a cart suggestion engine has something to suggest.
_BRAND_ACCESSORIES = (("CASE", "Protective Case", 3999), ("SCREEN", "Glass Screen Protector", 2999))
_UNIVERSAL_ACCESSORIES = (
    ("ACC-CHARGER-FAST", "Fast Wall Charger", 3499), ("ACC-CABLE-2PACK", "Charging Cable Twin Pack", 1999),
    ("ACC-EARBUDS", "Wireless Earbuds", 8999), ("ACC-POWERBANK", "Portable Power Bank", 4999),
)


def _brand_accessories() -> tuple[Addon, ...]:
    out = []
    for brand in ("Apple", "Samsung", "Google", "Motorola"):
        fits = tuple(d.sku for d in DEVICES if d.manufacturer == brand)
        for kind, name, cents in _BRAND_ACCESSORIES:
            out.append(Addon(f"TMO-STUB-ADD-ACC-{kind}-{brand.upper()}", f"{name} ({brand} phones)", "accessory", 0,
                             cents, "item", compatible_devices=fits))
    return tuple(out)


def _universal_accessories() -> tuple[Addon, ...]:
    return tuple(
        Addon(f"TMO-STUB-ADD-{sku}", name, "accessory", 0, cents, "item") for sku, name, cents in _UNIVERSAL_ACCESSORIES
    )


# Source: t-mobile.com plans, device protection, home internet, smartwatch and accessories pages (2026-10-08).
# Names are generic on purpose. Protection tier prices come from a search snippet; the page itself states a
# $7-$26 range. Unpublished details are left unspecified (None).
ADDONS: tuple[Addon, ...] = (
    *(_protection(tier, price) for tier, price in enumerate(_PROTECTION_MONTHLY_CENTS, start=1)),
    Addon("TMO-STUB-ADD-STREAM-VIDEO", "Streaming Video Add-on", "streaming", 300, 0, "account",
          "Discounted streaming video subscription", eligible_families=_MORE_AND_BEYOND),
    Addon("TMO-STUB-ADD-LINE-WATCH", "Smartwatch Line", "connected_line", 1000, _CONNECTION_CHARGE_CENTS, "line",
          "Unlimited talk, text and high-speed data for a smartwatch; postpaid only"),
    Addon("TMO-STUB-ADD-LINE-WATCH-PLUS", "Smartwatch Line Plus", "connected_line", 1500, _CONNECTION_CHARGE_CENTS,
          "line", "Smartwatch line with Canada/Mexico (15 GB) and international data (5 GB, 215+ destinations)"),
    Addon("TMO-STUB-ADD-LINE-CONNECTED-BEYOND", "Connected Device Line (Beyond only)", "connected_line", 500, 0,
          "line", "Watch or tablet line at a reduced price", eligible_families=("experience_beyond",)),
    Addon("TMO-STUB-ADD-HINT-BASIC", "Home Internet Basic", "home_internet", 5000, _CONNECTION_CHARGE_CENTS,
          "account", "Home internet gateway included; 170-354 Mbps; 5-year price guarantee; $15 off with a phone line"),
    Addon("TMO-STUB-ADD-HINT-PLUS", "Home Internet Plus", "home_internet", 6000, _CONNECTION_CHARGE_CENTS,
          "account", "Wi-Fi 7 gateway included; 170-498 Mbps; 5-year price guarantee; $15 off with a phone line"),
    Addon("TMO-STUB-ADD-HINT-PREMIUM", "Home Internet Premium", "home_internet", 7000, _CONNECTION_CHARGE_CENTS,
          "account", "Wi-Fi 7 gateway and mesh extender; 170-498 Mbps; $15 off with a phone line"),
    _accessory("ACC-CASE-SILICONE-18PRO", "Silicone Magnetic Case (iPhone 18 Pro)", 4999, ("iPhone 18 Pro",)),
    _accessory("ACC-CASE-KICKSTAND-18PROMAX", "Kickstand Magnetic Case (iPhone 18 Pro Max)", 6999,
               ("iPhone 18 Pro Max",)),
    _accessory("ACC-CASE-RUGGED-18PRO", "Rugged Magnetic Case (iPhone 18 Pro)", 7499, ("iPhone 18 Pro",)),
    _accessory("ACC-SCREEN-PRIVACY-18PRO", "Privacy Glass Screen Protector (iPhone 18 Pro)", 5999, ("iPhone 18 Pro",)),
    _accessory("ACC-LENS-PROTECTOR", "Camera Lens Protector", 2499),
    _accessory("ACC-BUNDLE-3IN1-18PRO", "3-in-1 Charging Bundle (iPhone 18 Pro)", 9999, ("iPhone 18 Pro",)),
    *_brand_accessories(),
    *_universal_accessories(),
)

def _skus(*names: str) -> tuple[str, ...]:
    return tuple(device_by_name(n).sku for n in names)


_ALL = ("essentials", "experience_more", "experience_beyond")
_MORE_UP = ("experience_more", "experience_beyond")
_BEYOND = ("experience_beyond",)
_DEVICE = {"kind": "device_credit", "per": "device", "payout_months": 36, "max_units": 4, "source": "site"}

# Source: t-mobile.com/offers, /switch/free-cell-phone-with-plan and /cell-phone-plans/student-discounts
# (2026-10-08). Values are the "up to" maximums. Names are generic. "stub" promotions are invented retention
# offers (the site does not publish any): they exist so retention strategies have actions to choose from.
PROMOTIONS: tuple[Promotion, ...] = (
    Promotion("PROMO-STUB-IPHONE18PRO", "iPhone 18 Pro and Pro Max credit", value_cents=100_000,
              device_skus=_skus("iPhone 18 Pro", "iPhone 18 Pro Max"), requires_new_line=True, requires_port_in=True,
              requires_tradein=True, new_line_or_tradein=True, plan_families=_BEYOND, min_plan_cents=10_000,
              **_DEVICE),
    Promotion("PROMO-STUB-IPHONE17", "iPhone 17 credit", value_cents=83_000, device_skus=_skus("iPhone 17"),
              requires_new_line=True, requires_port_in=True, plan_families=_MORE_UP, min_plan_cents=8_500, **_DEVICE),
    Promotion("PROMO-STUB-IPHONE17E", "iPhone 17e credit", value_cents=70_000, device_skus=_skus("iPhone 17e"),
              requires_new_line=True, requires_port_in=True, plan_families=_ALL, min_plan_cents=6_000, **_DEVICE),
    Promotion("PROMO-STUB-FLIP8", "Galaxy Z Flip8 credit", value_cents=120_000, device_skus=_skus("Galaxy Z Flip8"),
              requires_new_line=True, requires_tradein=True, new_line_or_tradein=True, plan_families=_MORE_UP,
              min_plan_cents=8_500, **_DEVICE),
    Promotion("PROMO-STUB-PIXEL11PROXL", "Pixel 11 Pro XL credit", value_cents=100_000,
              device_skus=_skus("Pixel 11 Pro XL"), requires_new_line=True, requires_tradein=True,
              new_line_or_tradein=True, plan_families=_MORE_UP, min_plan_cents=8_500, **_DEVICE),
    Promotion("PROMO-STUB-RAZRPLUS", "razr+ 2026 credit", value_cents=110_000, device_skus=_skus("razr+ 2026"),
              requires_new_line=True, plan_families=_BEYOND, min_plan_cents=10_000, **_DEVICE),
    Promotion("PROMO-STUB-S26FE", "Galaxy S26 FE trade-in credit", value_cents=80_000,
              device_skus=_skus("Galaxy S26 FE"), requires_tradein=True, plan_families=_MORE_UP, min_plan_cents=8_500,
              **_DEVICE),
    Promotion("PROMO-STUB-FREE-SELECT", "Free select phone credit", value_cents=30_099,
              device_skus=_skus("Galaxy A17 5G", "moto g - 2026", "moto g stylus - 2026", "Revvl 8 Pro"),
              requires_new_line=True, plan_families=_ALL, min_plan_cents=6_000, credit_tiers=("prime",),
              **{**_DEVICE, "max_units": 12}),
    Promotion("PROMO-STUB-TRADEIN-ANY", "Trade in any phone, any condition", value_cents=20_000,
              requires_tradein=True, requires_device=True, plan_families=_ALL, **_DEVICE),
    Promotion("PROMO-STUB-FAMILY-PAYOFF", "Family payoff card: up to $800 per line", "prepaid_card", 80_000,
              "site", per="device", max_units=4, requires_new_line=True, requires_port_in=True,
              requires_tradein=True, requires_device=True,
              description="Prepaid card to pay off the old phones when a family switches and trades in"),
    Promotion("PROMO-STUB-BYOD-CARD", "Bring your own phone card", "prepaid_card", 20_000, "site", per="line",
              max_units=4, requires_new_line=True, requires_port_in=True, requires_byod=True,
              plan_families=_ALL, min_plan_cents=6_000),
    Promotion("PROMO-STUB-KEEP-YOUR-PHONE", "Keep your phone monthly credit", "bill_credit", 2_000, "site",
              payout_months=36, requires_new_line=True, requires_port_in=True, requires_byod=True,
              plan_families=("essentials",), plan_variants=("saver",), min_plan_cents=5_000),
    Promotion("PROMO-STUB-GROUP-NEW-PHONE", "Group savings new-phone credit", "device_credit", 90_000, "site",
              payout_months=24, per="device", max_units=4, requires_new_line=True, requires_port_in=True,
              requires_device=True, plan_families=_MORE_UP, discount_plan_only=True,
              discount_groups=("55_plus", "partner", "community")),
    Promotion("PROMO-STUB-WATCH-LINE", "Smartwatch line credit", "line_credit", 30_000, "site", payout_months=36,
              requires_addon_kind="connected_line", min_lines=2),
    Promotion("PROMO-STUB-HINT-CARD", "Home Internet new-line card", "prepaid_card", 20_000, "site",
              requires_addon_kind="home_internet"),
    Promotion("PROMO-STUB-BUNDLE-HINT", "Home Internet bundle credit", "bill_credit", 1_500, "site",
              requires_addon_kind="home_internet", min_lines=1,
              description="$15 off per month with a phone line"),
    Promotion("PROMO-STUB-ACC-BUNDLE", "Accessory bundle discount", "accessory_discount", 0, "site", per="cart",
              max_units=6, min_accessories=3, percent_off=25),
    Promotion("PROMO-STUB-STUDENT", "Student monthly credit", "bill_credit", 2_000, "site", per="line", max_units=2,
              plan_families=_ALL, discount_groups=("student",),
              description="$20 off per line per month for verified students, up to 2 lines"),
    Promotion("PROMO-STUB-LOYALTY-CREDIT", "Loyalty monthly credit", "bill_credit", 500, "stub",
              min_tenure_months=36),
    Promotion("PROMO-STUB-CARE-CREDIT", "Care goodwill credit", "bill_credit", 2_500, "stub", payout_months=1,
              min_tenure_months=6, min_support_contacts_90d=3),
    Promotion("PROMO-STUB-OLD-PHONE-UPGRADE", "Upgrade an older phone credit", "device_credit", 15_000, "stub",
              payout_months=24, per="device", max_units=4, requires_tradein=True, requires_device=True,
              min_device_age_months=36),
)


def plan_price_cents(plan: Plan, line_index: int) -> int:
    """Marginal monthly price of the line at this 0-based position in the household."""
    return plan.line_prices[line_index] if line_index < len(plan.line_prices) else plan.extra_line_cents


def plan_total_cents(plan: Plan, lines: int) -> int:
    return sum(plan_price_cents(plan, i) for i in range(lines))


def tradein_value_cents(device: Device, age_months: int) -> int:
    """Exponentially decaying resale value with a floor, never above MSRP."""
    residual = max(0.06, exp(-device.decay_rate * age_months) * 0.78)
    return round(device.msrp_cents * residual)


def tradein_curve(device: Device) -> tuple[tuple[int, int], ...]:
    return tuple((age, tradein_value_cents(device, age)) for age in range(MAX_TRADEIN_AGE_MONTHS + 1))
