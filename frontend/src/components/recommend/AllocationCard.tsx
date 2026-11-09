import { pct, type Recommendation } from '../../lib/api'
import { ASSETS } from './assets'

export function Swatch({ color }: { color: string }) {
  return <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: color }} />
}

export default function AllocationCard({ rec }: { rec: Recommendation }) {
  const { weights, rationale, expected_return } = rec.allocation
  const shown = ASSETS.filter((a) => weights[a.key] > 0)
  return (
    <div className="card">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Your asset allocation</h2>
        <p className="text-sm text-slate-500">
          Expected return ≈ <span className="font-semibold text-slate-800">{pct(expected_return)}</span> a year
        </p>
      </div>
      <div className="mt-4 flex h-4 w-full gap-[2px] overflow-hidden rounded" role="img"
        aria-label={shown.map((a) => `${a.label} ${pct(weights[a.key], 0)}`).join(', ')}>
        {shown.map((a) => (
          <div key={a.key} style={{ width: `${weights[a.key] * 100}%`, background: a.color }} title={`${a.label}: ${pct(weights[a.key], 0)}`} />
        ))}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {ASSETS.map((a) => (
          <div key={a.key} title={a.hint}>
            <dt className="flex items-center gap-1.5 text-slate-500"><Swatch color={a.color} />{a.label}</dt>
            <dd className="mt-0.5 text-lg font-semibold text-slate-800">{pct(weights[a.key], 0)}</dd>
            <dd className="text-xs text-slate-400">assumes {pct(rec.allocation.assumed_returns[a.key])}/yr</dd>
          </div>
        ))}
      </dl>
      <details className="mt-4 text-sm" open>
        <summary className="cursor-pointer font-medium text-slate-700">Why this mix</summary>
        <ul className="mt-2 list-inside list-disc space-y-1 text-slate-600">
          {rationale.map((r) => <li key={r}>{r}</li>)}
        </ul>
      </details>
    </div>
  )
}
