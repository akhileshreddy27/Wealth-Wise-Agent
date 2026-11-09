"""Goal / SIP planner.

Uses the same convention as the expense insights (`sip_future_value`): monthly rate = annual / 12,
contributions at the start of each month (annuity due), which is how SIPs are usually quoted.
"""
from math import ceil

MAX_YEARS = 50


def _factor(r: float, n: int) -> float:
    """Future value of ₹1 invested at the start of each of n months."""
    return n if r == 0 else (((1 + r) ** n - 1) / r) * (1 + r)


def sip_future_value(monthly: float, years: float, annual_return: float, corpus: float = 0) -> float:
    r, n = annual_return / 12, round(years * 12)
    return monthly * _factor(r, n) + corpus * (1 + r) ** n


def months_to_goal(goal: float, monthly: float, annual_return: float, corpus: float = 0) -> int | None:
    r, balance = annual_return / 12, corpus
    for month in range(1, MAX_YEARS * 12 + 1):
        balance = (balance + monthly) * (1 + r)
        if balance >= goal:
            return month
    return None


def plan_goal(goal_amount: float, years: int, annual_return: float, current_corpus: float = 0,
              inflation: float = 0.0, monthly_budget: float | None = None) -> dict:
    """Monthly SIP needed to reach `goal_amount` (in today's rupees if `inflation` > 0) in `years`."""
    n, r = years * 12, annual_return / 12
    target = goal_amount * (1 + inflation) ** years
    corpus_fv = current_corpus * (1 + r) ** n
    needed = max(0.0, target - corpus_fv) / _factor(r, n)
    monthly = ceil(needed / 100) * 100 if needed else 0     # round up to ₹100

    projection, invested = [], current_corpus
    for y in range(1, years + 1):
        invested += monthly * 12
        projection.append({"year": y, "invested": round(invested),
                           "value": round(sip_future_value(monthly, y, annual_return, current_corpus))})

    out = {
        "goal_amount": goal_amount, "years": years, "annual_return": annual_return, "inflation": inflation,
        "target_amount": round(target), "current_corpus": current_corpus,
        "corpus_future_value": round(corpus_fv),
        "monthly_sip": monthly,
        "total_invested": round(current_corpus + monthly * n),
        "projected_value": projection[-1]["value"] if projection else round(corpus_fv),
        "projection": projection,
        "assumptions": [
            f"{annual_return:.1%} a year expected return (not guaranteed)",
            f"Goal inflated at {inflation:.1%} a year" if inflation else "Goal amount is in future rupees (no inflation)",
            "SIP paid at the start of each month",
        ],
    }
    out["gains"] = out["projected_value"] - out["total_invested"]
    if monthly_budget is not None:
        out["monthly_budget"] = round(monthly_budget)
        out["affordable"] = monthly <= monthly_budget
        m = months_to_goal(target, monthly_budget, annual_return, current_corpus) if monthly_budget > 0 else None
        out["months_at_budget"] = m
    return out
