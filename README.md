# Wealth Wise Agent

AI-powered personal finance assistant: personalised stock / mutual fund / FD recommendations,
a RAG chatbot with learning modules, and an expense tracker.

> Educational project. Not SEBI-registered investment advice.

## Stack
- **Backend:** FastAPI, SQLAlchemy 2, SQLite (swap to Postgres via `DATABASE_URL`), JWT auth
- **AI:** LangGraph + any OpenAI-compatible LLM (Groq free tier by default)
- **Frontend:** React 19 + Vite + TypeScript + Tailwind v4, React Router

## Run locally

```bash
# backend (http://localhost:8000, docs at /docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # then set JWT_SECRET, and GROQ_API_KEY for the AI features (optional)
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
  services/   (Phase 4, deterministic recommendation engine)
              allocation.py     risk score + age + horizon -> equity/debt/FD/liquid, emergency fund, SIP split
              stock_scoring.py  value / quality / momentum / low-vol percentile scoring, risk filter
              fund_ranking.py   rank funds within category; sleeve -> allowed fund categories
              fd_pick.py        best FD for the horizon, senior rate, tax-saver FD
              planner.py        goal SIP planner and projections
              recommend.py      ties it all together for /api/recommend
  jobs/       refresh.py (CLI + refresh log), scheduler.py (APScheduler, IST)
  agents/     (Phase 5, LangGraph)
              llm.py         provider config: Groq (free tier), Ollama, OpenRouter, Gemini; all OpenAI-compatible
              tools.py       tools the agents call for every figure (plan, stocks, funds, FDs, goals, expenses)
              advisor.py     tool-calling agent graph with a number-verification step
              guard.py       checks every number in an AI answer against tool outputs
              explainer.py   "Explain my plan" with a rule-based fallback
              categorizer.py batched AI fallback for transactions the keyword rules can't place
  rag/        (Phase 6)
frontend/src/
  pages/      AuthPage, Onboarding (3-step), Dashboard, Expenses, Markets, Recommendations
  components/expenses/  charts, insights, budgets, transaction form, CSV import
  components/recommend/ allocation, monthly plan, stock picks, FD pick, goal planner, AI explanation
  pages/Assistant.tsx   chat with the advisor agent
  context/    AuthContext
  lib/api.ts  axios client + shared types
```

## API
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

| GET | `/api/recommend?tax_regime=new\|old` | full plan: investable surplus, emergency fund, allocation, monthly SIP split with picks, stocks, FD |
| GET | `/api/recommend/stocks?risk_category=&limit=` | NIFTY 50 scored for a risk category, plus sector-capped picks |
| GET | `/api/recommend/funds?category=` | funds ranked within their category |
| GET | `/api/recommend/sip-plan?goal_amount=&years=&annual_return=&current_corpus=&inflation=` | monthly SIP for a goal, vs your surplus |

| GET | `/api/agent/status` | whether AI is configured (provider, model) |
| GET | `/api/agent/explain-plan?tax_regime=` | plain-language plan explanation (`source`: ai or rules) |
| POST | `/api/agent/chat` | `{messages: [{role, content}]}` → reply, tools used, `grounded`, `unverified` |

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

### Recommendation logic (Phase 4)
All rule-based and deterministic: the same profile and data always give the same plan, and every number traces back to a rule.
- **Investable surplus:** average actual savings (income minus non-investment spending) over the last 3 complete months with transactions; otherwise profile income minus expenses.
- **Emergency fund first:** 6 months of expenses in a liquid fund. If the gap is at most 3 months of surplus, all of the surplus goes there; otherwise half does, so investing still starts. If the fund takes everything for now, the page shows the plan that starts once it's full.
- **Asset allocation:** equity starts at `10% + 8% × (risk score − 1)`, then is capped by age (`110 − age`) and horizon (0% under 3 years, 30% under 5, 55% under 7). Liquid is 5% (10% for horizons under 3 years). The rest is split between FDs and debt funds, with more in FDs for lower risk scores. Each cap that applies is listed under "Why this mix".
- **Sleeves:** equity is spread by risk category (conservative: index/large + balanced advantage; moderate: + flexi + mid; aggressive: + small). Users who already invest get 10–20% in direct stocks. With the old tax regime, ELSS takes up to ₹12,500/month (the 80C limit). Sleeves under the ₹500 SIP minimum are merged.
- **Stock scoring:** percentile within NIFTY 50 for value (P/E, P/B), quality (ROE, D/E, margin), momentum (6M, 1Y return) and low volatility (vol, beta), with weights by risk category. Loss-makers get the worst value score. A risk filter applies (conservative: vol ≤ 25% and beta ≤ 1.0; moderate: vol ≤ 35% and beta ≤ 1.3), and picks are capped at 2 per sector.
- **Fund ranking:** within the AMFI category by Sharpe 3Y (25%), Sortino, 3Y and 5Y CAGR, rolling 1Y consistency and max drawdown (15% each). Missing metrics count as neutral and are flagged. Index funds are placed by what they track (Nifty 50 is core; Midcap 150 is mid).
- **FD pick:** best rate for the horizon (1–5 years), senior rate at 60+, the best large bank shown alongside a small finance bank (DICGC ₹5 lakh), and the tax-saver FD under the old regime.
- **Goal planner:** monthly SIP = (goal × (1 + inflation)^years − corpus growth) / SIP factor, paid monthly in advance. The default return is the expected return of the allocation for *that goal's* horizon.

### AI layer (Phase 5)
The AI explains; it never calculates. Every number comes from the deterministic code above.
- **Provider:** set `LLM_PROVIDER` and a key in `backend/.env`. The default is **Groq** (free tier, `llama-3.3-70b-versatile`; get a key at console.groq.com/keys). `ollama` runs fully locally with no key; `openrouter` and `gemini` also work. Without a key, everything still works: the explanation falls back to a rule-based summary and the Assistant page shows setup steps.
- **Advisor agent (LangGraph):** `agent → tools → agent … → verify`. The agent has 8 tools wrapping Phase 2–4 code: profile, full plan, stock scores, stock lookup, fund rankings, FD options, goal SIP and expense summary. Tool outputs are kept compact to fit free-tier token limits.
- **Number guard:** after the agent answers, every figure in the reply (₹ amounts, %, lakh/crore/k, ratios) must match a tool result, the user's own message, or a known rule (80C ₹1.5 lakh, DICGC ₹5 lakh, 50/30/20…), allowing for rounding and % vs fraction. If any doesn't, the agent is told which figures failed and gets one retry. Anything still unverified is returned in `unverified` and flagged in the UI. For "Explain my plan", a failed check falls back to the rule-based summary.
- **Categoriser fallback:** keyword rules run first. Only descriptions they file under "other" go to the model, in one batched call per CSV import, and replies are validated against the category list.
- **Tests** use a scripted fake model (`tests/fakes.py`), so they run offline. `tests/conftest.py` forces `LLM_PROVIDER=none` so a real key in `.env` is never used.

Try it with [`data/sample_statement.csv`](data/sample_statement.csv) (6 months of sample data) via **Import CSV**.

## Roadmap
- [x] **Phase 1** Foundation: auth, financial profile, risk scoring
- [x] **Phase 2** Expense tracker + savings insights
- [x] **Phase 3** Market data layer (yfinance, mfapi.in, FD rates)
- [x] **Phase 4** Recommendation algorithms (allocation, stock scoring, MF ranking, FD pick, SIP planner)
- [x] **Phase 5** AI agents (LangGraph) on top of the algorithms
- [ ] **Phase 6** RAG chatbot + learning modules
- [ ] **Phase 7** Polish, Docker, deploy
