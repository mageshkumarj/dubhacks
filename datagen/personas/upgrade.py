"""Timekeeper: customers weighing whether to upgrade their phone now or wait."""

from ..rows import LineSpec
from .base import BEYOND, ESS, MORE, SAVER, TIMEKEEPER, customer, dev

UPGRADE = (
    customer(
        29, "single", 30, 0.15,
        (LineSpec("primary", "moderate", 20, device_sku=dev("iPhone 16"), plan_sku=MORE, financed=True),),
        support_recent=0, support_older=0,
        title="Phone with four payments left", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "iPhone 18 Pro"}, {"kind": "tradein", "line": 1}),
        scenario="Twenty months into a 24-month installment plan, the phone is nearly paid off and the upgrade offers "
                 "keep arriving.",
    ),
    customer(
        30, "single", 80, 0.2,
        (LineSpec("primary", "moderate", 48, device_sku=dev("iPhone 12"), plan_sku=ESS, financed=False),),
        support_recent=1, support_older=1,
        title="Four-year-old phone showing its age", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "iPhone 18 Pro"}, {"kind": "tradein", "line": 1}),
        scenario="A paid-off phone from 2022 still works, but it is getting old and its trade-in value keeps falling.",
    ),
    customer(
        31, "single", 40, 0.15,
        (LineSpec("primary", "heavy", 12, device_sku=dev("iPhone 17 Pro Max"), plan_sku=BEYOND, financed=True),),
        support_recent=0, support_older=0,
        title="Flagship owner just as the next model launches", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "iPhone 18 Pro Max"}, {"kind": "tradein", "line": 1}),
        scenario="Their iPhone 17 Pro Max is a year old and still has a year of payments left. The next iPhone has "
                 "just come out.",
    ),
    customer(
        32, "single", 50, 0.15,
        (LineSpec("primary", "moderate", 24, device_sku=dev("iPhone 16 Pro"), plan_sku=MORE, financed=False),),
        support_recent=0, support_older=0,
        title="Two-year-old flagship that is fully paid off", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "iPhone 18 Pro"}, {"kind": "tradein", "line": 1}),
        scenario="A premium phone from two years ago with no balance left, which still holds meaningful "
                 "trade-in value.",
    ),
    customer(
        33, "single", 26, 0.2,
        (LineSpec("primary", "heavy", 20, device_sku=dev("Galaxy Z Fold6"), plan_sku=BEYOND, financed=True),),
        support_recent=0, support_older=0,
        title="Foldable owner whose phone loses value quickly", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "Galaxy Z Fold8"}, {"kind": "tradein", "line": 1}),
        scenario="Twenty months into owning a foldable, with a few payments still to go. Foldables lose value faster "
                 "than other phones.",
    ),
    customer(
        34, "couple", 70, 0.15, (
            LineSpec("primary", "moderate", 32, device_sku=dev("Galaxy S23"), plan_sku=MORE, financed=False,
                     label="Partner 1"),
            LineSpec("partner", "moderate", 33, device_sku=dev("iPhone 14"), plan_sku=MORE, financed=False,
                     label="Partner 2"),
        ), support_recent=0, support_older=0,
        title="Couple whose two phones are due at the same time", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "iPhone 18 Pro"}, {"kind": "tradein", "line": 1}),
        scenario="Both partners bought their phones within a month of each other, nearly three years ago, and both "
                 "are paid off. Should they upgrade together or one after the other?",
    ),
    customer(
        35, "single", 18, 0.2,
        (LineSpec("primary", "light", 12, device_sku=dev("Galaxy A17 5G"), plan_sku=SAVER, financed=False),),
        support_recent=0, support_older=0,
        title="Budget phone owner with little to trade in", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "Galaxy A37 5G"}, {"kind": "tradein", "line": 1}),
        scenario="A year-old inexpensive phone, paid off, on the cheapest plan. There is little trade-in value to wait "
                 "for or lose.",
    ),
    customer(
        36, "single", 90, 0.15,
        (LineSpec("primary", "light", 58, device_sku=dev("iPhone 13"), plan_sku=SAVER, financed=False),),
        support_recent=0, support_older=1,
        title="Five-year-old phone with almost no trade-in value left", theme=TIMEKEEPER,
        cart=({"kind": "device", "device": "iPhone 17"}, {"kind": "tradein", "line": 1}),
        scenario="A phone from 2021 that is paid off and worth very little. It still does the job for a light user.",
    ),
)
