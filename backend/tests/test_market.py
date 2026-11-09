import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.jobs import refresh
from app.main import app
from app.market_data import fds, funds, stocks
from app.services import metrics as m

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def series(values, start="2021-01-01", freq="D"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq), dtype=float)


def growth(rate_per_year, years, start="2020-01-01", noise=0.0, seed=0):
    days = int(365 * years) + 1
    rng = np.random.default_rng(seed)
    daily = (1 + rate_per_year) ** (1 / 365) - 1
    rets = daily + rng.normal(0, noise, days)
    rets[0] = 0
    return series(100 * np.cumprod(1 + rets), start)


# ---------- metrics ----------
def test_returns_and_cagr():
    s = growth(0.10, 5)
    assert m.trailing_return(s, 365) == pytest.approx(0.10, abs=0.002)
    assert m.cagr(s, 3) == pytest.approx(0.10, abs=0.002)
    assert m.cagr(s, 5) == pytest.approx(0.10, abs=0.002)
    assert m.cagr(s, 6) is None  # not enough history


def test_drawdown_vol_sharpe_beta():
    assert m.max_drawdown(series([100, 120, 90, 130])) == pytest.approx(-0.25)
    smooth = growth(0.12, 1)
    assert m.volatility(smooth) == pytest.approx(0, abs=1e-6)
    noisy = growth(0.12, 1, noise=0.01)
    assert 0.1 < m.volatility(noisy) < 0.25          # ~1% daily ≈ 16% annual
    assert m.sharpe(noisy) is not None

    bench = growth(0.10, 1, noise=0.01, seed=1)
    levered = series((1 + 2 * bench.pct_change().fillna(0)).cumprod().values * 100, bench.index[0])
    assert m.beta(levered, bench) == pytest.approx(2, abs=0.01)


def test_rolling_positive_share():
    assert m.rolling_positive_share(growth(0.10, 4)) == 1.0
    assert m.rolling_positive_share(growth(-0.10, 4)) == 0.0
    assert m.rolling_positive_share(growth(0.10, 1)) is None


# ---------- loaders ----------
def test_fund_category_and_pick():
    assert funds.normalize_category("Equity Scheme - Flexi Cap Fund") == "Flexi Cap"
    assert funds.normalize_category("Other Scheme - Index Funds") == "Index"
    assert funds.normalize_category("Equity Scheme - ELSS") == "ELSS"
    assert funds.normalize_category("Debt Scheme - Corporate Bond Fund") == "Debt"
    assert funds.normalize_category("Debt Scheme - Liquid Fund") == "Liquid"
    assert funds.normalize_category("Income/Debt Oriented Schemes - Short Term Fund") == "Debt"
    results = [
        {"schemeCode": 1, "schemeName": "X Fund - Regular Plan - Growth"},
        {"schemeCode": 2, "schemeName": "X Fund - Direct Plan - IDCW Payout"},
        {"schemeCode": 3, "schemeName": "X Fund - Direct Plan - Growth"},
    ]
    assert funds.pick_scheme(results)["schemeCode"] == 3
    assert funds.pick_scheme(results[:2]) is None


def test_build_fund_row():
    navs = growth(0.15, 4, noise=0.008)
    payload = {"meta": {"scheme_code": 9, "scheme_name": "Test Flexi - Direct - Growth", "fund_house": "T",
                        "scheme_category": "Equity Scheme - Flexi Cap Fund"},
               "data": [{"date": d.strftime("%d-%m-%Y"), "nav": str(v)} for d, v in navs.items()][::-1]}
    parsed = funds.parse_navs(payload)
    assert parsed.index.is_monotonic_increasing and len(parsed) == len(navs)
    row = funds.build_fund_row(payload, parsed)
    assert row["category"] == "Flexi Cap" and row["nav_date"] == navs.index[-1].date()
    assert row["cagr_3y"] == pytest.approx(0.15, abs=0.05)
    assert row["volatility_3y"] and row["sharpe_3y"] is not None and row["max_drawdown_3y"] < 0


def test_build_stock_row_converts_percent_fields():
    closes = growth(0.2, 2, noise=0.01)
    info = {"longName": "Test Ltd", "sector": "Technology", "dividendYield": 1.9, "debtToEquity": 45.0,
            "returnOnEquity": 0.21, "trailingPE": 25.123}
    r = stocks.build_stock_row("TEST", info, closes, closes)
    assert r["dividend_yield"] == 0.019 and r["debt_to_equity"] == 0.45 and r["pe"] == 25.12
    assert r["beta_1y"] == pytest.approx(1.0) and r["cagr_3y"] is None and r["return_1y"] is not None


def test_fd_rows_and_maturity():
    rows = fds.load_fd_rows()
    assert all(r["min_days"] <= r["max_days"] for r in rows)
    assert any(r["tax_saver"] for r in rows)
    assert fds.maturity_value(100000, 7.0, 365) == pytest.approx(107186, abs=1)


# ---------- refresh job (network mocked) ----------
def test_refresh_stocks_records_failures(monkeypatch):
    closes = {"AAA": growth(0.1, 2, noise=0.01), "^NSEI": growth(0.08, 2, noise=0.008, seed=2)}
    monkeypatch.setattr(stocks, "fetch_closes", lambda syms, period="5y": closes)
    monkeypatch.setattr(stocks, "fetch_info", lambda sym: {"longName": f"{sym} Ltd", "sector": "Energy"})
    with SessionLocal() as db:
        run = refresh.refresh_stocks(db, ["AAA", "MISSING"], info_delay=0)
    assert run.status == "partial" and run.ok_count == 1 and "MISSING" in run.failures[0]

    st = client.get("/api/market/status").json()
    assert st["stocks"]["count"] == 1 and st["stocks"]["last_refresh"]["status"] == "partial"
    d = client.get("/api/market/stocks/aaa?range=1y").json()
    assert d["stock"]["name"] == "AAA Ltd" and len(d["history"]) > 100 and d["benchmark"]["history"]
    assert len(client.get("/api/market/stocks/AAA?range=5y").json()["history"]) <= 301

    # A symbol that leaves the universe is pruned on the next run
    with SessionLocal() as db:
        refresh.refresh_stocks(db, ["BBB_NEW", "AAA"][1:], info_delay=0)
        closes["CCC"] = closes["AAA"]
        refresh.refresh_stocks(db, ["CCC"], info_delay=0)
    assert [s["symbol"] for s in client.get("/api/market/stocks").json()["items"]] == ["CCC"]


# ---------- API ----------
def _seed_funds():
    from app.models import MutualFund
    with SessionLocal() as db:
        for code, cat, c3 in [(1, "Flexi Cap", 0.18), (2, "Debt", 0.07), (3, "Flexi Cap", None), (4, "Index", 0.14)]:
            db.add(MutualFund(scheme_code=code, name=f"F{code}", category=cat, cagr_3y=c3))
        db.commit()


def test_funds_list_sort_filter():
    _seed_funds()
    items = client.get("/api/market/funds").json()["items"]
    assert [f["scheme_code"] for f in items] == [1, 4, 2, 3]  # None sorts last
    assert [f["scheme_code"] for f in client.get("/api/market/funds?kind=equity").json()["items"]] == [1, 4, 3]
    assert [f["scheme_code"] for f in client.get("/api/market/funds?category=Debt").json()["items"]] == [2]
    assert client.get("/api/market/funds?sort=hacked").status_code == 422
    assert client.get("/api/market/funds/999").status_code == 404


def test_fd_endpoint():
    with SessionLocal() as db:
        refresh.load_fd_rates(db)
    r = client.get("/api/market/fds?days=400&amount=100000").json()
    rates = [i["applied_rate"] for i in r["items"]]
    assert rates == sorted(rates, reverse=True) and r["indicative"] is True
    assert all(i["min_days"] <= 400 <= i["max_days"] for i in r["items"])
    senior = client.get("/api/market/fds?days=400&senior=true").json()["items"]
    assert senior[0]["applied_rate"] >= rates[0]
    ts = client.get("/api/market/fds?days=1825&tax_saver=true").json()["items"]
    assert ts and all(i["tax_saver"] for i in ts)


def test_find_candidates_matches_whole_phrase():
    schemes = [
        {"schemeCode": 1, "schemeName": "HDFC Ultra Short to Short Term Fund - Direct Plan - Growth Option"},
        {"schemeCode": 2, "schemeName": "HDFC Short Term Fund - Direct Plan - Growth Option"},
        {"schemeCode": 3, "schemeName": "HDFC Short Term Fund - Regular Plan - Growth Option"},
        {"schemeCode": 4, "schemeName": "Kotak Flexi Cap Fund - Direct Plan - IDCW"},
        {"schemeCode": 5, "schemeName": "Kotak Flexi Cap Fund - Direct Plan - Growth"},
    ]
    schemes += [{"schemeCode": 6, "schemeName": "X Large & Mid Cap Fund - Direct Plan - Growth"},
                {"schemeCode": 7, "schemeName": "X Nifty 500 Index Fund - Direct Plan - Growth"}]
    assert [c["schemeCode"] for c in funds.find_candidates(schemes, "HDFC Short Term Fund")] == [2]
    assert funds.find_candidates(schemes, "X Large Cap Fund") == []
    assert funds.find_candidates(schemes, "X Nifty 50 Index Fund") == []
    assert [c["schemeCode"] for c in funds.find_candidates(schemes, "Kotak Flexi Cap Fund")] == [5]
    assert funds.find_candidates(schemes, "SBI Gilt") == []
