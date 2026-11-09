"""Asset allocation: risk score + age + horizon -> equity / debt / FD / liquid split.

Each rule is a simple, explainable cap applied in order, and each cap that bites adds a line
to `rationale`, so the UI (and the Phase 5 agents) can say *why* the split looks the way it does.
"""
from math import ceil

ASSETS = ("equity", "debt", "fd", "liquid")

# Long-run, pre-tax return assumptions used for projections. Deliberately conservative.
EXPECTED_RETURN = {"equity": 0.12, "debt": 0.07, "fd": 0.065, "liquid": 0.065}

MIN_SIP = 500  # most AMCs' minimum monthly SIP

# How the equity part is spread across fund "sleeves", by risk category.
EQUITY_MIX = {
    "conservative": {"core": 0.6, "hybrid": 0.4},
    "moderate":     {"core": 0.6, "flexi": 0.3, "mid": 0.1},
    "aggressive":   {"core": 0.4, "flexi": 0.3, "mid": 0.2, "small": 0.1},
}
# Share of equity in direct stocks, only for users who already invest (experience answer >= 3).
DIRECT_STOCK_SHARE = {"conservative": 0.0, "moderate": 0.10, "aggressive": 0.20}
ELSS_MONTHLY_CAP = 150000 / 12  # Section 80C limit is ₹1.5 lakh a year

SLEEVE_LABEL = {
    "core": "Index / large-cap funds", "hybrid": "Balanced advantage (hybrid) funds", "flexi": "Flexi-cap funds",
    "mid": "Mid-cap funds", "small": "Small-cap funds", "elss": "ELSS tax-saver funds", "stocks": "Direct stocks",
    "debt": "Debt funds", "fd": "Fixed deposits", "liquid": "Liquid funds",
}
SLEEVE_ASSET = {"core": "equity", "hybrid": "equity", "flexi": "equity", "mid": "equity", "small": "equity",
                "elss": "equity", "stocks": "equity", "debt": "debt", "fd": "fd", "liquid": "liquid"}


def _round5(x: float) -> int:
    return int(5 * round(x * 100 / 5))


def asset_allocation(risk_score: int, risk_category: str, age: int, horizon_years: int) -> dict:
    rationale: list[str] = []

    # 1. Risk score sets the starting equity share: 10% at score 1 up to 82% at score 10.
    equity = 0.10 + (risk_score - 1) * 0.08
    rationale.append(f"Risk score {risk_score}/10 suggests about {equity:.0%} in equity.")

    # 2. Age cap: the "100 minus age" rule of thumb, plus 10 points of headroom.
    age_cap = max(0.0, (110 - age) / 100)
    if equity > age_cap:
        equity = age_cap
        rationale.append(f"At age {age}, equity is capped at {age_cap:.0%} (110 minus age).")

    # 3. Horizon cap: money needed soon shouldn't ride the stock market.
    horizon_cap = 0.0 if horizon_years < 3 else 0.30 if horizon_years < 5 else 0.55 if horizon_years < 7 else 1.0
    if equity > horizon_cap:
        equity = horizon_cap
        rationale.append(
            f"With a {horizon_years}-year horizon, equity is capped at {horizon_cap:.0%}: "
            + ("stocks can stay down for 2-3 years." if horizon_cap == 0 else "a market fall may not recover in time."))

    eq = _round5(equity)

    # 4. A small liquid buffer for near-term needs (separate from the emergency fund).
    liq = 10 if horizon_years < 3 else 5

    # 5. The rest goes to fixed income, split between bank FDs and debt funds.
    rest = 100 - eq - liq
    fd_share = 0.7 if horizon_years < 3 else 0.6 if risk_score <= 3 else 0.5 if risk_score <= 6 else 0.4
    fd = _round5(rest * fd_share / 100)
    debt = rest - fd
    rationale.append(
        f"Fixed income ({rest}%) is split {fd}% FDs / {debt}% debt funds: FDs lock in a rate, "
        "debt funds can be withdrawn any time.")

    weights = {"equity": eq / 100, "debt": debt / 100, "fd": fd / 100, "liquid": liq / 100}
    return {
        "weights": weights,
        "equity_mix": EQUITY_MIX[risk_category],
        "rationale": rationale,
    }


def expected_return(weights: dict[str, float], fd_rate: float | None = None) -> float:
    r = {**EXPECTED_RETURN, **({"fd": fd_rate} if fd_rate else {})}
    return round(sum(w * r[a] for a, w in weights.items()), 4)


def emergency_plan(monthly_expenses: float, current_savings: float, investable: float) -> dict:
    """Emergency fund first: 6 months of expenses in a liquid fund before investing for growth.

    If the gap can be closed within 3 months, all of the surplus goes to it;
    otherwise half does, so long-term investing still starts now.
    """
    target = round(monthly_expenses * 6, 2)
    shortfall = round(max(0.0, target - current_savings), 2)
    if shortfall == 0 or investable <= 0:
        contribution = 0.0
    elif shortfall <= 3 * investable:
        contribution = investable
    else:
        contribution = investable / 2
    contribution = round(min(contribution, shortfall), 2)
    return {
        "ok": shortfall == 0,
        "target": target,
        "current": round(current_savings, 2),
        "shortfall": shortfall,
        "monthly_contribution": contribution,
        "months_to_fill": ceil(shortfall / contribution) if contribution else (0 if shortfall == 0 else None),
    }


def sleeve_weights(allocation: dict, risk_category: str, experience: int) -> dict[str, float]:
    """Expand asset weights into sleeves: equity -> core/flexi/mid/small/hybrid (+ stocks)."""
    w = allocation["weights"]
    stock_share = DIRECT_STOCK_SHARE[risk_category] if experience >= 3 else 0.0
    sleeves: dict[str, float] = {}
    if w["equity"]:
        if stock_share:
            sleeves["stocks"] = w["equity"] * stock_share
        for k, share in allocation["equity_mix"].items():
            sleeves[k] = w["equity"] * (1 - stock_share) * share
    for k in ("debt", "fd", "liquid"):
        if w[k]:
            sleeves[k] = w[k]
    return sleeves


def monthly_split(amount: float, sleeves: dict[str, float], elss: bool = False) -> tuple[dict[str, float], list[str]]:
    """Turn sleeve weights into rupee amounts (rounded to ₹100).

    - With the old tax regime, the flexi (or core) sleeve goes to ELSS up to the 80C limit.
    - Sleeves under the ₹500 SIP minimum are folded into the largest sleeve.
    """
    notes: list[str] = []
    rupees = {k: amount * v for k, v in sleeves.items()}

    if elss:
        room = ELSS_MONTHLY_CAP
        for src in ("flexi", "core", "hybrid"):   # ELSS funds are diversified equity, so they replace these first
            moved = min(rupees.get(src, 0), room)
            if moved:
                rupees[src] -= moved
                rupees["elss"] = rupees.get("elss", 0) + moved
                room -= moved
        if rupees.get("elss"):
            notes.append("ELSS funds replace part of your equity SIP to use the ₹1.5 lakh 80C deduction "
                         "(3-year lock-in, shortest among 80C options).")

    small = [k for k, v in rupees.items() if 0 < v < MIN_SIP]
    if small and len(rupees) > len(small):
        biggest = max((k for k in rupees if k not in small), key=lambda k: rupees[k])
        for k in small:
            rupees[biggest] += rupees.pop(k)
        notes.append(f"Sleeves under ₹{MIN_SIP}/month (the usual SIP minimum) were merged into "
                     f"{SLEEVE_LABEL[biggest].lower()}.")

    rounded = {k: float(round(v / 100) * 100) for k, v in rupees.items() if round(v / 100) > 0}
    return rounded, notes
