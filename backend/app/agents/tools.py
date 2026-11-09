"""Tools the agents call for every figure. Each wraps deterministic Phase 2-4 code.

Outputs are compact JSON: Groq's free tier allows only a few thousand tokens a minute, so the
agent gets just the numbers it needs to explain, not whole database rows.
"""
from datetime import date

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session

from app.api.expenses import load_expense_data
from app.models import User
from app.services import allocation as alloc
from app.services.expenses import build_insights, build_summary, month_key
from app.services.fd_pick import pick_fd
from app.services.fund_ranking import rank_funds
from app.services.planner import plan_goal
from app.services.recommend import build_plan, investable_surplus, load_market
from app.services.risk import financial_snapshot
from app.services.stock_scoring import pick_stocks, score_stocks


def _pct(x: float | None, digits: int = 1) -> float | None:
    return None if x is None else round(x * 100, digits)


def compact_fund(f: dict) -> dict:
    m = f["metrics"]
    return {"name": f["short_name"], "category": f["category"], "score": f["score"],
            "rank": f"{f['rank_in_category']} of {f['peers']}", "cagr_3y_pct": _pct(m["cagr_3y"]),
            "sharpe_3y": m["sharpe_3y"] and round(m["sharpe_3y"], 2), "max_drawdown_3y_pct": _pct(m["max_drawdown_3y"]),
            "reasons": f["reasons"], "cautions": f["cautions"]}


def compact_stock(s: dict) -> dict:
    return {"symbol": s["symbol"], "name": s["name"], "sector": s["sector"], "score": s["score"],
            "factor_percentiles": s["factors"], "eligible": s["eligible"], "reasons": s["reasons"], "cautions": s["cautions"]}


def compact_plan(plan: dict) -> dict:
    """The /api/recommend plan, trimmed to what an explanation needs."""
    def pick(p):
        if "scheme_code" in p:
            return compact_fund(p)
        if "bank" in p:
            return {"bank": p["bank"], "rate_pct": p["rate"], "tenure_years": round(p["tenure_days"] / 365)}
        return {"symbol": p["symbol"], "score": p["score"]}

    em, inv, fd = plan["emergency"], plan["investable"], plan["fd"]
    return {
        "profile": plan["profile"],
        "investable_monthly": inv["monthly"], "investable_source": inv["source"],
        "invest_for_growth_monthly": inv["to_invest"], "lumpsum_available": inv["lumpsum"],
        "emergency_fund": {k: em[k] for k in ("ok", "target", "current", "shortfall", "monthly_contribution", "months_to_fill")}
                          | {"liquid_fund": em["picks"][0]["short_name"] if em["picks"] else None},
        "allocation_pct": {k: _pct(v, 0) for k, v in plan["allocation"]["weights"].items()},
        "expected_return_pct": _pct(plan["allocation"]["expected_return"]),
        "allocation_rationale": plan["allocation"]["rationale"],
        "plan_starts": plan["plan_starts"],
        "monthly_plan": [{"sleeve": i["label"], "monthly": i["monthly"], "lumpsum": i["lumpsum"],
                          "share_pct": _pct(i["share"], 0), "picks": [pick(p) for p in i["picks"][:2]]} for i in plan["plan"]],
        "fd": fd and {"best": fd["best"] and {"bank": fd["best"]["bank"], "rate_pct": fd["best"]["rate"]},
                      "tenure_years": round(fd["tenure_days"] / 365), "notes": fd["notes"]},
        "top_stocks": [compact_stock(s) for s in plan["stocks"]["picks"][:5]],
        "notes": plan["notes"],
        "tax_regime": plan["tax_regime"],
    }


def build_tools(db: Session, user: User) -> list[BaseTool]:
    """Tools bound to the current user and DB session."""
    p = user.profile

    @tool
    def get_financial_snapshot() -> dict:
        """The user's profile: age, income, expenses, savings, risk score and category, horizon, emergency-fund status."""
        return {"age": p.age, "monthly_income": p.monthly_income, "monthly_expenses": p.monthly_expenses,
                "current_savings": p.current_savings, "dependents": p.dependents, "horizon_years": p.horizon_years,
                "goals": p.goals, "risk_score": p.risk_score, "risk_category": p.risk_category,
                **financial_snapshot(p.monthly_income, p.monthly_expenses, p.current_savings)}

    @tool
    def get_investment_plan(tax_regime: str = "new") -> dict:
        """The user's full recommended plan: investable surplus, emergency fund, asset allocation with reasons,
        monthly SIP split with fund/FD/stock picks. tax_regime: 'new' or 'old' (old enables 80C picks)."""
        return compact_plan(build_plan(db, user, old_tax_regime=tax_regime == "old"))

    @tool
    def get_stock_scores(top_n: int = 5, risk_category: str | None = None) -> dict:
        """Top NIFTY 50 stocks scored on value, quality, momentum and low volatility for a risk category
        (defaults to the user's). Use for questions about specific stocks or stock picks."""
        cat = risk_category if risk_category in ("conservative", "moderate", "aggressive") else p.risk_category
        stocks, _, _ = load_market(db)
        scored = score_stocks(stocks, cat)
        return {"risk_category": cat, "picks": [compact_stock(s) for s in pick_stocks(scored, n=max(1, min(top_n, 10)))]}

    @tool
    def lookup_stock(symbol: str) -> dict:
        """Score and key metrics for one NIFTY 50 stock by NSE symbol (e.g. INFY, HDFCBANK)."""
        stocks, _, _ = load_market(db)
        for i, s in enumerate(score_stocks(stocks, p.risk_category), 1):
            if s["symbol"] == symbol.upper().strip():
                return compact_stock(s) | {"rank_in_nifty50": i, "price": s["price"],
                                           "metrics": {k: v for k, v in s["metrics"].items() if v is not None}}
        return {"error": f"{symbol} is not in the NIFTY 50 data"}

    @tool
    def get_fund_rankings(category: str) -> dict:
        """Mutual funds ranked within a category, e.g. 'Flexi Cap', 'Index', 'Large Cap', 'Mid Cap',
        'Small Cap', 'ELSS', 'Hybrid', 'Debt', 'Liquid'."""
        _, funds, _ = load_market(db)
        ranked = [f for f in rank_funds(funds) if f["category"].lower() == category.lower().strip()]
        cats = sorted({f["category"] for f in funds})
        return {"category": category, "funds": [compact_fund(f) for f in ranked[:5]]} if ranked else \
            {"error": f"No funds in '{category}'", "available_categories": cats}

    @tool
    def get_fd_options(years: int, amount: float = 100000) -> dict:
        """Best fixed-deposit rates for a tenure in years (1-5) and amount, with maturity values.
        Applies senior-citizen rates automatically for users aged 60+."""
        _, _, rows = load_market(db)
        r = pick_fd(rows, int(years), p.age, old_tax_regime=True, amount=float(amount))

        def q(x):
            return x and {k: x[k] for k in ("bank", "bank_type", "rate", "maturity_value", "interest")}

        return {"tenure_years": round(r["tenure_days"] / 365), "amount": amount, "senior": r["senior"], "best": q(r["best"]),
                "best_large_bank": q(r["safest"]), "others": [q(a) for a in r["alternatives"]],
                "tax_saver_fd": q(r["tax_saver"]), "rates_as_of": str(r["as_of"]), "notes": r["notes"]}

    @tool
    def plan_goal_sip(goal_amount: float, years: int, current_corpus: float = 0, inflation: float = 0.06,
                      annual_return: float | None = None) -> dict:
        """Monthly SIP needed to reach a goal amount (in today's rupees) in N years. annual_return and inflation are
        fractions (0.12 = 12%); annual_return defaults to the user's allocation for that horizon."""
        years = max(1, min(int(years), 50))
        if annual_return is None:
            a = alloc.asset_allocation(p.risk_score, p.risk_category, p.age, years)
            annual_return = alloc.expected_return(a["weights"])
        r = plan_goal(goal_amount, years, annual_return, current_corpus, inflation,
                      monthly_budget=investable_surplus(db, user)["monthly"])
        r.pop("projection")
        return r | {"annual_return_pct": _pct(annual_return), "inflation_pct": _pct(inflation)}

    @tool
    def get_expense_summary(month: str | None = None) -> dict:
        """The user's spending for a month (YYYY-MM, default this month): totals, top categories,
        50/30/20 split and savings insights."""
        month = month or month_key(date.today())
        txns, budgets, income = load_expense_data(db, user, month)
        s = build_summary(txns, month, budgets, income)
        ins = build_insights(txns, month, budgets, income)
        return {"month": month, "income": s["income_base"], "spent": s["expense"], "invested": s["invested"],
                "saved": s["net"], "savings_rate_pct": _pct(s["savings_rate"]),
                "top_categories": [{"category": c["label"], "amount": c["amount"], "budget": c["budget"]}
                                   for c in s["categories"][:5]],
                "needs_wants_savings_pct": {k: _pct(v, 0) for k, v in s["bucket_share"].items()},
                "insights": [f"{i['title']}: {i['detail']}" for i in ins["insights"][:5]],
                "potential_monthly_saving": ins["potential_monthly_saving"]}

    return [get_financial_snapshot, get_investment_plan, get_stock_scores, lookup_stock, get_fund_rankings,
            get_fd_options, plan_goal_sip, get_expense_summary]
