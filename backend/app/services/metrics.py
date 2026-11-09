"""Return / risk metrics on a daily price or NAV series.

All functions take a pandas Series indexed by date (ascending) and return plain
floats (fractions: 0.12 = 12%) or None when there isn't enough history.
"""
from datetime import timedelta

import numpy as np
import pandas as pd

TRADING_DAYS = 252
DEFAULT_RISK_FREE = 0.065  # ~India 91-day T-bill yield; override via settings


def _value_on_or_before(s: pd.Series, when) -> float | None:
    sub = s.loc[:when]
    return float(sub.iloc[-1]) if len(sub) else None


def trailing_return(s: pd.Series, days: int) -> float | None:
    """Simple return over the last `days` calendar days."""
    if len(s) < 2:
        return None
    end_date = s.index[-1]
    start_date = end_date - timedelta(days=days)
    if s.index[0] > start_date + timedelta(days=7):   # history doesn't reach back far enough
        return None
    start = _value_on_or_before(s, start_date) or float(s.iloc[0])
    return float(s.iloc[-1]) / start - 1 if start else None


def cagr(s: pd.Series, years: float) -> float | None:
    r = trailing_return(s, int(round(years * 365)))
    return None if r is None or r <= -1 else (1 + r) ** (1 / years) - 1


def window(s: pd.Series, days: int) -> pd.Series:
    return s.loc[s.index[-1] - timedelta(days=days):] if len(s) else s


def daily_returns(s: pd.Series) -> pd.Series:
    return s.pct_change().dropna()


def volatility(s: pd.Series) -> float | None:
    r = daily_returns(s)
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(r) >= 20 else None


def annualised_return(s: pd.Series) -> float | None:
    if len(s) < 20:
        return None
    years = (s.index[-1] - s.index[0]).days / 365
    if years <= 0 or s.iloc[0] <= 0:
        return None
    return float((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1)


def sharpe(s: pd.Series, risk_free: float = DEFAULT_RISK_FREE) -> float | None:
    ret, vol = annualised_return(s), volatility(s)
    return (ret - risk_free) / vol if ret is not None and vol else None


def sortino(s: pd.Series, risk_free: float = DEFAULT_RISK_FREE) -> float | None:
    ret = annualised_return(s)
    r = daily_returns(s)
    downside = r[r < 0]
    if ret is None or len(downside) < 5:
        return None
    dd = float(np.sqrt((downside ** 2).mean()) * np.sqrt(TRADING_DAYS))
    return (ret - risk_free) / dd if dd else None


def max_drawdown(s: pd.Series) -> float | None:
    """Most negative peak-to-trough fall, e.g. -0.23."""
    if len(s) < 2:
        return None
    return float((s / s.cummax() - 1).min())


def beta(s: pd.Series, benchmark: pd.Series) -> float | None:
    joined = pd.concat([daily_returns(s), daily_returns(benchmark)], axis=1, join="inner").dropna()
    if len(joined) < 60:
        return None
    var = joined.iloc[:, 1].var()
    return float(joined.iloc[:, 0].cov(joined.iloc[:, 1]) / var) if var else None


def rolling_positive_share(s: pd.Series, window_days: int = 365, lookback_days: int = 3 * 365) -> float | None:
    """Share of rolling `window_days` periods (within the lookback) that ended with a gain."""
    s = window(s, lookback_days + window_days)
    if len(s) < 2 or (s.index[-1] - s.index[0]).days < window_days + 180:
        return None
    daily = s.asfreq("D").ffill()
    rolled = (daily / daily.shift(window_days) - 1).dropna()
    rolled = rolled.loc[rolled.index[-1] - timedelta(days=lookback_days):]
    return float((rolled > 0).mean()) if len(rolled) else None


def to_series(points: list[tuple]) -> pd.Series:
    """[(date, value), ...] in any order -> ascending Series with DatetimeIndex."""
    if not points:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in points}).sort_index()
    return s[s > 0]


def clean(x: float | None, digits: int = 4) -> float | None:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return None
    return round(float(x), digits)
