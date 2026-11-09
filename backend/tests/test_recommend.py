import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.market_data.fds import load_fd_rows
from app.models import FdRate, MutualFund, Stock
from app.services import allocation as alloc
from app.services.fd_pick import fd_tenure_days, pick_fd
from app.services.fund_ranking import in_sleeve, picks_for_sleeve, rank_funds
from app.services.planner import months_to_goal, plan_goal, sip_future_value
from app.services.ranking import percentiles
from app.services.stock_scoring import passes_risk_filter, pick_stocks, score_stocks

client = TestClient(app)
ANSWERS = {"market_drop": 3, "primary_goal": 3, "experience": 3, "return_vs_risk": 3, "income_stability": 3}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


# ---------- ranking ----------
def test_percentiles():
    assert percentiles([10, 20, 30]) == [0, 0.5, 1]
    assert percentiles([10, 20, 30], higher_is_better=False) == [1, 0.5, 0]
    assert percentiles([5, None, 5, 9]) == [0.25, None, 0.25, 1]   # ties share the average rank
    assert percentiles([7]) == [0.5]                                 # no peers -> neutral


# ---------- allocation ----------
@pytest.mark.parametrize("score,cat,age,horizon", [
    (1, "conservative", 65, 2), (5, "moderate", 35, 6), (10, "aggressive", 24, 15), (8, "aggressive", 55, 10)])
def test_allocation_sums_to_one(score, cat, age, horizon):
    w = alloc.asset_allocation(score, cat, age, horizon)["weights"]
    assert sum(w.values()) == pytest.approx(1)
    assert all(v >= 0 for v in w.values())


def test_allocation_caps():
    young = alloc.asset_allocation(10, "aggressive", 24, 15)
    assert young["weights"]["equity"] == 0.80
    short = alloc.asset_allocation(10, "aggressive", 24, 2)
    assert short["weights"]["equity"] == 0 and short["weights"]["liquid"] == 0.10
    assert any("horizon" in r for r in short["rationale"])
    older = alloc.asset_allocation(9, "aggressive", 70, 10)
    assert older["weights"]["equity"] == 0.40 and any("age 70" in r for r in older["rationale"])


def test_emergency_plan():
    ok = alloc.emergency_plan(30000, 200000, 20000)
    assert ok["ok"] and ok["monthly_contribution"] == 0 and ok["months_to_fill"] == 0
    small_gap = alloc.emergency_plan(30000, 150000, 20000)      # gap 30k <= 3 x 20k -> all of the surplus
    assert small_gap["monthly_contribution"] == 20000 and small_gap["months_to_fill"] == 2
    big_gap = alloc.emergency_plan(30000, 0, 20000)             # gap 180k -> half of the surplus
    assert big_gap["monthly_contribution"] == 10000 and big_gap["months_to_fill"] == 18
    nothing = alloc.emergency_plan(30000, 0, 0)
    assert nothing["months_to_fill"] is None


def test_sleeves_and_monthly_split():
    a = alloc.asset_allocation(8, "aggressive", 28, 12)
    novice = alloc.sleeve_weights(a, "aggressive", experience=1)
    assert "stocks" not in novice and sum(novice.values()) == pytest.approx(1)
    pro = alloc.sleeve_weights(a, "aggressive", experience=4)
    assert pro["stocks"] == pytest.approx(a["weights"]["equity"] * 0.2)

    split, notes = alloc.monthly_split(50000, pro, elss=True)
    assert split["elss"] == 12500 and all(v % 100 == 0 for v in split.values())
    assert sum(split.values()) == pytest.approx(50000, abs=500)

    tiny, notes = alloc.monthly_split(3000, pro)
    assert all(v >= alloc.MIN_SIP for v in tiny.values()) and any("merged" in n for n in notes)


def test_expected_return():
    assert alloc.expected_return({"equity": 1, "debt": 0, "fd": 0, "liquid": 0}) == 0.12
    assert alloc.expected_return({"equity": 0, "debt": 0, "fd": 1, "liquid": 0}, fd_rate=0.07) == 0.07


# ---------- stock scoring ----------
def _stock(sym, sector="IT", **kw):
    base = {"symbol": sym, "name": f"{sym} Ltd", "sector": sector, "price": 100, "market_cap": 1e12,
            "pe": 25, "pb": 4, "roe": 0.15, "debt_to_equity": 0.5, "profit_margin": 0.12,
            "return_6m": 0.05, "return_1y": 0.10, "volatility_1y": 0.22, "beta_1y": 0.9}
    return base | kw


def test_score_stocks_orders_by_factors():
    universe = [
        _stock("GREAT", pe=12, pb=2, roe=0.30, debt_to_equity=0.1, profit_margin=0.25, return_6m=0.2, return_1y=0.35,
               volatility_1y=0.18, beta_1y=0.7),
        _stock("MEH"),
        _stock("POOR", pe=-5, pb=9, roe=-0.05, debt_to_equity=2.5, profit_margin=-0.1, return_6m=-0.2, return_1y=-0.3,
               volatility_1y=0.45, beta_1y=1.6),
    ]
    scored = score_stocks(universe, "moderate")
    assert [s["symbol"] for s in scored] == ["GREAT", "MEH", "POOR"]
    great, poor = scored[0], scored[-1]
    assert great["score"] == 100 and great["reasons"] and "NIFTY 50" in great["reasons"][0]
    assert poor["factors"]["value"] == 0 and any("loss-making" in c for c in poor["cautions"])
    assert not poor["eligible"]                                  # 45% volatility is too much for moderate


def test_risk_filter_and_sector_cap():
    assert passes_risk_filter(_stock("A", volatility_1y=0.24, beta_1y=0.95), "conservative")
    assert not passes_risk_filter(_stock("B", volatility_1y=0.30), "conservative")
    assert not passes_risk_filter(_stock("C", beta_1y=None), "conservative")   # unknown risk isn't "low risk"
    assert passes_risk_filter(_stock("C", beta_1y=None), "moderate")
    assert passes_risk_filter(_stock("D", volatility_1y=0.6, beta_1y=2), "aggressive")

    universe = [_stock(f"IT{i}", "IT", roe=0.3 - i / 100) for i in range(4)] + [_stock("BANK", "Financial Services")]
    picks = pick_stocks(score_stocks(universe, "aggressive"), n=10)
    assert sum(p["sector"] == "IT" for p in picks) == 2 and "BANK" in {p["symbol"] for p in picks}


# ---------- fund ranking ----------
def _fund(code, cat, name=None, **kw):
    base = {"scheme_code": code, "name": name or f"Fund {code} - Direct Plan - Growth", "fund_house": "AMC",
            "category": cat, "sharpe_3y": 1.0, "sortino_3y": 1.4, "cagr_3y": 0.15, "cagr_5y": 0.14,
            "rolling_1y_positive_pct": 0.9, "max_drawdown_3y": -0.15, "return_1y": 0.1, "volatility_3y": 0.14}
    return base | kw


def test_rank_funds_within_category():
    funds = [
        _fund(1, "Flexi Cap", sharpe_3y=1.5, sortino_3y=2.0, cagr_3y=0.2, cagr_5y=0.2, max_drawdown_3y=-0.1),
        _fund(2, "Flexi Cap", sharpe_3y=0.5, sortino_3y=0.8, cagr_3y=0.1, cagr_5y=None, max_drawdown_3y=-0.3),
        _fund(3, "Liquid", sharpe_3y=0.2),                         # alone in its category
    ]
    ranked = {f["scheme_code"]: f for f in rank_funds(funds)}
    assert ranked[1]["rank_in_category"] == 1 and ranked[1]["score"] > ranked[2]["score"]
    assert ranked[1]["short_name"] == "Fund 1" and "best in 2 Flexi Cap funds" in ranked[1]["reasons"][0]
    assert any("Limited history" in c for c in ranked[2]["cautions"])
    assert ranked[3]["score"] == 50 and ranked[3]["reasons"] == []


def test_index_funds_split_by_segment():
    nifty = {"category": "Index", "name": "UTI Nifty 50 Index Fund - Direct Plan - Growth"}
    mid = {"category": "Index", "name": "Motilal Oswal Nifty Midcap 150 Index Fund - Direct Plan - Growth"}
    assert in_sleeve(nifty, "core") and not in_sleeve(nifty, "mid")
    assert in_sleeve(mid, "mid") and not in_sleeve(mid, "core")
    ranked = rank_funds([_fund(1, "Large Cap"), _fund(2, "Mid Cap"), _fund(3, "Index", name=mid["name"])])
    assert {f["scheme_code"] for f in picks_for_sleeve(ranked, "mid")} == {2, 3}
    assert [f["scheme_code"] for f in picks_for_sleeve(ranked, "core")] == [1]


# ---------- FD pick ----------
def test_fd_pick():
    rows = load_fd_rows()
    assert fd_tenure_days(1) == 365 and fd_tenure_days(3) == 1095 and fd_tenure_days(12) == 1825

    young = pick_fd(rows, 3, 30, old_tax_regime=False)
    assert young["best"]["bank_type"] == "small_finance" and young["safest"]["bank_type"] != "small_finance"
    assert young["tax_saver"] is None and not young["senior"]
    assert young["best"]["rate"] >= max(a["rate"] for a in young["alternatives"])

    senior = pick_fd(rows, 3, 65, old_tax_regime=True)
    assert senior["senior"] and senior["best"]["rate"] == young["best"]["rate"] + 0.5
    assert senior["tax_saver"]["tenure_days"] == 1825 and senior["tax_saver"]["tax_saver"]


# ---------- planner ----------
def test_plan_goal_matches_future_value():
    fv = sip_future_value(10000, 10, 0.12)
    assert fv == pytest.approx(2323391, abs=1)
    p = plan_goal(fv, 10, 0.12)
    assert p["monthly_sip"] == 10000 and p["projected_value"] == pytest.approx(fv, abs=1)
    assert p["total_invested"] == 1200000 and p["gains"] > 0 and len(p["projection"]) == 10


def test_plan_goal_inflation_corpus_and_budget():
    base = plan_goal(1000000, 5, 0.10)
    inflated = plan_goal(1000000, 5, 0.10, inflation=0.06)
    assert inflated["target_amount"] == round(1000000 * 1.06 ** 5) and inflated["monthly_sip"] > base["monthly_sip"]
    funded = plan_goal(100000, 5, 0.10, current_corpus=100000)
    assert funded["monthly_sip"] == 0
    zero = plan_goal(120000, 1, 0.0)
    assert zero["monthly_sip"] == 10000

    tight = plan_goal(5000000, 10, 0.12, monthly_budget=10000)
    assert not tight["affordable"] and tight["months_at_budget"] > 120
    assert months_to_goal(1e12, 1, 0.01) is None


# ---------- API ----------
def _signup(email="r@example.com", **profile):
    r = client.post("/api/auth/signup", json={"email": email, "full_name": "R", "password": "password123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    body = {"age": 28, "monthly_income": 100000, "monthly_expenses": 50000, "current_savings": 500000,
            "dependents": 0, "horizon_years": 10, "goals": ["wealth_creation"], "risk_answers": ANSWERS} | profile
    if profile is not None:
        assert client.put("/api/profile", json=body, headers=h).status_code == 200
    return h


def _seed_market():
    with SessionLocal() as db:
        for i, sector in enumerate(["IT", "IT", "IT", "Energy", "Financial Services"]):
            db.add(Stock(**_stock(f"S{i}", sector, roe=0.1 + i / 50, volatility_1y=0.2 + i / 100)))
        for code, cat, name in [(1, "Index", "UTI Nifty 50 Index Fund - Direct Plan - Growth"),
                                (2, "Large Cap", None), (3, "Flexi Cap", None), (4, "Mid Cap", None),
                                (5, "Small Cap", None), (6, "Debt", None), (7, "Liquid", None), (8, "ELSS", None),
                                (9, "Hybrid", None)]:
            db.add(MutualFund(**{k: v for k, v in _fund(code, cat, name).items()}))
        for r in load_fd_rows():
            db.add(FdRate(**r))
        db.commit()


def test_recommend_requires_profile():
    r = client.post("/api/auth/signup", json={"email": "np@example.com", "full_name": "N", "password": "password123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/recommend", headers=h).status_code == 404
    assert client.get("/api/recommend").status_code == 401


def test_recommend_full_plan():
    _seed_market()
    h = _signup()
    data = client.get("/api/recommend", headers=h).json()
    assert data["investable"]["source"] == "profile" and data["investable"]["monthly"] == 50000
    assert data["emergency"]["ok"] and data["investable"]["lumpsum"] == 200000
    assert sum(data["allocation"]["weights"].values()) == pytest.approx(1)
    assert sum(item["monthly"] for item in data["plan"]) == pytest.approx(50000, abs=500)
    sleeves = {item["sleeve"]: item for item in data["plan"]}
    assert "stocks" in sleeves and sleeves["stocks"]["picks"]          # experience 3 -> some direct stocks
    assert sleeves["core"]["picks"][0]["category"] in ("Index", "Large Cap")
    assert sleeves["fd"]["picks"][0]["bank"] and data["fd"]["best"]["rate"] > 0
    assert "elss" not in sleeves and data["fd"]["tax_saver"] is None
    assert 0.06 < data["allocation"]["expected_return"] < 0.12
    assert data["stocks"]["universe"] == 5 and data["disclaimer"]

    old = client.get("/api/recommend?tax_regime=old", headers=h).json()
    assert any(i["sleeve"] == "elss" for i in old["plan"]) and old["fd"]["tax_saver"]


def test_recommend_emergency_first_and_expense_surplus():
    _seed_market()
    h = _signup(current_savings=0)
    today = date.today()
    prev = date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, 10)
    for kind, amount, cat in [("income", 90000, "salary"), ("expense", 60000, "rent"), ("expense", 10000, "investments")]:
        client.post("/api/transactions", headers=h, json={"kind": kind, "amount": amount, "category": cat,
                                                          "date": prev.isoformat(), "note": "", "payment_mode": "upi"})
    data = client.get("/api/recommend", headers=h).json()
    inv = data["investable"]
    assert inv["source"] == "expenses" and inv["monthly"] == 30000      # 90k - 60k; the SIP counts as saving
    em = data["emergency"]
    assert not em["ok"] and em["shortfall"] == 300000 and em["monthly_contribution"] == 15000
    assert em["picks"] and em["picks"][0]["category"] == "Liquid"
    assert inv["to_invest"] == 15000 and "Emergency fund first" in data["allocation"]["rationale"][0]


def test_recommend_without_market_data():
    h = _signup()
    data = client.get("/api/recommend", headers=h).json()
    assert data["data"] == {"stocks": 0, "funds": 0, "fds": 0} and data["fd"] is None
    assert all(item["picks"] == [] for item in data["plan"])


def test_stock_and_fund_rank_endpoints():
    _seed_market()
    h = _signup()
    s = client.get("/api/recommend/stocks?risk_category=conservative&limit=3", headers=h).json()
    assert s["risk_category"] == "conservative" and len(s["scored"]) == 5 and len(s["picks"]) <= 3
    f = client.get("/api/recommend/funds?category=Debt", headers=h).json()["items"]
    assert [x["scheme_code"] for x in f] == [6]


def test_sip_plan_endpoint():
    h = _signup()
    r = client.get("/api/recommend/sip-plan", headers=h,
                   params={"goal_amount": 2000000, "years": 2, "inflation": 0}).json()
    # A 2-year goal gets no equity, so the default return is the fixed-income blend.
    assert r["annual_return"] < 0.07 and r["monthly_budget"] == 50000 and r["affordable"] is False
    r = client.get("/api/recommend/sip-plan", headers=h,
                   params={"goal_amount": 1000000, "years": 10, "annual_return": 0.12, "inflation": 0}).json()
    assert r["annual_return"] == 0.12 and r["affordable"] and r["monthly_sip"] < 5000
    assert client.get("/api/recommend/sip-plan", headers=h, params={"goal_amount": -1, "years": 5}).status_code == 422


def test_plan_shown_for_after_emergency_fund():
    _seed_market()
    h = _signup(current_savings=250000, monthly_expenses=60000, monthly_income=120000)  # gap 110k <= 3 x 60k
    data = client.get("/api/recommend", headers=h).json()
    assert data["investable"]["to_invest"] == 0 and data["emergency"]["months_to_fill"] == 2
    assert data["plan_starts"] == "after_emergency"
    assert sum(i["monthly"] for i in data["plan"]) == pytest.approx(60000, abs=500)
