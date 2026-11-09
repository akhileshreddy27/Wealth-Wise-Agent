import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage, inr, monthLabel, type Recommendation } from '../lib/api'
import AllocationCard from '../components/recommend/AllocationCard'
import PlanTable from '../components/recommend/PlanTable'
import StockPicks from '../components/recommend/StockPicks'
import FdCard from '../components/recommend/FdCard'
import GoalPlanner from '../components/recommend/GoalPlanner'
import ExplainCard from '../components/recommend/ExplainCard'

const REGIME_KEY = 'ww_tax_regime'

function readRegime(): 'new' | 'old' {
  try { return localStorage.getItem(REGIME_KEY) === 'old' ? 'old' : 'new' } catch { return 'new' }
}

function EmergencyCard({ rec }: { rec: Recommendation }) {
  const e = rec.emergency
  if (e.ok) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
        ✓ Emergency fund in place: {inr(e.current)} covers 6 months of expenses ({inr(e.target)}).
        {rec.investable.lumpsum > 0 && <> The extra {inr(rec.investable.lumpsum)} can be invested as a lump sum using the same mix.</>}
      </div>
    )
  }
  const fund = e.picks[0]
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="font-semibold">! Step 1: build your emergency fund</p>
      <p className="mt-1">
        You have {inr(e.current)} of the {inr(e.target)} target (6 months of expenses).
        {e.monthly_contribution > 0
          ? <> Put <b>{inr(e.monthly_contribution)}/month</b> into a liquid fund{fund ? <> such as <b>{fund.short_name}</b></> : null} and you’ll be there in about {e.months_to_fill} month{e.months_to_fill === 1 ? '' : 's'}.</>
          : <> Free up some monthly surplus first; the Expenses page shows where.</>}
      </p>
    </div>
  )
}

export default function Recommendations() {
  const [regime, setRegime] = useState<'new' | 'old'>(readRegime)
  const [rec, setRec] = useState<Recommendation | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    try { localStorage.setItem(REGIME_KEY, regime) } catch { /* storage unavailable */ }
    api.get<Recommendation>('/recommend', { params: { tax_regime: regime } })
      .then((r) => { setRec(r.data); setError('') })
      .catch((e) => setError(errorMessage(e)))
  }, [regime])

  if (error) return <div className="card text-sm text-red-700">{error}</div>
  if (!rec) return <p className="text-slate-500">Building your plan…</p>

  const inv = rec.investable
  const noMarket = rec.data.funds === 0 && rec.data.stocks === 0
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Recommendations</h1>
          <p className="text-sm text-slate-500">
            For a <span className="font-medium capitalize text-slate-700">{rec.profile.risk_category}</span> investor
            (risk {rec.profile.risk_score}/10), age {rec.profile.age}, {rec.profile.horizon_years}-year horizon.{' '}
            <Link to="/onboarding" className="text-brand-700 hover:underline">Edit profile</Link>
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 text-sm" role="group" aria-label="Tax regime">
          {(['new', 'old'] as const).map((r) => (
            <button key={r} onClick={() => setRegime(r)} aria-pressed={regime === r}
              className={`rounded-md px-3 py-1 ${regime === r ? 'bg-brand-50 font-semibold text-brand-700' : 'text-slate-600 hover:bg-slate-50'}`}>
              {r === 'new' ? 'New tax regime' : 'Old regime (80C)'}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-sm text-slate-500">Investable each month</p>
          <p className="mt-1 text-2xl font-bold">{inr(inv.monthly)}</p>
          <p className="mt-1 text-xs text-slate-400">
            {inv.source === 'expenses'
              ? `Average actual savings, ${inv.months_used.map((m) => monthLabel(m, 'short')).join(', ')}`
              : 'Profile income minus expenses (import transactions for actuals)'}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-slate-500">To emergency fund</p>
          <p className="mt-1 text-2xl font-bold">{inr(rec.emergency.monthly_contribution)}</p>
          <p className="mt-1 text-xs text-slate-400">{rec.emergency.ok ? 'Already fully funded' : `Gap: ${inr(rec.emergency.shortfall)}`}</p>
        </div>
        <div className="card">
          <p className="text-sm text-slate-500">To invest for growth</p>
          <p className="mt-1 text-2xl font-bold">{inr(inv.to_invest)}</p>
          <p className="mt-1 text-xs text-slate-400">Split across the plan below</p>
        </div>
      </div>

      <EmergencyCard rec={rec} />
      {noMarket && (
        <div className="card text-sm text-slate-600">
          No market data loaded yet, so fund and stock picks are empty. Run{' '}
          <code className="rounded bg-slate-100 px-1.5 py-0.5">python -m app.jobs.refresh all</code> in <code>backend/</code>.
        </div>
      )}
      <ExplainCard key={regime} regime={regime} />
      <AllocationCard rec={rec} />
      <PlanTable rec={rec} />
      <FdCard rec={rec} />
      <StockPicks rec={rec} />
      <GoalPlanner />
      <p className="text-xs text-slate-500">⚠ {rec.disclaimer}</p>
    </div>
  )
}
