"""Cart Whisperer: people at checkout, with a cart that could use better suggestions."""

from ..rows import LineSpec
from .base import BEYOND, CART_WHISPERER, ESS, MORE, SAVER, TIMEKEEPER, customer, dev, prospect

CART = (
    customer(
        11, "single", 60, 0.2,
        (LineSpec("primary", "moderate", 44, device_sku=dev("iPhone 14"), plan_sku=MORE, financed=False),),
        support_recent=0, support_older=0,
        title="Paid-off upgrader buying a new flagship", theme=CART_WHISPERER, secondary=(TIMEKEEPER,),
        cart=({"kind": "device", "device": "iPhone 18 Pro"}, {"kind": "tradein", "line": 1}),
        scenario="A customer with a paid-off iPhone 14 is checking out with an iPhone 18 Pro and a trade-in. The cart "
                 "has the phone and nothing else. What else would genuinely help them?",
    ),
    customer(
        12, "family", 30, 0.15, (
            LineSpec("primary", "moderate", 14, plan_sku=ESS, label="Parent 1"),
            LineSpec("partner", "light", 18, plan_sku=ESS, label="Parent 2"),
            LineSpec("child", "light", 10, plan_sku=ESS, label="Younger child"),
        ), support_recent=0, support_older=1,
        title="Family adding a teenager's first phone", theme=CART_WHISPERER,
        cart=({"kind": "new_line", "plan": "ESSENTIALS"}, {"kind": "device", "device": "Galaxy A17 5G"}),
        scenario="A family of three is adding a fourth line for a teenager and an inexpensive phone. What helps a "
                 "first-time phone owner and a parent watching the bill?",
    ),
    customer(
        13, "single", 14, 0.3, (LineSpec("primary", "moderate", byod=True, plan_sku=ESS),), support_recent=0,
        support_older=0,
        title="Adding a partner who is switching carriers", theme=CART_WHISPERER,
        cart=({"kind": "new_line", "plan": "ESSENTIALS", "port_in": True},),
        scenario="A customer is adding a second line for a partner who is moving over from another carrier and keeping "
                 "their number and their own phone. What would make joining worthwhile?",
    ),
    customer(
        14, "couple", 36, 0.2, (
            LineSpec("primary", "moderate", 16, plan_sku=MORE, label="Partner 1"),
            LineSpec("partner", "moderate", 22, plan_sku=MORE, label="Partner 2"),
        ), support_recent=0, support_older=0,
        title="Couple adding home internet to their phones", theme=CART_WHISPERER,
        cart=({"kind": "addon", "addon": "HINT-BASIC"},),
        scenario="A couple already on an unlimited phone plan has put Home Internet in their cart. What else fits "
                 "this household, and is there a better way to buy it?",
    ),
    customer(
        15, "couple", 24, 0.2, (
            LineSpec("primary", "moderate", 12, plan_sku=MORE, label="Partner 1"),
            LineSpec("partner", "light", 15, plan_sku=MORE, label="Partner 2"),
        ), support_recent=0, support_older=1,
        title="Couple adding a smartwatch line", theme=CART_WHISPERER,
        cart=({"kind": "addon", "addon": "LINE-WATCH-PLUS"},),
        scenario="One partner is adding a smartwatch line to the account. Which offers, accessories and extras suit "
                 "someone buying a connected device?",
    ),
    customer(
        16, "single", 32, 0.2,
        (LineSpec("primary", "moderate", 30, device_sku=dev("Pixel 8"), plan_sku=ESS, financed=False),),
        support_recent=0, support_older=0,
        title="Upgrader who has not thought about trading in", theme=CART_WHISPERER,
        cart=({"kind": "device", "device": "Pixel 11"},),
        scenario="A customer is checking out with a Pixel 11 and has not mentioned their current Pixel 8. The cart "
                 "has only the new phone.",
    ),
    customer(
        17, "student", 14, 0.2, (LineSpec("student", "light", 12, plan_sku=SAVER),), credit_tier="near_prime",
        discount_group="student",
        support_recent=0, support_older=0, title="Student buying a phone and a few accessories", theme=CART_WHISPERER,
        cart=({"kind": "device", "device": "iPhone 17e"}, {"kind": "addon", "addon": "ACC-CASE-APPLE"},
              {"kind": "addon", "addon": "ACC-SCREEN-APPLE"}),
        scenario="A student on a tight budget is buying an iPhone 17e with a case and a screen protector. Is there a "
                 "smarter way to fill this cart?",
    ),
    customer(
        18, "single", 48, 0.15,
        (LineSpec("primary", "heavy", 16, device_sku=dev("Galaxy Z Fold6"), plan_sku=BEYOND, financed=True),),
        support_recent=0, support_older=0,
        title="Buying a $2,000 foldable phone", theme=CART_WHISPERER,
        cart=({"kind": "device", "device": "Galaxy Z Fold8 Ultra"}, {"kind": "tradein", "line": 1}),
        scenario="A heavy user is upgrading from a foldable they bought sixteen months ago to the most expensive "
                 "foldable on offer. Protection, accessories and the trade-in all matter at this price.",
    ),
    prospect(
        1, title="New customer switching with a number to bring over", theme=CART_WHISPERER, lines=1,
        budget_dollars=110,
        usage="moderate", notes="Already chose an iPhone 17 and wants to keep their number from another carrier.",
        cart=({"kind": "device", "device": "iPhone 17"}, {"kind": "new_line", "plan": "MORE", "port_in": True}),
        scenario="Someone who is not yet a customer has an iPhone 17 and a new Experience More line in their cart and "
                 "plans to port their number in. What would complete the cart and which offers apply?",
    ),
    prospect(
        2, title="Retiree choosing a 55+ plan and a new phone", theme=CART_WHISPERER, lines=2, budget_dollars=130,
        usage="light", notes="Two lines, wants a reliable phone and the 55+ pricing, mostly calls and photos.",
        cart=({"kind": "device", "device": "Galaxy S26 FE"}, {"kind": "new_line", "plan": "MORE-55", "port_in": True},
              {"kind": "new_line", "plan": "MORE-55", "port_in": True}),
        scenario="A retired couple who are not yet customers have two 55+ lines and a Galaxy S26 FE in their cart. "
                 "Which offers apply and what would a first-time customer of this kind appreciate?",
    ),
)
