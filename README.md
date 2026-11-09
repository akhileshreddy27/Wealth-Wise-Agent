# Wealth Wise Agent

AI-powered personal finance assistant: personalised stock / mutual fund / FD recommendations,
a RAG chatbot with learning modules, and an expense tracker.

> Educational project. Not SEBI-registered investment advice.

## Stack
- **Backend:** FastAPI, SQLAlchemy 2, SQLite (swap to Postgres via `DATABASE_URL`), JWT auth
- **Frontend:** React 19 + Vite + TypeScript + Tailwind v4, React Router

## Run locally

```bash
# backend (http://localhost:8000, docs at /docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # then set JWT_SECRET
.venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
# frontend (http://localhost:5173, proxies /api to :8000)
cd frontend
npm install
npm run dev
```

```bash
# load market data (first time takes ~2 min; afterwards the scheduler refreshes it daily)
cd backend && .venv/bin/python -m app.jobs.refresh all     # or: stocks | funds | fds
```

```bash
# tests
cd backend && .venv/bin/pytest -q
```

## Layout
```
backend/app/
  api/        auth.py, profile.py, deps.py (current-user dependency)
  core/       config.py, security.py (bcrypt + JWT)
  models/     User, FinancialProfile
  schemas/    Pydantic request/response models
  services/   risk.py        questionnaire + risk tolerance x capacity scoring
              categories.py  categories, 50/30/20 buckets, keyword auto-categoriser
              csv_import.py  bank-statement CSV parser (signed amount or debit/credit)
              expenses.py    monthly summary, recurring/spike detection, savings insights
  market_data/ universe.py (NIFTY 50 + curated funds), stocks.py (yfinance), funds.py (mfapi.in),
              fds.py + fd_rates.json (indicative FD rates, edit to update)
  services/metrics.py  CAGR, volatility, Sharpe, Sortino, max drawdown, beta, rolling-return consistency
  jobs/       refresh.py (CLI + refresh log), scheduler.py (APScheduler, IST)
  agents/     (Phase 5)
  rag/        (Phase 6)
frontend/src/
  pages/      AuthPage, Onboarding (3-step), Dashboard, Expenses
  components/expenses/  charts, insights, budgets, transaction form, CSV import
  context/    AuthContext
  lib/api.ts  axios client + shared types
```

## API (so far)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/signup` | returns JWT |
| POST | `/api/auth/login` | returns JWT |
| GET | `/api/auth/me` | current user + `has_profile` |
| GET | `/api/profile/questionnaire` | risk questions |
| GET/PUT | `/api/profile` | read / upsert profile; computes risk score + snapshot |
| GET/POST | `/api/transactions` | list (`?month=YYYY-MM&kind=&category=`) / create (category auto-detected if omitted) |
| PUT/DELETE | `/api/transactions/{id}` | edit / delete |
| POST | `/api/transactions/import` | CSV upload, auto-categorised, duplicates skipped |
| GET | `/api/transactions/categories` | expense + income categories |
| GET/PUT | `/api/budgets` | monthly budget per category (limit 0 removes) |
| GET | `/api/expenses/summary?month=` | totals, categories vs budget, 50/30/20 buckets, 6-month trend |
| GET | `/api/expenses/insights?month=` | over-budget, 50/30/20, subscriptions, spending spikes, SIP-value tips |

| GET | `/api/market/status` | counts and last refresh per source |
| GET | `/api/market/stocks?sector=&q=&sort=&order=` | NIFTY 50 with fundamentals + risk metrics |
| GET | `/api/market/stocks/{symbol}?range=1m..5y` | detail + price history + NIFTY 50 benchmark |
| GET | `/api/market/funds?category=&kind=equity\|debt&sort=` | funds with CAGR, Sharpe, Sortino, drawdown |
| GET | `/api/market/funds/{code}?range=` | detail + NAV history + benchmark |
| GET | `/api/market/fds?days=&amount=&senior=&tax_saver=` | banks ranked by rate with maturity value |

### Market data
- **Stocks:** NIFTY 50 via Yahoo Finance: 5 years of adjusted daily closes plus fundamentals. Refreshed Mon–Fri at 16:30 IST.
- **Mutual funds:** about 30 Direct-Growth funds across Index, Large, Flexi, Mid, Small, ELSS, Hybrid, Debt and Liquid, from AMFI NAVs via mfapi.in. Refreshed daily at 23:30 IST.
  - Funds are matched by name against the full scheme list. A fund that has stopped publishing NAVs falls through to the next match.
  - Instruments that leave the list are removed on the next refresh.
- **FDs:** indicative rates in `market_data/fd_rates.json`, since no free API exists. Confirm on each bank's site and bump `as_of`.
- **Risk metrics:** use a risk-free rate of `RISK_FREE_RATE` (default 6.5%). The in-process scheduler runs when `ENABLE_SCHEDULER=true`. Use a single worker; in production, run the CLI from cron instead.

### Savings insights logic
- **Budgets:** flags categories over 100% (danger) or past 80% (warning).
- **50/30/20:** needs / wants / savings as a share of income. SIPs and investments count as savings.
- **Recurring payments:** same merchant in 2 or more of the last 3 months, with amounts within ±15% of the median.
- **Spikes:** this month's category total > mean + 2σ of the previous 6 months, and > 25% above the mean.
- **Compounding nudge:** what a 20% cut in the top discretionary category grows to as a 10-year SIP at 12%.

Try it with [`data/sample_statement.csv`](data/sample_statement.csv) (6 months of sample data) via **Import CSV**.

## Roadmap
- [x] **Phase 1** Foundation: auth, financial profile, risk scoring
- [x] **Phase 2** Expense tracker + savings insights
- [x] **Phase 3** Market data layer (yfinance, mfapi.in, FD rates)
- [ ] **Phase 4** Recommendation algorithms (allocation, stock scoring, MF ranking, FD pick, SIP planner)
- [ ] **Phase 5** AI agents (LangGraph) on top of the algorithms
- [ ] **Phase 6** RAG chatbot + learning modules
- [ ] **Phase 7** Polish, Docker, deploy
