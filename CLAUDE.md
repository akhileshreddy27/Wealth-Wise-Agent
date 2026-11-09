# Wealth Wise Agent: notes for Claude

AI-powered personal finance assistant for Indian users. It gives stock, mutual fund and FD recommendations, has a RAG chatbot with
learning modules, and includes an expense tracker. It's a resume project, so keep the code clean and explainable. The app is
educational, not SEBI-registered advice, and that disclaimer stays visible.

## Stack
- **Backend:** FastAPI, SQLAlchemy 2 and SQLite (`backend/wealthwise.db`; Postgres via `DATABASE_URL`), JWT auth, pytest.
- **Frontend:** React 19, Vite, TypeScript, Tailwind v4, React Router and Recharts. Dev server on :5173, proxying `/api` to :8000.
- **Market data:** yfinance (NSE, `.NS` suffix) and mfapi.in (AMFI NAVs). FD rates come from `backend/app/market_data/fd_rates.json`.

## Run
```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
cd backend && .venv/bin/pytest -q                     # all tests, offline (network is mocked)
cd backend && .venv/bin/python -m app.jobs.refresh all # load / refresh market data
```
First-time setup is in README.md. `.env` isn't committed: copy `.env.example` and set `JWT_SECRET`.

## Status (as of 2026-11-09)
- [x] **Phase 1:** auth, financial profile, risk score 1–10 (`services/risk.py`: questionnaire tolerance, capped by capacity).
- [x] **Phase 2:** expense tracker: transactions CRUD, CSV import with keyword auto-categorise, budgets, 50/30/20 check,
      recurring-payment and spike detection, savings insights (`services/expenses.py`).
- [x] **Phase 3:** market data: 50 NIFTY stocks, about 29 Direct-Growth funds and FD rates. Metrics are in `services/metrics.py`
      (CAGR, volatility, Sharpe, Sortino, max drawdown, beta, rolling consistency). Daily APScheduler refresh. Markets page.
- [x] **Phase 4:** recommendation engine, deterministic and with no LLM: `services/allocation.py` (allocation, emergency fund,
      SIP split into sleeves), `stock_scoring.py`, `fund_ranking.py`, `fd_pick.py`, `planner.py`, all wired up in `recommend.py`.
      `/api/recommend` (+ `/stocks`, `/funds`, `/sip-plan`), Recommendations page. Logic is documented in the README.
- [ ] **Phase 5:** LangGraph agents that explain and combine the Phase 4 outputs. Agents must call tools for every number
      and never invent figures. The keyword auto-categoriser in `services/categories.py` can get an LLM fallback.
- [ ] **Phase 6:** RAG chatbot (ChromaDB, citations, tools for live prices and the user's own data) and learning modules with videos.
- [ ] **Phase 7:** Docker Compose, deploy (Vercel + Render/Railway + Neon/Supabase), README screenshots, demo video.

## Conventions and gotchas
- Ratios are stored as fractions (0.12 = 12%). yfinance returns `dividendYield` and `debtToEquity` ×100; `_pct_field` converts them.
- Money is formatted the Indian way (₹2,29,737; market cap as ₹17.92L Cr): `inr()` in Python, and `inr`, `mcap` and `inrCompact` in `lib/api.ts`.
- SIPs and investments count as savings, not spending, in expense analytics.
- Fund names in `market_data/universe.py` are matched as whole phrases against mfapi's full scheme list. AMCs rename
  schemes, so check the refresh log for funds that no longer match.
- FD rates are indicative (`as_of` 2025-10-01) and must be updated by hand from bank websites. The UI says so.
- SQLite drops timezone info, so timestamps are UTC (`utcDate()` on the frontend).
- Schema changes: tables are created with `create_all`, so a new column on an existing table needs the DB deleted and data
  reloaded, or Alembic, which isn't set up yet. Consider adding Alembic before Phase 4 changes existing tables.
- Charts use the fixed palette `--series-1/2/3` in `index.css`, one y-axis, with gains/losses shown by ▲/▼ as well as colour.
- Demo data: import `data/sample_statement.csv` (6 months) on the Expenses page.
