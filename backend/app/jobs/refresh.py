"""Market data refresh. Run manually:

    python -m app.jobs.refresh all        # or: stocks | funds | fds
"""
import argparse
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (register tables)
from app.core.config import settings
from app.db import Base, SessionLocal, engine
from app.market_data import fds, funds, stocks
from app.market_data.universe import FUND_QUERIES, NIFTY50, NIFTY_INDEX
from app.models import DataRefresh, FdRate, MutualFund, PricePoint, Stock

log = logging.getLogger("refresh")


def _save_history(db: Session, kind: str, code: str, points: list[tuple]) -> None:
    db.execute(delete(PricePoint).where(PricePoint.kind == kind, PricePoint.code == code))
    if points:
        db.execute(insert(PricePoint), [{"kind": kind, "code": code, "date": d, "value": v} for d, v in points])


def _prune(db: Session, model, key_col, kind: str, keep_codes: set[str], keep_keys) -> None:
    """Drop instruments that left the universe (and their price history)."""
    db.execute(delete(model).where(key_col.not_in(list(keep_keys))))
    db.execute(delete(PricePoint).where(PricePoint.kind == kind, PricePoint.code.not_in(list(keep_codes))))
    db.commit()


def _start(db: Session, source: str) -> DataRefresh:
    run = DataRefresh(source=source, status="running", failures=[])
    db.add(run)
    db.commit()
    return run


def _finish(db: Session, run: DataRefresh, ok: int, failures: list[str]) -> DataRefresh:
    run.ok_count, run.failures = ok, failures
    run.status = "ok" if not failures else ("partial" if ok else "failed")
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    log.info("%s refresh: %s (%d ok, %d failed)", run.source, run.status, ok, len(failures))
    return run


def refresh_stocks(db: Session, symbols: list[str] = NIFTY50, info_delay: float = 0.3) -> DataRefresh:
    run = _start(db, "stocks")
    ok, failures = 0, []
    try:
        closes = stocks.fetch_closes(symbols + [NIFTY_INDEX])
    except Exception as e:
        return _finish(db, run, 0, [f"price download failed: {e}"])

    index = closes.get(NIFTY_INDEX)
    if index is not None:
        _save_history(db, "index", "NIFTY50", stocks.history_points(index))
        db.commit()

    for sym in symbols:
        try:
            series = closes.get(sym)
            if series is None or len(series) < 30:
                raise ValueError("no price history (symbol may have changed)")
            info = stocks.fetch_info(sym)
            row = stocks.build_stock_row(sym, info, series, index, settings.risk_free_rate)
            db.merge(Stock(**row))
            _save_history(db, "stock", sym, stocks.history_points(series))
            db.commit()
            ok += 1
            time.sleep(info_delay)
        except Exception as e:
            db.rollback()
            failures.append(f"{sym}: {e}")
    if ok:
        _prune(db, Stock, Stock.symbol, "stock", set(symbols), symbols)
    return _finish(db, run, ok, failures)


def refresh_funds(db: Session, queries: list[str] = FUND_QUERIES, max_stale_days: int = 30) -> DataRefresh:
    run = _start(db, "funds")
    ok, failures, seen = 0, [], set()
    with httpx.Client(timeout=60, headers={"User-Agent": "wealth-wise/0.1"}) as client:
        try:
            all_schemes = funds.fetch_all_schemes(client)
        except Exception as e:
            return _finish(db, run, 0, [f"scheme list download failed: {e}"])

        for q in queries:
            try:
                candidates = [c for c in funds.find_candidates(all_schemes, q) if int(c["schemeCode"]) not in seen]
                if not candidates:
                    raise ValueError("no Direct-Growth scheme matches this name")
                for cand in candidates[:3]:  # closed / merged schemes stop publishing NAVs: try the next match
                    code = int(cand["schemeCode"])
                    payload = funds.fetch_scheme(client, code)
                    navs = funds.parse_navs(payload)
                    if len(navs) >= 30 and (datetime.now() - navs.index[-1].to_pydatetime()).days <= max_stale_days:
                        break
                else:
                    raise ValueError("matching schemes have no recent NAVs")
                seen.add(code)
                db.merge(MutualFund(**funds.build_fund_row(payload, navs, settings.risk_free_rate)))
                _save_history(db, "mf", str(code), funds.history_points(navs))
                db.commit()
                ok += 1
            except Exception as e:
                db.rollback()
                failures.append(f"{q}: {e}")
    if seen:
        _prune(db, MutualFund, MutualFund.scheme_code, "mf", {str(c) for c in seen}, seen)
    return _finish(db, run, ok, failures)


def load_fd_rates(db: Session) -> DataRefresh:
    run = _start(db, "fds")
    try:
        rows = fds.load_fd_rows()
    except Exception as e:
        return _finish(db, run, 0, [str(e)])
    db.execute(delete(FdRate))
    db.execute(insert(FdRate), rows)
    db.commit()
    return _finish(db, run, len(rows), [])


def ensure_seeded(db: Session) -> None:
    if db.scalar(select(FdRate.id).limit(1)) is None:
        load_fd_rates(db)


JOBS = {"stocks": refresh_stocks, "funds": refresh_funds, "fds": load_fd_rates}


def run_job(name: str) -> None:
    with SessionLocal() as db:
        JOBS[name](db)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh market data")
    parser.add_argument("what", choices=[*JOBS, "all"], nargs="?", default="all")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Base.metadata.create_all(bind=engine)
    for name in (JOBS if args.what == "all" else [args.what]):
        with SessionLocal() as db:
            run = JOBS[name](db)
            for f in run.failures:
                print(f"  ✗ {f}")


if __name__ == "__main__":
    main()
