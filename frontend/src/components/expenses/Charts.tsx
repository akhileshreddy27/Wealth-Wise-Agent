import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts'
import { inr, inrCompact, monthLabel, type Summary } from '../../lib/api'

const S1 = 'var(--series-1)', S2 = 'var(--series-2)', S3 = 'var(--series-3)'

function Swatch({ color }: { color: string }) {
  return <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
}

function TrendTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-semibold text-slate-700">{monthLabel(String(label))}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-slate-600">
          <Swatch color={String(p.color)} /> <span className="capitalize">{p.dataKey}</span>
          <span className="ml-auto pl-4 font-medium text-slate-800">{inr(Number(p.value))}</span>
        </p>
      ))}
    </div>
  )
}

export function TrendChart({ data }: { data: Summary['trend'] }) {
  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Income vs spending, last 6 months</h2>
        <div className="flex gap-4 text-xs text-slate-600">
          <span className="flex items-center gap-1.5"><Swatch color={S1} />Income</span>
          <span className="flex items-center gap-1.5"><Swatch color={S2} />Spending</span>
        </div>
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={2} barCategoryGap="28%" margin={{ left: -8, right: 4, top: 4 }}>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis dataKey="month" tickFormatter={(m) => monthLabel(m, 'short')} tickLine={false} axisLine={false}
              tick={{ fontSize: 12, fill: 'var(--chart-axis)' }} />
            <YAxis tickFormatter={inrCompact} tickLine={false} axisLine={false} width={56}
              tick={{ fontSize: 12, fill: 'var(--chart-axis)' }} />
            <Tooltip content={<TrendTooltip />} cursor={{ fill: '#f1f5f9' }} />
            <Bar dataKey="income" fill={S1} radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="expense" fill={S2} radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

const BUCKETS = [
  { key: 'needs', label: 'Needs', target: 0.5, color: S1 },
  { key: 'wants', label: 'Wants', target: 0.3, color: S2 },
  { key: 'savings', label: 'Savings', target: 0.2, color: S3 },
] as const

export function BucketBar({ summary }: { summary: Summary }) {
  const base = summary.income_base
  if (!base) {
    return <div className="card text-sm text-slate-500">Add an income transaction to see your 50/30/20 split.</div>
  }
  const total = BUCKETS.reduce((s, b) => s + summary.buckets[b.key], 0) || 1
  return (
    <div className="card">
      <h2 className="font-semibold">50 / 30 / 20 check</h2>
      <p className="mb-4 text-xs text-slate-500">
        Share of {summary.income_is_estimate ? 'your profile income (no income logged this month)' : 'this month’s income'}
      </p>
      <div className="flex h-4 w-full gap-[2px] overflow-hidden rounded">
        {BUCKETS.map((b) => {
          const v = summary.buckets[b.key]
          return v > 0 ? (
            <div key={b.key} style={{ width: `${(v / total) * 100}%`, background: b.color }}
              title={`${b.label}: ${inr(v)} (${((summary.bucket_share[b.key] ?? 0) * 100).toFixed(0)}% of income)`} />
          ) : null
        })}
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
        {BUCKETS.map((b) => {
          const share = summary.bucket_share[b.key] ?? 0
          const off = b.key === 'savings' ? share < b.target : share > b.target
          return (
            <div key={b.key}>
              <dt className="flex items-center gap-1.5 text-slate-500"><Swatch color={b.color} />{b.label}</dt>
              <dd className="mt-0.5 text-lg font-semibold text-slate-800">{(share * 100).toFixed(0)}%</dd>
              <dd className={`text-xs ${off ? 'text-amber-700' : 'text-slate-400'}`}>
                {off ? '▲ ' : ''}target {b.target * 100}% · {inrCompact(summary.buckets[b.key])}
              </dd>
            </div>
          )
        })}
      </dl>
    </div>
  )
}

export function CategoryBars({ summary, onEditBudgets }: { summary: Summary; onEditBudgets: () => void }) {
  const rows = summary.categories
  const max = Math.max(1, ...rows.map((r) => Math.max(r.amount, r.budget ?? 0)))
  return (
    <div className="card">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold">Spending by category</h2>
        <button className="text-sm font-medium text-brand-700 hover:underline" onClick={onEditBudgets}>Set budgets</button>
      </div>
      {rows.length === 0 ? <p className="text-sm text-slate-500">No spending recorded this month.</p> : (
        <ul className="space-y-3">
          {rows.map((r) => {
            const over = r.budget != null && r.amount > r.budget
            return (
              <li key={r.category} className="group" title={`${r.label}: ${inr(r.amount)}${r.budget ? ` of ${inr(r.budget)} budget` : ''}`}>
                <div className="mb-1 flex items-baseline justify-between text-sm">
                  <span className="text-slate-700">{r.label}</span>
                  <span className="font-medium text-slate-800">
                    {inr(r.amount)}
                    {r.budget != null && (
                      <span className={`ml-1.5 text-xs font-normal ${over ? 'text-red-700' : 'text-slate-400'}`}>
                        {over ? `⚠ over by ${inr(r.amount - r.budget)}` : `of ${inrCompact(r.budget)}`}
                      </span>
                    )}
                  </span>
                </div>
                <div className="relative h-2 rounded bg-slate-100">
                  <div className="h-2 rounded group-hover:opacity-80" style={{ width: `${(r.amount / max) * 100}%`, background: S1 }} />
                  {r.budget != null && (
                    <div className="absolute -top-1 h-4 w-0.5 rounded bg-slate-700" style={{ left: `calc(${(r.budget / max) * 100}% - 1px)` }}
                      aria-label={`Budget ${inr(r.budget)}`} />
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
      {rows.some((r) => r.budget != null) && (
        <p className="mt-4 flex items-center gap-1.5 text-xs text-slate-400"><span className="inline-block h-3 w-0.5 bg-slate-700" /> budget limit</p>
      )}
    </div>
  )
}
