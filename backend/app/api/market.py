from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.market_data.fds import maturity_value
from app.market_data.funds import EQUITY_CATEGORIES
from app.models import DataRefresh, FdRate, MutualFund, PricePoint, Stock

router = APIRouter(prefix="/market", tags=["market"])

Range = Literal["1m", "6m", "1y", "3y", "5y"]
RANGE_DAYS = {"1m": 31, "6m": 183, "1y": 366, "3y": 3 * 366, "5y": 5 * 366}


def row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _sortable(model, sort: str):
    col = model.__table__.columns.get(sort)
    if col is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Cannot sort by '{sort}'")
    return col


def _history(db: Session, kind: str, code: str, rng: str) -> list[dict]:
    last = db.scalar(select(func.max(PricePoint.date)).where(PricePoint.kind == kind, PricePoint.code == code))
    if last is None:
        return []
    pts = db.execute(
        select(PricePoint.date, PricePoint.value)
        .where(PricePoint.kind == kind, PricePoint.code == code, PricePoint.date >= last - timedelta(days=RANGE_DAYS[rng]))
        .order_by(PricePoint.date)
    ).all()
    step = 1 if len(pts) <= 400 else len(pts) // 300 + 1   # keep charts light
    sampled = pts[::step]
    if sampled[-1] != pts[-1]:
        sampled.append(pts[-1])
    return [{"date": d.isoformat(), "value": v} for d, v in sampled]


@router.get("/status")
def market_status(db: Session = Depends(get_db)):
    def last_run(source):
        r = db.scalars(select(DataRefresh).where(DataRefresh.source == source, DataRefresh.status != "running")
                       .order_by(DataRefresh.id.desc()).limit(1)).first()
        return None if r is None else {"status": r.status, "finished_at": r.finished_at, "ok": r.ok_count, "failures": r.failures[:20]}

    return {
        "stocks": {"count": db.scalar(select(func.count()).select_from(Stock)), "last_refresh": last_run("stocks")},
        "funds": {"count": db.scalar(select(func.count()).select_from(MutualFund)), "last_refresh": last_run("funds")},
        "fds": {"count": db.scalar(select(func.count()).select_from(FdRate)), "as_of": db.scalar(select(func.max(FdRate.as_of))),
                "indicative": True},
    }


@router.get("/stocks")
def list_stocks(
    sector: str | None = None,
    q: str | None = Query(None, max_length=50),
    sort: str = "market_cap",
    order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
):
    col = _sortable(Stock, sort)
    stmt = select(Stock)
    if sector:
        stmt = stmt.where(Stock.sector == sector)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Stock.symbol.ilike(like) | Stock.name.ilike(like))
    stmt = stmt.order_by(col.is_(None), col.desc() if order == "desc" else col.asc())
    items = [row(s) for s in db.scalars(stmt)]
    sectors = sorted(x for x in db.scalars(select(Stock.sector).distinct()) if x)
    return {"items": items, "sectors": sectors}


@router.get("/stocks/{symbol}")
def stock_detail(symbol: str, range: Range = "1y", db: Session = Depends(get_db)):
    s = db.get(Stock, symbol.upper())
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    return {"stock": row(s), "history": _history(db, "stock", s.symbol, range),
            "benchmark": {"name": "NIFTY 50", "history": _history(db, "index", "NIFTY50", range)}}


@router.get("/funds")
def list_funds(
    category: str | None = None,
    kind: Literal["equity", "debt"] | None = None,
    sort: str = "cagr_3y",
    order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
):
    col = _sortable(MutualFund, sort)
    stmt = select(MutualFund)
    if category:
        stmt = stmt.where(MutualFund.category == category)
    if kind == "equity":
        stmt = stmt.where(MutualFund.category.in_(EQUITY_CATEGORIES))
    elif kind == "debt":
        stmt = stmt.where(MutualFund.category.not_in(EQUITY_CATEGORIES))
    stmt = stmt.order_by(col.is_(None), col.desc() if order == "desc" else col.asc())
    items = [row(f) for f in db.scalars(stmt)]
    categories = sorted(db.scalars(select(MutualFund.category).distinct()))
    return {"items": items, "categories": categories}


@router.get("/funds/{code}")
def fund_detail(code: int, range: Range = "3y", db: Session = Depends(get_db)):
    f = db.get(MutualFund, code)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fund not found")
    return {"fund": row(f), "history": _history(db, "mf", str(code), range),
            "benchmark": {"name": "NIFTY 50", "history": _history(db, "index", "NIFTY50", range)}}


@router.get("/fds")
def fd_rates(
    days: int = Query(365, ge=7, le=3650),
    senior: bool = False,
    tax_saver: bool = False,
    amount: float = Query(100000, gt=0, le=1e10),
    db: Session = Depends(get_db),
):
    stmt = select(FdRate).where(FdRate.min_days <= days, FdRate.max_days >= days, FdRate.tax_saver.is_(tax_saver))
    rows = list(db.scalars(stmt))
    items = []
    for r in rows:
        rate = r.senior_rate if senior else r.rate
        mv = maturity_value(amount, rate, days)
        items.append({**row(r), "applied_rate": rate, "maturity_value": round(mv, 2), "interest": round(mv - amount, 2)})
    items.sort(key=lambda x: -x["applied_rate"])
    as_of: date | None = rows[0].as_of if rows else None
    return {"days": days, "senior": senior, "tax_saver": tax_saver, "amount": amount, "as_of": as_of,
            "indicative": True, "items": items}
