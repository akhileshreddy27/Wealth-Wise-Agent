import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, inr, type Profile } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const RISK_STYLE = {
  conservative: 'bg-sky-100 text-sky-800',
  moderate: 'bg-amber-100 text-amber-800',
  aggressive: 'bg-rose-100 text-rose-800',
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [p, setP] = useState<Profile | null>(null)

  useEffect(() => { api.get<Profile>('/profile').then((r) => setP(r.data)) }, [])

  if (!p) return <p className="text-slate-500">Loading…</p>
  const s = p.snapshot

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Hi, {user?.full_name.split(' ')[0]}</h1>
          <p className="text-sm text-slate-500">Here's your financial snapshot.</p>
        </div>
        <Link to="/onboarding" className="btn-ghost">Edit profile</Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Monthly surplus" value={inr(s.monthly_surplus)} sub="Income minus expenses" />
        <Stat label="Savings rate" value={`${(s.savings_rate * 100).toFixed(0)}%`} sub="Aim for 20% or more" />
        <Stat label="Emergency fund" value={s.emergency_fund_months != null ? `${s.emergency_fund_months} months` : '—'}
          sub={`Target: ${inr(s.emergency_fund_target)} (6 months)`} />
        <div className="card">
          <p className="text-sm text-slate-500">Risk profile</p>
          <p className="mt-1 text-2xl font-bold">{p.risk_score}/10</p>
          <span className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${RISK_STYLE[p.risk_category]}`}>
            {p.risk_category}
          </span>
        </div>
      </div>

      {!s.emergency_fund_ok && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Build your emergency fund first: you need {inr(s.emergency_fund_target - p.current_savings)} more to cover 6 months of expenses.
        </div>
      )}

      <div className="card">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Coming next</h2>
          <Link to="/expenses" className="text-sm font-medium text-brand-700 hover:underline">Track expenses →</Link>
        </div>
        <ul className="mt-2 list-inside list-disc text-sm text-slate-600">
                    <li>Personalised stock, mutual fund and FD recommendations (Phases 3–5)</li>
          <li>RAG chatbot and learning modules (Phase 6)</li>
        </ul>
      </div>
    </div>
  )
}
