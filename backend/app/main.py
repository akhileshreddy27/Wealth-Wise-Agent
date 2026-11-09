import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers tables)
from app.api import agent, auth, expenses, market, profile, recommend, transactions
from app.core.config import settings
from app.db import Base, SessionLocal, engine
from app.jobs.refresh import ensure_seeded

# Phase 1: create tables directly. Switch to Alembic migrations once the schema settles.
Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        ensure_seeded(db)  # FD rates come from a bundled file, so load them on first start
    sched = None
    if settings.enable_scheduler:
        from app.jobs.scheduler import start_scheduler
        sched = start_scheduler()
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="Wealth Wise Agent API", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(recommend.router, prefix="/api")
app.include_router(agent.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
