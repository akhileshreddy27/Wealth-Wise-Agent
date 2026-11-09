import { mcap, pct, shortName, type Recommendation } from '../../lib/api'

const FACTORS = [
  { key: 'value', label: 'Value', hint: 'Low P/E and P/B vs other NIFTY 50 stocks' },
  { key: 'quality', label: 'Quality', hint: 'High ROE and margins, low debt' },
  { key: 'momentum', label: 'Momentum', hint: 'Strong 6-month and 1-year returns' },
  { key: 'low_vol', label: 'Low vol', hint: 'Low volatility and beta' },
] as const

/** A 0-100 percentile as a thin bar plus the number, so the value never relies on bar length alone. */
function FactorBar({ v }: { v: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full" style={{ width: `${v}%`, background: 'var(--series-1)' }} />
      </div>
      <span className="w-6 text-right tabular-nums text-slate-600">{v}</span>
    </div>
  )
}

export default function StockPicks({ rec }: { rec: Recommendation }) {
  const { picks, eligible, universe, weights } = rec.stocks
  if (universe === 0) return null
  return (
    <div className="card overflow-hidden p-0">
      <div className="p-5">
        <h2 className="font-semibold">Stock ideas for {rec.profile.risk_category === 'aggressive' ? 'an' : 'a'} {rec.profile.risk_category} investor</h2>
        <p className="mt-1 text-sm text-slate-500">
          {eligible} of {universe} NIFTY 50 stocks pass your risk filter. Scores weight{' '}
          {FACTORS.map((f, i) => <span key={f.key}>{i > 0 && (i === FACTORS.length - 1 ? ' and ' : ', ')}{f.label.toLowerCase()} {pct(weights[f.key], 0)}</span>)},
          with at most two per sector.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-y border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Stock</th>
              <th className="px-3 py-2 text-right font-medium">Score</th>
              {FACTORS.map((f) => <th key={f.key} className="px-3 py-2 font-medium" title={f.hint}>{f.label}</th>)}
              <th className="px-4 py-2 font-medium">Why</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {picks.map((s) => (
              <tr key={s.symbol} className="align-top">
                <td className="px-4 py-2.5">
                  <span className="font-semibold text-slate-800">{s.symbol}</span>
                  <span className="block text-xs text-slate-400">{shortName(s.name)} · {s.sector ?? '—'} · {mcap(s.market_cap)}</span>
                </td>
                <td className="px-3 py-2.5 text-right text-base font-semibold tabular-nums">{s.score.toFixed(0)}</td>
                {FACTORS.map((f) => <td key={f.key} className="px-3 py-2.5 text-xs"><FactorBar v={s.factors[f.key]} /></td>)}
                <td className="max-w-xs px-4 py-2.5 text-xs">
                  {s.reasons.map((r) => <p key={r} className="text-emerald-800">✓ {r}</p>)}
                  {s.cautions.map((c) => <p key={c} className="text-amber-800">! {c}</p>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-5 py-3 text-xs text-slate-400">Factor columns are percentiles within NIFTY 50 (100 = best). Scores rank stocks against each other; they don’t predict prices.</p>
    </div>
  )
}
