"""Household Mix Optimizer: households where a different arrangement could cost less or fit better."""

from ..rows import LineSpec
from .base import BEYOND, ESS, HOUSEHOLD, MORE, customer

HOUSEHOLDS = (
    customer(
        37, "family", 36, 0.15, (
            LineSpec("primary", "moderate", 14, plan_sku=MORE, label="Parent 1"),
            LineSpec("partner", "light", 18, plan_sku=MORE, label="Parent 2"),
            LineSpec("teen", "light", 10, plan_sku=MORE, label="Teen"),
            LineSpec("child", "light", 10, plan_sku=MORE, label="Child"),
        ), support_recent=0, support_older=0,
        title="Family of four on an unlimited plan with light usage", theme=HOUSEHOLD,
        scenario="Four lines, none using much data, all on a premium unlimited plan. Are there plans or offers aimed "
                 "at exactly this kind of household?",
    ),
    customer(
        38, "senior", 60, 0.1, (
            LineSpec("senior", "moderate", 20, plan_sku=MORE, label="Partner 1"),
            LineSpec("senior", "light", 26, plan_sku=MORE, label="Partner 2"),
        ), discount_group="55_plus", support_recent=0, support_older=0,
        title="Couple over 55 paying standard prices", theme=HOUSEHOLD,
        scenario="Both partners qualify for 55+ pricing but are on the regular version of the same plan. What changes "
                 "if they use the pricing they qualify for?",
    ),
    customer(
        39, "family", 36, 0.2, (
            LineSpec("primary", "moderate", 12, plan_sku=ESS, label="Parent 1"),
            LineSpec("partner", "light", 14, plan_sku=ESS, label="Parent 2"),
            LineSpec("teen", "moderate", 10, plan_sku=ESS, label="Teen A"),
            LineSpec("teen", "moderate", 10, plan_sku=ESS, label="Teen B"),
            LineSpec("child", "light", 12, plan_sku=ESS, label="Child"),
        ), support_recent=0, support_older=0,
        title="Five lines on the entry-level plan", theme=HOUSEHOLD,
        scenario="Five lines that mostly stay under the data cap. There are special offers and plan variants for "
                 "households with many lines.",
    ),
    customer(
        40, "family", 40, 0.15, (
            LineSpec("primary", "heavy", 14, plan_sku=BEYOND, label="Parent 1"),
            LineSpec("partner", "moderate", 16, plan_sku=BEYOND, label="Parent 2"),
            LineSpec("adult", "moderate", 12, plan_sku=BEYOND, label="Adult child"),
        ), discount_group="partner",
        support_recent=0, support_older=0, title="Household that qualifies for a partner discount but does not use it",
        theme=HOUSEHOLD,
        scenario="Three lines on the top plan at the regular price, in a household that is eligible for the partner "
                 "version of that same plan.",
    ),
    customer(
        41, "couple", 80, 0.1, (
            LineSpec("primary", "moderate", 16, plan_sku=MORE, label="Parent 1"),
            LineSpec("partner", "moderate", 20, plan_sku=MORE, label="Parent 2"),
        ), related=42, support_recent=0,
        support_older=0, title="Parents on their own account while their grown child has another",
        theme=HOUSEHOLD,
        scenario="Two lines on one account. Their adult child and partner have their own separate account, also on "
                 "the same plan. Would one combined account be better for everyone?",
    ),
    customer(
        42, "couple", 30, 0.2, (
            LineSpec("primary", "moderate", 10, plan_sku=MORE, label="Adult child"),
            LineSpec("partner", "moderate", 12, plan_sku=MORE, label="Partner"),
        ), related=41, support_recent=0,
        support_older=0, title="Young couple paying separately from the parents' account", theme=HOUSEHOLD,
        scenario="Two lines on their own account, on the same plan as the parents' separate account. They split bills "
                 "informally and would be open to combining.",
    ),
)
