"""Mutual funds from mfapi.in (free mirror of AMFI NAV data)."""
import re
from datetime import datetime, timedelta

import httpx
import pandas as pd

from app.services import metrics as m

BASE = "https://api.mfapi.in/mf"
_EXCLUDE = re.compile(r"idcw|dividend|bonus|segregated|regular|payout|reinvest", re.I)

# AMFI "scheme_category" -> app category, first match wins.
CATEGORY_RULES = [
    ("Index", ["index fund", "etf"]),
    ("ELSS", ["elss"]),
    ("Large Cap", ["large cap fund"]),
    ("Large & Mid Cap", ["large & mid cap"]),
    ("Flexi Cap", ["flexi cap"]),
    ("Multi Cap", ["multi cap"]),
    ("Mid Cap", ["mid cap fund"]),
    ("Small Cap", ["small cap fund"]),
    ("Hybrid", ["hybrid", "balanced advantage", "dynamic asset", "equity savings", "arbitrage"]),
    ("Liquid", ["liquid", "overnight", "money market"]),
    ("Debt", ["debt", "income", "gilt", "bond", "duration", "short term", "credit risk", "banking and psu"]),
]

EQUITY_CATEGORIES = {"Index", "ELSS", "Large Cap", "Large & Mid Cap", "Flexi Cap", "Multi Cap", "Mid Cap", "Small Cap"}


def normalize_category(raw: str | None) -> str:
    r = (raw or "").lower()
    for cat, keys in CATEGORY_RULES:
        if any(k in r for k in keys):
            return cat
    return "Other"


def pick_scheme(results: list[dict]) -> dict | None:
    """From search results, pick the Direct Plan Growth option (shortest clean name)."""
    good = [r for r in results
            if "direct" in r["schemeName"].lower() and "growth" in r["schemeName"].lower()
            and not _EXCLUDE.search(r["schemeName"])]
    return min(good, key=lambda r: len(r["schemeName"])) if good else None


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name.lower())).strip()


def find_candidates(all_schemes: list[dict], query: str) -> list[dict]:
    """Direct-Growth schemes whose name contains `query` as a whole phrase, shortest name first.

    Phrase (not bag-of-words) matching keeps "Large Cap Fund" from matching "Large & Mid Cap Fund"
    and "Nifty 50" from matching "Nifty 500".
    """
    phrase = re.compile(r"\b" + re.escape(_norm(query)) + r"\b")
    good = [r for r in all_schemes
            if phrase.search(_norm(r["schemeName"]))
            and "direct" in r["schemeName"].lower() and "growth" in r["schemeName"].lower()
            and not _EXCLUDE.search(r["schemeName"])]
    return sorted(good, key=lambda r: len(r["schemeName"]))


def fetch_all_schemes(client: httpx.Client) -> list[dict]:
    r = client.get(BASE)
    r.raise_for_status()
    return r.json()


def search(client: httpx.Client, query: str) -> list[dict]:
    r = client.get(f"{BASE}/search", params={"q": query})
    r.raise_for_status()
    return r.json()


def fetch_scheme(client: httpx.Client, code: int) -> dict:
    r = client.get(f"{BASE}/{code}")
    r.raise_for_status()
    data = r.json()
    if not data.get("data"):
        raise ValueError(f"no NAV data for scheme {code}")
    return data


def parse_navs(payload: dict) -> pd.Series:
    pts = [(datetime.strptime(p["date"], "%d-%m-%Y").date(), float(p["nav"])) for p in payload["data"] if p.get("nav")]
    return m.to_series(pts)


def build_fund_row(payload: dict, navs: pd.Series, risk_free: float = m.DEFAULT_RISK_FREE) -> dict:
    meta = payload["meta"]
    three_y = m.window(navs, 3 * 365)
    has_3y = (navs.index[-1] - navs.index[0]).days >= 3 * 365 - 7
    return {
        "scheme_code": int(meta["scheme_code"]),
        "name": meta["scheme_name"],
        "fund_house": meta.get("fund_house"),
        "category": normalize_category(meta.get("scheme_category")),
        "scheme_category": meta.get("scheme_category"),
        "nav": m.clean(float(navs.iloc[-1])),
        "nav_date": navs.index[-1].date(),
        "inception_date": navs.index[0].date(),
        "return_1y": m.clean(m.trailing_return(navs, 365)),
        "cagr_3y": m.clean(m.cagr(navs, 3)),
        "cagr_5y": m.clean(m.cagr(navs, 5)),
        "volatility_3y": m.clean(m.volatility(three_y)) if has_3y else None,
        "sharpe_3y": m.clean(m.sharpe(three_y, risk_free), 2) if has_3y else None,
        "sortino_3y": m.clean(m.sortino(three_y, risk_free), 2) if has_3y else None,
        "max_drawdown_3y": m.clean(m.max_drawdown(three_y)) if has_3y else None,
        "rolling_1y_positive_pct": m.clean(m.rolling_positive_share(navs)),
    }


def history_points(navs: pd.Series, years: int = 5) -> list[tuple]:
    start = navs.index[-1] - timedelta(days=365 * years)
    return [(ts.date(), round(float(v), 4)) for ts, v in navs.loc[start:].items()]
