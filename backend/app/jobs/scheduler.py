"""In-process scheduler. Enable with ENABLE_SCHEDULER=true (one API worker only).
In production, prefer a separate cron / worker running `python -m app.jobs.refresh`."""
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.db import SessionLocal
from app.jobs.refresh import run_job
from app.models import MutualFund, Stock

log = logging.getLogger(__name__)
TZ = "Asia/Kolkata"


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone=TZ, job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600})
    # NSE closes 15:30 IST; AMFI publishes NAVs by ~23:00 IST.
    sched.add_job(run_job, "cron", args=["stocks"], day_of_week="mon-fri", hour=16, minute=30, id="stocks")
    sched.add_job(run_job, "cron", args=["funds"], hour=23, minute=30, id="funds")

    with SessionLocal() as db:
        if db.scalar(select(Stock.symbol).limit(1)) is None:
            sched.add_job(run_job, args=["stocks"], next_run_time=datetime.now(), id="stocks-initial")
        if db.scalar(select(MutualFund.scheme_code).limit(1)) is None:
            sched.add_job(run_job, args=["funds"], next_run_time=datetime.now(), id="funds-initial")
    sched.start()
    log.info("market-data scheduler started")
    return sched
