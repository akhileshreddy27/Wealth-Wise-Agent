"""Multi-factor stock scoring within the NIFTY 50 universe.

Four factors, each the average percentile of its metrics within the universe:
  value     low P/E, low P/B
  quality   high ROE, low debt-to-equity, high profit margin
  momentum  high 6-month and 1-year return
  low_vol   low 1-year volatility, low beta

Factor weights depend on the risk category (conservative users lean on quality and low
volatility; aggressive users on momentum). A risk filter removes stocks that are too volatile
for the user before ranking, and picks are capped at two per sector for diversification.
"""
from collections import Counter

from app.services.ranking import NEUTRAL, bottom_label, percentile_table, top_label

FACTORS: dict[str, list[tuple[str, bool]]] = {
    "value":    [("pe", False), ("pb", False)],
    "quality":  [("roe", True), ("debt_to_equity", False), ("profit_margin", True)],
    "momentum": [("return_6m", True), ("return_1y", True)],
    "low_vol":  [("volatility_1y", False), ("beta_1y", False)],
}

WEIGHTS = {
    "conservative": {"value": 0.25, "quality": 0.35, "momentum": 0.10, "low_vol": 0.30},
    "moderate":     {"value": 0.25, "quality": 0.30, "momentum": 0.25, "low_vol": 0.20},
    "aggressive":   {"value": 0.20, "quality": 0.25, "momentum": 0.40, "low_vol": 0.15},
}

# (max 1Y volatility, max beta, allow missing risk data)
RISK_FILTER = {
    "conservative": (0.25, 1.0, False),
    "moderate":     (0.35, 1.3, True),
    "aggressive":   (None, None, True),
}

METRIC_LABEL = {
    "pe": "P/E", "pb": "P/B", "roe": "ROE", "debt_to_equity": "Debt/equity", "profit_margin": "Net margin",
    "return_6m": "6M return", "return_1y": "1Y return", "volatility_1y": "Volatility", "beta_1y": "Beta",
}
_PCT_METRICS = {"roe", "profit_margin", "return_6m", "return_1y", "volatility_1y"}  # D/E reads as a ratio


def _get(stock: dict, key: str) -> float | None:
    v = stock.get(key)
    if key == "pe" and v is not None and v <= 0:
        return None  # negative P/E means losses; scored as worst value below, not as neutral
    return v


def _fmt(key: str, v: float) -> str:
    return f"{v * 100:.1f}%" if key in _PCT_METRICS else f"{v:.2f}"


def passes_risk_filter(stock, risk_category: str) -> bool:
    max_vol, max_beta, allow_missing = RISK_FILTER[risk_category]
    for value, limit in ((_get(stock, "volatility_1y"), max_vol), (_get(stock, "beta_1y"), max_beta)):
        if limit is None:
            continue
        if value is None:
            if not allow_missing:
                return False
        elif value > limit:
            return False
    return True


def score_stocks(stocks: list[dict], risk_category: str) -> list[dict]:
    """Score every stock (percentiles are within the whole universe), best first."""
    weights = WEIGHTS[risk_category]
    metrics = {m: ((lambda s, m=m: _get(s, m)), hi) for f in FACTORS.values() for m, hi in f}
    table = percentile_table(stocks, metrics)

    out = []
    for s, pcts in zip(stocks, table):
        loss_making = s.get("pe") is not None and s["pe"] <= 0
        if loss_making:
            pcts["pe"] = 0.0

        factors = {}
        for f, ms in FACTORS.items():
            got = [pcts[m] for m, _ in ms if pcts[m] is not None]
            factors[f] = sum(got) / len(got) if got else NEUTRAL
        score = sum(weights[f] * factors[f] for f in FACTORS)

        # Explain the score with the stock's strongest and weakest metrics.
        ranked = sorted(((p, m) for m, p in pcts.items() if p is not None and _get(s, m) is not None), reverse=True)
        reasons = [f"{METRIC_LABEL[m]} {_fmt(m, _get(s, m))} ({top_label(p, 'NIFTY 50')})"
                   for p, m in ranked[:2] if p >= 0.7]
        cautions = [f"{METRIC_LABEL[m]} {_fmt(m, _get(s, m))} ({bottom_label(p, 'NIFTY 50')})"
                    for p, m in ranked[-1:] if p <= 0.2]
        if loss_making:
            cautions.append("Currently loss-making (negative P/E)")

        out.append({
            "symbol": s["symbol"], "name": s["name"], "sector": s.get("sector"), "price": s.get("price"),
            "market_cap": s.get("market_cap"),
            "metrics": {m: s.get(m) for m in METRIC_LABEL},
            "score": round(score * 100, 1),
            "factors": {f: round(v * 100) for f, v in factors.items()},
            "eligible": passes_risk_filter(s, risk_category),
            "reasons": reasons,
            "cautions": cautions,
        })
    out.sort(key=lambda r: -r["score"])
    return out


def pick_stocks(scored: list[dict], n: int = 10, max_per_sector: int = 2) -> list[dict]:
    """Top `n` eligible stocks, at most `max_per_sector` from any one sector."""
    picks, per_sector = [], Counter()
    for r in scored:
        if not r["eligible"]:
            continue
        sector = r["sector"] or "Unknown"
        if per_sector[sector] >= max_per_sector:
            continue
        per_sector[sector] += 1
        picks.append(r)
        if len(picks) == n:
            break
    return picks
