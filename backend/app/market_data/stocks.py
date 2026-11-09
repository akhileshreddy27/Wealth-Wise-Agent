"""Stocks from Yahoo Finance via yfinance (NSE symbols get a .NS suffix)."""
import logging
from datetime import timedelta

import pandas as pd
import yfinance as yf

from app.services import metrics as m

log = logging.getLogger(__name__)


def yahoo_symbol(symbol: str) -> str:
    return symbol if symbol.startswith("^") else f"{symbol}.NS"


def fetch_closes(symbols: list[str], period: str = "5y") -> dict[str, pd.Series]:
    """Adjusted daily closes for many symbols in one request."""
    tickers = [yahoo_symbol(s) for s in symbols]
    df = yf.download(tickers, period=period, interval="1d", auto_adjust=True,
                     progress=False, group_by="ticker", threads=True)
    out: dict[str, pd.Series] = {}
    for sym, tk in zip(symbols, tickers):
        try:
            close = (df[tk]["Close"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]).dropna()
        except KeyError:
            continue
        if len(close):
            close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
            out[sym] = close.astype(float)
    return out


def fetch_info(symbol: str) -> dict:
    try:
        return yf.Ticker(yahoo_symbol(symbol)).info or {}
    except Exception as e:  # yfinance raises many kinds of errors on bad symbols / rate limits
        log.warning("info failed for %s: %s", symbol, e)
        return {}


def _pct_field(info: dict, key: str) -> float | None:
    """yfinance returns some ratios as percentages (dividendYield 1.9, debtToEquity 45.2)."""
    v = info.get(key)
    return None if v is None else float(v) / 100


def build_stock_row(symbol: str, info: dict, closes: pd.Series, index_closes: pd.Series | None,
                    risk_free: float = m.DEFAULT_RISK_FREE) -> dict:
    last_year = m.window(closes, 365)
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) > 1 else None
    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "price": m.clean(price, 2),
        "change_pct_1d": m.clean(price / prev - 1) if prev else None,
        "market_cap": info.get("marketCap"),
        "pe": m.clean(info.get("trailingPE"), 2),
        "pb": m.clean(info.get("priceToBook"), 2),
        "roe": m.clean(info.get("returnOnEquity")),
        "debt_to_equity": m.clean(_pct_field(info, "debtToEquity")),
        "dividend_yield": m.clean(_pct_field(info, "dividendYield")),
        "profit_margin": m.clean(info.get("profitMargins")),
        "revenue_growth": m.clean(info.get("revenueGrowth")),
        "earnings_growth": m.clean(info.get("earningsGrowth")),
        "return_1m": m.clean(m.trailing_return(closes, 30)),
        "return_6m": m.clean(m.trailing_return(closes, 182)),
        "return_1y": m.clean(m.trailing_return(closes, 365)),
        "cagr_3y": m.clean(m.cagr(closes, 3)),
        "cagr_5y": m.clean(m.cagr(closes, 5)),
        "volatility_1y": m.clean(m.volatility(last_year)),
        "max_drawdown_1y": m.clean(m.max_drawdown(last_year)),
        "sharpe_1y": m.clean(m.sharpe(last_year, risk_free), 2),
        "beta_1y": m.clean(m.beta(last_year, m.window(index_closes, 365)), 2) if index_closes is not None else None,
        "high_52w": m.clean(float(last_year.max()), 2),
        "low_52w": m.clean(float(last_year.min()), 2),
    }


def history_points(closes: pd.Series, years: int = 5) -> list[tuple]:
    start = closes.index[-1] - timedelta(days=365 * years)
    return [(ts.date(), round(float(v), 4)) for ts, v in closes.loc[start:].items()]
