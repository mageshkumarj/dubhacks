"""Matchmaker: people who need help choosing a plan and a phone."""

from ..rows import LineSpec
from .base import CART_WHISPERER, ESS, MATCHMAKER, NEXT_BEST_MOMENT, SAVER, customer, prospect

MATCH = (
    customer(
        19, "single", 22, 0.3, (LineSpec("primary", "heavy", 12, plan_sku=SAVER),),
        "Heavy video streamer on the basic plan.", support_recent=1, support_older=0,
        title="Customer whose video habit outgrew a basic plan", theme=MATCHMAKER, secondary=(NEXT_BEST_MOMENT,),
        scenario="Usage has grown to far more than the plan was built for since they began streaming video all day. "
                 "Which plan would suit how they use their phone now?",
    ),
    customer(
        20, "couple", 18, 0.2, (
            LineSpec("primary", "moderate", 10, plan_sku=ESS, label="Partner 1"),
            LineSpec("partner", "moderate", 12, plan_sku=ESS, label="Partner 2"),
        ), "Couple who want a smartwatch and home internet.", support_recent=0, support_older=0,
        title="Couple who want a smartwatch and home internet", theme=MATCHMAKER, secondary=(CART_WHISPERER,),
        scenario="Two moderate users on a basic plan say they would like a smartwatch line and home internet. Which "
                 "plan and bundle fit them, and what are the trade-offs?",
    ),
    prospect(
        3, title="Budget single who already owns a phone", theme=MATCHMAKER, lines=1, budget_dollars=55, usage="light",
        notes="Mostly texts and maps, own phone, wants a low bill without surprises.",
        scenario="A new customer wants one line for as little as possible with the phone they already have. They "
                 "stream almost nothing.",
    ),
    prospect(
        4, title="Family of four with two heavy-streaming teens", theme=MATCHMAKER, lines=4, budget_dollars=220,
        usage="heavy", notes="Teens stream and game all day; parents want new phones and a bill under $220.",
        scenario="A family of four is switching and wants everyone on one plan. The teens use a lot of data, the "
                 "parents much less, and the budget is limited.",
    ),
    prospect(
        5, title="Frequent traveler to Canada and Mexico", theme=MATCHMAKER, lines=2, budget_dollars=240,
        usage="moderate",
        notes="Crosses the border most months and needs data abroad, video calls with family overseas.",
        scenario="Two travelers need dependable data in Canada, Mexico and occasionally further away, and are willing "
                 "to pay for it.",
    ),
    prospect(
        6, title="Retired couple who want it simple", theme=MATCHMAKER, lines=2, budget_dollars=110, usage="light",
        notes="55 and over, own phones, mostly calls, no interest in streaming or extras.",
        scenario="Two people over 55 want straightforward service and the lowest sensible price, with no gadgets.",
    ),
    prospect(
        7, title="Heavy hotspot user who wants the newest phone", theme=MATCHMAKER, lines=1, budget_dollars=200,
        usage="heavy", notes="Works and games from a hotspot, wants the best flagship, price is flexible.",
        scenario="A power user runs their work and gaming from a hotspot and wants the newest flagship. They say "
                 "price matters less than not running out of data.",
    ),
    prospect(
        8, title="Small business owner with five lines", theme=MATCHMAKER, lines=5, budget_dollars=300,
        usage="moderate",
        notes="Wants a predictable bill and a price guarantee; some staff travel for work.",
        scenario="A shop owner needs five lines, wants to know what the bill will be next year, and has a monthly "
                 "budget of around $300.",
    ),
)
