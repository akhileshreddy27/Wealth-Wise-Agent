import { inr, pct, type FdPickQuote, type FundPick, type PlanItem, type Recommendation } from '../../lib/api'
import { Swatch } from './AllocationCard'
import { ASSETS } from './assets'

const colorOf = (asset: string) => ASSETS.find((a) => a.key === asset)?.color ?? 'var(--chart-axis)'

function FundLine({ f }: { f: FundPick }) {
  return (
    <li className="rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium text-slate-800">{f.short_name}</span>
        <span className="text-xs text-slate-500">
          {f.category} · score <span className="font-semibold text-slate-700">{f.score.toFixed(0)}</span>/100
          {f.peers > 1 && <> · #{f.rank_in_category} of {f.peers}</>}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        3Y CAGR {pct(f.metrics.cagr_3y)} · Sharpe {f.metrics.sharpe_3y?.toFixed(2) ?? '—'} · Max drawdown {pct(f.metrics.max_drawdown_3y)}
      </p>
      {f.reasons.length > 0 && <p className="mt-1 text-xs text-emerald-800">✓ {f.reasons.join(' · ')}</p>}
      {f.cautions.length > 0 && <p className="mt-0.5 text-xs text-amber-800">! {f.cautions.join(' · ')}</p>}
    </li>
  )
}

function FdLine({ q }: { q: FdPickQuote }) {
  return (
    <li className="rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2">
      <span className="font-medium text-slate-800">{q.bank}</span>
      <span className="ml-2 text-xs text-slate-500">{q.rate.toFixed(2)}% p.a. for {Math.round(q.tenure_days / 365)} yr</span>
      <p className="text-xs text-slate-500">Monthly amounts can go into a recurring deposit, or build up and then be locked into an FD.</p>
    </li>
  )
}

function Picks({ item }: { item: PlanItem }) {
  if (item.picks.length === 0) return <p className="text-xs text-slate-400">No market data loaded for this sleeve yet.</p>
  if (item.sleeve === 'stocks') {
    return (
      <div>
        <ul className="flex flex-wrap gap-1.5">
          {item.picks.map((p) => 'symbol' in p && (
            <li key={p.symbol} className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs">
              <span className="font-semibold">{p.symbol}</span> <span className="text-slate-500">score {p.score.toFixed(0)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-1.5 text-xs text-slate-500">Build these up over a few months rather than buying all at once. The full scoring is below.</p>
      </div>
    )
  }
  return (
    <ul className="space-y-1.5">
      {item.picks.map((p) =>
        'scheme_code' in p ? <FundLine key={p.scheme_code} f={p} /> : 'bank' in p ? <FdLine key={p.bank} q={p} /> : null)}
    </ul>
  )
}

export default function PlanTable({ rec }: { rec: Recommendation }) {
  const { investable, plan, notes } = rec
  const total = plan.reduce((s, p) => s + p.monthly, 0)
  const hasLump = plan.some((p) => p.lumpsum > 0)
  return (
    <div className="card">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Monthly investment plan</h2>
        <p className="text-sm text-slate-500">
          <span className="font-semibold text-slate-800">{inr(total)}</span>/month
          {investable.lumpsum > 0 && <> + {inr(investable.lumpsum)} one-time</>}
        </p>
      </div>
      {rec.plan_starts === 'after_emergency' && (
        <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
          Starts in month {(rec.emergency.months_to_fill ?? 0) + 1}, once your emergency fund is full. Until then, your whole surplus goes there.
        </p>
      )}
      {plan.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">
          Nothing left to invest after {rec.emergency.ok ? 'expenses' : 'building your emergency fund'}. Check the savings tips on the Expenses page.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-slate-100">
          {plan.map((item) => (
            <li key={item.sleeve} className="grid gap-3 py-4 sm:grid-cols-[14rem_1fr]">
              <div>
                <p className="flex items-center gap-2 font-medium text-slate-800"><Swatch color={colorOf(item.asset)} />{item.label}</p>
                <p className="mt-1 text-xl font-semibold text-slate-900">{inr(item.monthly)}<span className="text-sm font-normal text-slate-500">/mo</span></p>
                <p className="text-xs text-slate-400">
                  {pct(item.share, 0)} of the plan{hasLump && item.lumpsum > 0 && <> · {inr(item.lumpsum)} lump sum</>}
                </p>
              </div>
              <Picks item={item} />
            </li>
          ))}
        </ul>
      )}
      {notes.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500">
          {notes.map((n) => <li key={n}>ℹ {n}</li>)}
        </ul>
      )}
    </div>
  )
}
