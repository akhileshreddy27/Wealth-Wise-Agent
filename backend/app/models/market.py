from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Stock(Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)   # NSE symbol without .NS
    name: Mapped[str] = mapped_column(String(160))
    sector: Mapped[str | None] = mapped_column(String(60))
    industry: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float | None] = mapped_column(Float)
    change_pct_1d: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    # Fundamentals (ratios as fractions: 0.18 = 18%)
    pe: Mapped[float | None] = mapped_column(Float)
    pb: Mapped[float | None] = mapped_column(Float)
    roe: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)     # 0.5 = debt is half of equity
    dividend_yield: Mapped[float | None] = mapped_column(Float)
    profit_margin: Mapped[float | None] = mapped_column(Float)
    revenue_growth: Mapped[float | None] = mapped_column(Float)
    earnings_growth: Mapped[float | None] = mapped_column(Float)
    # Price-derived metrics
    return_1m: Mapped[float | None] = mapped_column(Float)
    return_6m: Mapped[float | None] = mapped_column(Float)
    return_1y: Mapped[float | None] = mapped_column(Float)
    cagr_3y: Mapped[float | None] = mapped_column(Float)
    cagr_5y: Mapped[float | None] = mapped_column(Float)
    volatility_1y: Mapped[float | None] = mapped_column(Float)
    max_drawdown_1y: Mapped[float | None] = mapped_column(Float)
    sharpe_1y: Mapped[float | None] = mapped_column(Float)
    beta_1y: Mapped[float | None] = mapped_column(Float)
    high_52w: Mapped[float | None] = mapped_column(Float)
    low_52w: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MutualFund(Base):
    __tablename__ = "mutual_funds"

    scheme_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    fund_house: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(30))                 # normalised: Large Cap, Flexi Cap, ...
    scheme_category: Mapped[str | None] = mapped_column(String(120))  # raw AMFI category
    nav: Mapped[float | None] = mapped_column(Float)
    nav_date: Mapped[date | None] = mapped_column(Date)
    inception_date: Mapped[date | None] = mapped_column(Date)
    return_1y: Mapped[float | None] = mapped_column(Float)
    cagr_3y: Mapped[float | None] = mapped_column(Float)
    cagr_5y: Mapped[float | None] = mapped_column(Float)
    volatility_3y: Mapped[float | None] = mapped_column(Float)
    sharpe_3y: Mapped[float | None] = mapped_column(Float)
    sortino_3y: Mapped[float | None] = mapped_column(Float)
    max_drawdown_3y: Mapped[float | None] = mapped_column(Float)
    rolling_1y_positive_pct: Mapped[float | None] = mapped_column(Float)  # share of 1y windows (last 3y) with a gain
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PricePoint(Base):
    """Daily close (stocks / index) or NAV (funds). kind: stock | mf | index."""
    __tablename__ = "price_points"

    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Float)


class FdRate(Base):
    __tablename__ = "fd_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank: Mapped[str] = mapped_column(String(80))
    bank_type: Mapped[str] = mapped_column(String(20))   # public | private | small_finance | government
    min_days: Mapped[int] = mapped_column(Integer)
    max_days: Mapped[int] = mapped_column(Integer)
    rate: Mapped[float] = mapped_column(Float)            # % p.a., general
    senior_rate: Mapped[float] = mapped_column(Float)     # % p.a., senior citizens
    tax_saver: Mapped[bool] = mapped_column(Boolean, default=False)
    as_of: Mapped[date] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(String(255))


class DataRefresh(Base):
    __tablename__ = "data_refreshes"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20))       # stocks | funds | fds
    status: Mapped[str] = mapped_column(String(10))       # running | ok | partial | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ok_count: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[list] = mapped_column(JSON, default=list)
