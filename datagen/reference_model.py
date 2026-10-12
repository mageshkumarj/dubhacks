"""Toy churn model for tests and dry runs ONLY.

Real judging must use a private model file (see README, "For organizers"). Anything in this public
file is, by definition, known to every student.
"""

import math


def probability(account_id: str, features: dict, conn) -> float:
    logit = (
        -3.9
        + 0.45 * features["support_90d"]
        + 0.8 * max(0.0, -features["avg_sentiment"])
        + 4.0 * features["bill_increase_pct"]
        + 2.2 * features["competitor_research"]
        + 1.2 * features["port_out_inquiry"]
        - 0.01 * min(features["tenure_months"], 60)
        + 0.7 * features["plan_misfit_share"]
    )
    return 1 / (1 + math.exp(-logit))
