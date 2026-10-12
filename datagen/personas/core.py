"""The original ten personas, now tagged with a theme and a scenario."""

from .. import catalog
from ..rows import LineSpec
from .base import (
    BEYOND, CART_WHISPERER, ESS, HINT, HOUSEHOLD, MATCHMAKER, MORE, NEXT_BEST_MOMENT, SAVER, TIMEKEEPER, VIDEO,
    customer,
)

CORE = (
    customer(
        1, "student", 8, 0.1, (LineSpec("student", "light", byod=True, plan_sku=SAVER),),
        "College student, BYOD, budget-sensitive, light usage.", credit_tier="near_prime", discount_group="student",
        support_recent=0, support_older=0, title="Budget student with their own phone", theme=MATCHMAKER,
        secondary=(CART_WHISPERER,), cart=({"kind": "new_line", "plan": "ESSENTIALS-SAVER", "port_in": True},),
        scenario="A first-year student paying for the cheapest plan with a phone they already own. A friend wants to "
                 "join their account and bring their number over. What plan and offers suit two budget-minded lines?",
    ),
    customer(
        2, "family", 60, 0.2, (
            LineSpec("primary", "moderate", 14, plan_sku=MORE, label="Dad"),
            LineSpec("partner", "moderate", 20, plan_sku=MORE, label="Mom"),
            LineSpec("teen", "heavy", 8, plan_sku=MORE, label="Teen A"),
            LineSpec("teen", "heavy", 10, plan_sku=MORE, label="Teen B"),
            LineSpec("child", "light", 18, plan_sku=MORE, label="Kid"),
        ), "Family of five with two heavy-streaming teens.", services=(HINT, VIDEO), support_recent=1,
        support_older=1, title="Family of five with two streaming teens", theme=HOUSEHOLD,
        scenario="Five lines share one plan and a large monthly bill. Two teens use far more data than the parents and "
                 "the youngest uses very little. Is this household set up in the best way?",
    ),
    customer(
        3, "single", 52, 0.2,
        (LineSpec("primary", "moderate", 40, device_sku=catalog.device_by_name("iPhone 13").sku, plan_sku=ESS,
                  financed=False),),
        "Upgrader: phone is 3+ years old, fully paid off, trade-in eligible.", support_recent=0, support_older=1,
        title="Paid-off phone that is over three years old", theme=TIMEKEEPER, secondary=(CART_WHISPERER,),
        cart=({"kind": "device", "device": "iPhone 18 Pro"}, {"kind": "tradein", "line": 1}),
        scenario="A loyal single-line customer on a modest plan owns a fully paid-off iPhone 13 and keeps getting "
                 "upgrade prompts. Is now a good time to upgrade, and what would it cost or save?",
    ),
    customer(
        4, "couple", 40, 0.85, (
            LineSpec("primary", "moderate", 22, plan_sku=MORE, label="Alex"),
            LineSpec("partner", "moderate", 22, plan_sku=MORE, label="Sam"),
            LineSpec("adult", "heavy", 10, plan_sku=MORE, label="Line 3"),
        ), "At-risk: recent support friction, bill jump, researching competitors.", bill_spike_pct=0.18,
        support_recent=5, support_older=2, title="Couple whose bill jumped and who keep calling support",
        theme=NEXT_BEST_MOMENT,
        scenario="Three lines, a steady bill until two months ago, and a run of unhappy support contacts about network "
                 "and devices. They have also been researching other carriers. What should happen next?",
    ),
    customer(
        5, "family", 36, 0.3, (
            LineSpec("primary", "light", 30, plan_sku=BEYOND, label="Light user A"),
            LineSpec("partner", "light", 26, plan_sku=BEYOND, label="Light user B"),
            LineSpec("teen", "light", 12, plan_sku=BEYOND, label="Light user C"),
        ), "Overpaying household: premium plan on every line, tiny usage.", support_recent=1, support_older=0,
        title="Household paying for a premium plan it barely uses", theme=HOUSEHOLD,
        scenario="Three lines on the most expensive plan, each using only a few gigabytes a month. What setup would "
                 "serve this household well for less?",
    ),
    customer(
        6, "smb", 28, 0.25, (
            LineSpec("primary", "moderate", 15, plan_sku=ESS, label="Owner"),
            LineSpec("employee", "moderate", 15, plan_sku=ESS, label="Staff 1"),
            LineSpec("employee", "heavy", 15, plan_sku=ESS, label="Staff 2 (field)"),
            LineSpec("employee", "moderate", 15, plan_sku=ESS, label="Staff 3"),
        ), "Small business with a heavy-usage field employee on a capped plan.", support_recent=1, support_older=1,
        title="Small business with one heavy field employee", theme=HOUSEHOLD,
        scenario="Four business lines on one capped plan. One field employee uses far more data than the rest and may "
                 "exceed the plan's limit. How should the plan be arranged?",
    ),
    customer(
        7, "single", 30, 0.15,
        (LineSpec("primary", "moderate", 3, device_sku=catalog.device_by_name("iPhone 17").sku, plan_sku=MORE,
                  financed=True),),
        "Upgraded a few months ago and is still paying off the phone.", support_recent=0, support_older=0,
        title="Customer who upgraded three months ago", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "iPhone 18 Pro"}, {"kind": "tradein", "line": 1}),
        scenario="A customer bought an iPhone 17 three months ago and still owes most of it. A new upgrade offer has "
                 "just reached their inbox. How should we respond to them?",
    ),
    customer(
        8, "senior", 90, 0.1, (
            LineSpec("senior", "light", 30, plan_sku=ESS, label="Grandpa"),
            LineSpec("senior", "light", 30, plan_sku=ESS, label="Grandma"),
        ), "Retired couple, very light usage, long tenure; eligible for 55+ pricing.", contact_preference="call",
        discount_group="55_plus", support_recent=0, support_older=1, title="Retired couple with very light usage",
        theme=HOUSEHOLD,
        scenario="Two lines used mostly for calls, with long tenure and a preference for phone support. "
                 "Are they on the most suitable plan, and are they getting every discount they can?",
    ),
    customer(
        9, "single", 18, 0.35,
        (LineSpec("primary", "heavy", 6, device_sku=catalog.device_by_name("Galaxy Z Fold7").sku, plan_sku=ESS,
                  hotspot_user=True),),
        "Power user capped on Essentials, heavy data and hotspot.", support_recent=2, support_older=1,
        title="Power user who keeps hitting data limits", theme=MATCHMAKER,
        scenario="One line with very heavy data and hotspot use, on an entry-level plan with a data cap. Which plan "
                 "would suit how they actually use their phone?",
    ),
    customer(
        10, "family", 120, 0.05, (
            LineSpec("primary", "moderate", 12, plan_sku=BEYOND, label="Parent 1"),
            LineSpec("partner", "moderate", 16, plan_sku=BEYOND, label="Parent 2"),
            LineSpec("child", "light", 20, plan_sku=BEYOND, label="Kid"),
        ), "Loyal long-tenure household already bundled with home internet and streaming.", services=(HINT, VIDEO),
        support_recent=0, support_older=0, competitor_score=0.15, port_out=False, app_sessions=12,
        title="Loyal household of ten years, already bundled",
        theme=NEXT_BEST_MOMENT,
        scenario="A long-tenured family with Home Internet and streaming and no support history. Nothing looks wrong, "
                 "but retention budgets are limited. Should anyone act on this account?",
    ),
)
