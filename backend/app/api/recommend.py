from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.services import allocation as alloc
from app.services.fund_ranking import rank_funds
from app.services.planner import plan_goal
from app.services.recommend import build_plan, investable_surplus, load_market
from app.services.stock_scoring import WEIGHTS, pick_stocks, score_stocks

router = APIRouter(prefix="/recommend", tags=["recommend"])

RiskCategory = Literal["conservative", "moderate", "aggressive"]


def _require_profile(user: User):
    if user.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Create your financial profile first")
    return user.profile


@router.get("")
def recommend(
    tax_regime: Literal["new", "old"] = Query("new", description="'old' enables 80C picks (ELSS, tax-saver FD)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full personalised plan: emergency fund, allocation, monthly SIP split with picks, stocks, FD."""
    _require_profile(user)
    return build_plan(db, user, old_tax_regime=tax_regime == "old")


@router.get("/stocks")
def stock_scores(
    risk_category: RiskCategory | None = None,
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every NIFTY 50 stock scored for a risk category (defaults to the user's), plus diversified picks."""
    cat = risk_category or _require_profile(user).risk_category
    stocks, _, _ = load_market(db)
    scored = score_stocks(stocks, cat)
    return {"risk_category": cat, "weights": WEIGHTS[cat], "picks": pick_stocks(scored, n=limit), "scored": scored}


@router.get("/funds")
def fund_ranks(category: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Funds ranked within their category (optionally one category)."""
    _, funds, _ = load_market(db)
    ranked = rank_funds(funds)
    if category:
        ranked = [f for f in ranked if f["category"] == category]
    return {"items": ranked}


@router.get("/sip-plan")
def sip_plan(
    goal_amount: float = Query(..., gt=0, le=1e11),
    years: int = Query(..., ge=1, le=50),
    annual_return: float | None = Query(None, ge=0, le=0.30, description="Defaults to your allocation's expected return"),
    current_corpus: float = Query(0, ge=0, le=1e11),
    inflation: float = Query(0.06, ge=0, le=0.15),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Monthly SIP needed for a goal, compared with what you can invest each month."""
    p = user.profile
    if annual_return is None:
        # The goal's own horizon drives the mix: a 2-year goal gets no equity, so a lower return.
        p = _require_profile(user)
        a = alloc.asset_allocation(p.risk_score, p.risk_category, p.age, years)
        annual_return = alloc.expected_return(a["weights"])
    budget = investable_surplus(db, user)["monthly"] if p else None
    return plan_goal(goal_amount, years, annual_return, current_corpus, inflation, monthly_budget=budget)
