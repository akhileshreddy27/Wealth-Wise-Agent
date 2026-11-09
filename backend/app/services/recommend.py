"""Builds the personalised plan behind /api/recommend from the Phase 4 building blocks.

    investable surplus -> emergency fund first -> asset allocation -> sleeves -> fund / stock / FD picks

Everything here is deterministic: the same profile and market data give the same plan,
and every number can be traced back to a rule in allocation.py, stock_scoring.py,
fund_ranking.py, fd_pick.py or planner.py.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FdRate, FinancialProfile, MutualFund, Stock, Transaction, User
from app.services import allocation as alloc
from app.services.expenses import build_summary, month_key, shift_month
from app.services.fd_pick import pick_fd
from app.services.fund_ranking import picks_for_sleeve, rank_funds
from app.services.stock_scoring import WEIGHTS as STOCK_WEIGHTS
from app.services.stock_scoring import pick_stocks, score_stocks

DISCLAIMER = ("Educational output from rule-based models, not SEBI-registered investment advice. "
              "Past returns don't guarantee future returns; FD rates are indicative.")


def as_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ---------- inputs ----------
def investable_surplus(db: Session, user: User, today: date | None = None, lookback: int = 3) -> dict:
    """Monthly amount available to invest.

    Uses actual savings (income minus non-investment spending) averaged over the last `lookback`
    complete months that have transactions; falls back to the profile's income minus expenses.
    """
    p: FinancialProfile = user.profile
    profile_surplus = max(0.0, p.monthly_income - p.monthly_expenses)
    this_month = month_key(today or date.today())
    months = [shift_month(this_month, -i) for i in range(1, lookback + 1)]
    start = date.fromisoformat(months[-1] + "-01")
    txns = list(db.scalars(select(Transaction).where(
        Transaction.user_id == user.id, Transaction.date >= start,
        Transaction.date < date.fromisoformat(this_month + "-01"))))

    used = sorted({month_key(t.date) for t in txns if t.kind == "expense"})
    if not used:
        return {"monthly": round(profile_surplus, 2), "source": "profile", "months_used": [],
                "profile_surplus": round(profile_surplus, 2)}
    nets = [build_summary(txns, m, {}, p.monthly_income)["net"] for m in used]
    avg = sum(nets) / len(nets)
    return {"monthly": round(max(0.0, avg), 2), "source": "expenses", "months_used": used,
            "actual_average": round(avg, 2), "profile_surplus": round(profile_surplus, 2)}


def load_market(db: Session) -> tuple[list[dict], list[dict], list[dict]]:
    stocks = [as_dict(s) for s in db.scalars(select(Stock))]
    funds = [as_dict(f) for f in db.scalars(select(MutualFund))]
    fds = [as_dict(r) for r in db.scalars(select(FdRate))]
    return stocks, funds, fds


# ---------- plan ----------
def build_plan(db: Session, user: User, old_tax_regime: bool = False, today: date | None = None) -> dict:
    p: FinancialProfile = user.profile
    experience = int((p.risk_answers or {}).get("experience", 1))
    stocks, funds, fd_rows = load_market(db)

    investable = investable_surplus(db, user, today)
    emergency = alloc.emergency_plan(p.monthly_expenses, p.current_savings, investable["monthly"])
    to_invest = max(0.0, investable["monthly"] - emergency["monthly_contribution"])
    lumpsum = max(0.0, p.current_savings - emergency["target"]) if emergency["ok"] else 0.0

    allocation = alloc.asset_allocation(p.risk_score, p.risk_category, p.age, p.horizon_years)
    sleeves = alloc.sleeve_weights(allocation, p.risk_category, experience)
    # If the emergency fund takes the whole surplus for now, show the plan that starts once it's full.
    starts_after_emergency = to_invest == 0 and investable["monthly"] > 0 and not emergency["ok"]
    plan_amount = investable["monthly"] if starts_after_emergency else to_invest
    monthly, notes = alloc.monthly_split(plan_amount, sleeves, elss=old_tax_regime)
    lump, _ = alloc.monthly_split(lumpsum, sleeves, elss=False) if lumpsum else ({}, [])

    if not emergency["ok"]:
        allocation["rationale"].insert(0, (
            f"Emergency fund first: {alloc.SLEEVE_LABEL['liquid'].lower()} get ₹{emergency['monthly_contribution']:,.0f}"
            f"/month until you have 6 months of expenses saved."))

    ranked_funds = rank_funds(funds)
    scored_stocks = score_stocks(stocks, p.risk_category) if stocks else []
    stock_picks = pick_stocks(scored_stocks)
    fd_amount = lump.get("fd") or 100000
    fd = pick_fd(fd_rows, p.horizon_years, p.age, old_tax_regime, amount=fd_amount) if fd_rows else None

    blended = alloc.expected_return(allocation["weights"], (fd["best"]["rate"] / 100) if fd and fd["best"] else None)

    plan = []
    for sleeve, amount in sorted(monthly.items(), key=lambda kv: -kv[1]):
        item = {"sleeve": sleeve, "label": alloc.SLEEVE_LABEL[sleeve], "asset": alloc.SLEEVE_ASSET[sleeve],
                "monthly": amount, "lumpsum": lump.get(sleeve, 0.0),
                "share": round(amount / sum(monthly.values()), 4) if monthly else 0}
        if sleeve == "stocks":
            item["picks"] = [{"symbol": s["symbol"], "name": s["name"], "score": s["score"]} for s in stock_picks[:5]]
        elif sleeve == "fd":
            item["picks"] = [fd["best"]] if fd and fd["best"] else []
        else:
            item["picks"] = picks_for_sleeve(ranked_funds, sleeve)
        plan.append(item)

    emergency_fund_picks = picks_for_sleeve(ranked_funds, "liquid", 1) if not emergency["ok"] else []

    return {
        "profile": {"age": p.age, "risk_score": p.risk_score, "risk_category": p.risk_category,
                    "horizon_years": p.horizon_years, "experience": experience, "goals": p.goals},
        "investable": investable | {"to_invest": round(to_invest, 2), "lumpsum": round(lumpsum, 2)},
        "emergency": emergency | {"picks": emergency_fund_picks},
        "allocation": allocation | {"expected_return": blended, "assumed_returns": alloc.EXPECTED_RETURN},
        "plan": plan,
        "plan_starts": "after_emergency" if starts_after_emergency else "now",
        "notes": notes,
        "stocks": {"picks": stock_picks, "eligible": sum(s["eligible"] for s in scored_stocks),
                   "universe": len(scored_stocks), "weights": STOCK_WEIGHTS[p.risk_category]},
        "fd": fd,
        "tax_regime": "old" if old_tax_regime else "new",
        "data": {"stocks": len(stocks), "funds": len(funds), "fds": len(fd_rows)},
        "disclaimer": DISCLAIMER,
    }

