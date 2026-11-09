import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts'
import { api, errorMessage, inr, inrCompact, pct, type GoalPlan } from '../../lib/api'
import { Swatch } from './AllocationCard'

const S1 = 'var(--series-1)', S2 = 'var(--series-2)'
const SERIES = [{ key: 'value', label: 'Projected value', color: S1 }, { key: 'invested', label: 'Amount invested', color: S2 }]

function ProjTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-semibold text-slate-700">Year {label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-slate-600">
          <Swatch color={String(p.color)} />{SERIES.find((s) => s.key === p.dataKey)?.label}
          <span className="ml-auto pl-4 font-medium text-slate-800">{inr(Number(p.value))}</span>
        </p>
      ))}
    </div>
  )
}

export default function GoalPlanner() {
  const [goal, setGoal] = useState(2500000)
  const [years, setYears] = useState(10)
  const [corpus, setCorpus] = useState(0)
  const [inflate, setInflate] = useState(true)
  const [ret, setRet] = useState('')   // blank = use the allocation's expected return
  const [plan, setPlan] = useState<GoalPlan | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!(goal > 0 && years >= 1 && years <= 50)) return
    const t = setTimeout(() => {
      const params: Record<string, number> = { goal_amount: goal, years, current_corpus: corpus || 0, inflation: inflate ? 0.06 : 0 }
      if (ret !== '') params.annual_return = Number(ret) / 100
      api.get<GoalPlan>('/recommend/sip-plan', { params })
        .then((r) => { setPlan(r.data); setError('') })
        .catch((e) => setError(errorMessage(e)))
    }, 250)
    return () => clearTimeout(t)
  }, [goal, years, corpus, inflate, ret])

  return (
    <div className="card">
      <h2 className="font-semibold">Goal planner</h2>
      <p className="mt-1 text-sm text-slate-500">How much to invest each month to reach a goal. The return defaults to the mix your plan would use for that horizon.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-4">
        <div>
          <label className="label" htmlFor="g-amount">Goal (today’s ₹)</label>
          <input id="g-amount" type="number" min={1000} step={10000} className="input" value={goal || ''} onChange={(e) => setGoal(Number(e.target.value))} />
        </div>
        <div>
          <label className="label" htmlFor="g-years">In years</label>
          <input id="g-years" type="number" min={1} max={50} className="input" value={years || ''} onChange={(e) => setYears(Number(e.target.value))} />
        </div>
        <div>
          <label className="label" htmlFor="g-corpus">Already saved (₹)</label>
          <input id="g-corpus" type="number" min={0} step={10000} className="input" value={corpus || ''} placeholder="0" onChange={(e) => setCorpus(Number(e.target.value))} />
        </div>
        <div>
          <label className="label" htmlFor="g-ret">Return % (optional)</label>
          <input id="g-ret" type="number" min={0} max={30} step={0.5} className="input" value={ret} placeholder={plan ? (plan.annual_return * 100).toFixed(1) : 'auto'} onChange={(e) => setRet(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm sm:col-span-4">
          <input type="checkbox" checked={inflate} onChange={(e) => setInflate(e.target.checked)} className="h-4 w-4 accent-emerald-600" />
          Adjust the goal for 6% inflation
        </label>
      </div>

      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {plan && (
        <div className="mt-5 grid gap-5 lg:grid-cols-[18rem_1fr]">
          <div className="space-y-3">
            <div className="rounded-xl bg-brand-50 p-4">
              <p className="text-sm text-slate-600">Monthly SIP needed</p>
              <p className="text-3xl font-bold text-slate-900">{inr(plan.monthly_sip)}</p>
              <p className="mt-1 text-xs text-slate-500">at {pct(plan.annual_return)} a year for {plan.years} years</p>
            </div>
            {plan.affordable != null && (
              <p className={`rounded-lg border p-3 text-sm ${plan.affordable ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
                {plan.affordable
                  ? <>✓ Fits within your {inr(plan.monthly_budget!)}/month investable surplus.</>
                  : <>! More than your {inr(plan.monthly_budget!)}/month surplus.{' '}
                    {plan.months_at_budget ? <>Investing all of it gets there in about {(plan.months_at_budget / 12).toFixed(1)} years.</> : <>Consider a smaller goal or longer horizon.</>}</>}
              </p>
            )}
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <div><dt className="text-slate-500">Target</dt><dd className="font-semibold">{inr(plan.target_amount)}</dd></div>
              <div><dt className="text-slate-500">You invest</dt><dd className="font-semibold">{inr(plan.total_invested)}</dd></div>
              <div><dt className="text-slate-500">Growth</dt><dd className="font-semibold">{inr(plan.gains)}</dd></div>
              <div><dt className="text-slate-500">Final value</dt><dd className="font-semibold">{inr(plan.projected_value)}</dd></div>
            </dl>
            <ul className="text-xs text-slate-400">{plan.assumptions.map((a) => <li key={a}>· {a}</li>)}</ul>
          </div>
          <div>
            <div className="mb-2 flex gap-4 text-xs text-slate-600">
              {SERIES.map((s) => <span key={s.key} className="flex items-center gap-1.5"><Swatch color={s.color} />{s.label}</span>)}
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={plan.projection} margin={{ left: -8, right: 8, top: 4 }}>
                  <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                  <XAxis dataKey="year" tickFormatter={(y) => `Y${y}`} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: 'var(--chart-axis)' }} />
                  <YAxis tickFormatter={inrCompact} tickLine={false} axisLine={false} width={60} tick={{ fontSize: 12, fill: 'var(--chart-axis)' }} />
                  <Tooltip content={<ProjTooltip />} />
                  {SERIES.map((s) => (
                    <Line key={s.key} dataKey={s.key} stroke={s.color} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
