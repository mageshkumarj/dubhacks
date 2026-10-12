"""Next Best Moment: customers drifting (or not) towards leaving, each for a different reason."""

from ..rows import LineSpec
from .base import BEYOND, ESS, HINT, MORE, NEXT_BEST_MOMENT, SAVER, VIDEO, customer, dev

CHURN = (
    customer(
        21, "single", 70, 0.1, (LineSpec("primary", "moderate", 30, plan_sku=MORE),),
        "Long-time customer, no support contact, researching competitors.", support_recent=0, support_older=0,
        competitor_score=0.85, port_out=True, app_sessions=2,
        title="Long-time customer who went quiet and is shopping around", theme=NEXT_BEST_MOMENT,
        scenario="Nearly six years with us and no support contact at all, but their app use has dropped to almost "
                 "nothing and they have asked about moving their number elsewhere.",
    ),
    customer(
        22, "couple", 28, 0.3, (
            LineSpec("primary", "moderate", 14, plan_sku=MORE, label="Partner 1"),
            LineSpec("partner", "moderate", 14, plan_sku=MORE, label="Partner 2"),
        ), "Couple whose bill rose after a promotion ended.", bill_spike_pct=0.22, support_recent=2, support_older=0,
        support_topics=("billing",), support_sentiment=-0.5, support_resolved=False, competitor_score=0.55,
        title="Couple hit by a bill increase after a promotion ended", theme=NEXT_BEST_MOMENT,
        scenario="Their bill went up by about a fifth two months ago. They have contacted us about billing twice and "
                 "neither contact was resolved.",
    ),
    customer(
        23, "family", 45, 0.4, (
            LineSpec("primary", "moderate", 18, plan_sku=MORE, label="Parent 1"),
            LineSpec("partner", "moderate", 24, plan_sku=MORE, label="Parent 2"),
            LineSpec("teen", "heavy", 12, plan_sku=MORE, label="Teen"),
        ), "Family with repeated unresolved network complaints.", support_recent=4, support_older=1,
        support_topics=("network",), support_sentiment=-0.6, support_resolved=False, competitor_score=0.75,
        title="Family complaining repeatedly about coverage", theme=NEXT_BEST_MOMENT,
        scenario="Four network complaints in three months, none resolved. The plan, price and devices are all fine "
                 "for them. The problem is the service itself.",
    ),
    customer(
        24, "single", 55, 0.1, (LineSpec("primary", "moderate", 20, plan_sku=MORE),),
        "Frequent caller, always resolved, happy.", support_recent=6, support_older=3,
        support_topics=("device", "plan_change"), support_sentiment=0.5, support_resolved=True, competitor_score=0.1,
        port_out=False, app_sessions=20, title="Frequent caller who is happy and loyal", theme=NEXT_BEST_MOMENT,
        scenario="Nine contacts in nine months, which looks alarming, but every one was resolved with a good outcome "
                 "and they use the app constantly.",
    ),
    customer(
        25, "single", 5, 0.5, (LineSpec("primary", "heavy", 4, plan_sku=ESS),),
        "New customer whose usage exceeds their plan.", support_recent=1, support_older=0, competitor_score=0.4,
        title="New customer whose usage already exceeds their plan", theme=NEXT_BEST_MOMENT,
        scenario="Five months in, they use more data than their plan includes and are still paying off their phone. "
                 "Nothing is broken yet, but the fit is poor.",
    ),
    customer(
        26, "family", 100, 0.1, (
            LineSpec("primary", "moderate", 12, plan_sku=BEYOND, label="Parent 1"),
            LineSpec("partner", "moderate", 16, plan_sku=BEYOND, label="Parent 2"),
            LineSpec("teen", "light", 14, plan_sku=BEYOND, label="Teen"),
        ), "Loyal bundled family, casually looking at competitors.", services=(HINT, VIDEO), support_recent=0,
        support_older=0, competitor_score=0.55, port_out=False,
        title="Loyal bundled family casually comparing carriers", theme=NEXT_BEST_MOMENT,
        scenario="Eight years of service, home internet and streaming bundled, and no complaints. They have looked at "
                 "competitor websites but have not contacted anyone.",
    ),
    customer(
        27, "couple", 12, 0.5, (
            LineSpec("primary", "moderate", 6, device_sku=dev("Galaxy S26 Ultra"), plan_sku=MORE, financed=True),
            LineSpec("partner", "moderate", 4, device_sku=dev("iPhone 17 Pro Max"), plan_sku=MORE, financed=True),
        ), "Unhappy couple still paying off two expensive phones.", credit_tier="subprime", support_recent=3,
        support_older=0, support_topics=("billing", "network"), support_sentiment=-0.55, support_resolved=False,
        competitor_score=0.5, title="Couple locked in by phone financing but unhappy", theme=NEXT_BEST_MOMENT,
        scenario="A year in, they owe well over a thousand dollars on two phones and have complained about billing and "
                 "coverage. Leaving would be expensive for them.",
    ),
    customer(
        28, "student", 40, 0.3, (LineSpec("student", "light", byod=True, plan_sku=SAVER),),
        "Student near graduation on the cheapest plan.", discount_group="student", support_recent=0,
        support_older=0, competitor_score=0.6, port_out=False,
        title="Student approaching graduation", theme=NEXT_BEST_MOMENT,
        scenario="A student nearing the end of their studies has been a customer for over three years on the cheapest "
                 "plan with a student credit. Their situation, and their loyalty, is about to change.",
    ),
)
