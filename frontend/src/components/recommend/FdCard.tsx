import { inr, type FdPickQuote, type Recommendation } from '../../lib/api'

function Quote({ q, tag }: { q: FdPickQuote; tag: string }) {
  return (
    <div className="rounded-xl border border-slate-200 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{tag}</p>
      <p className="mt-1 font-semibold text-slate-800">{q.bank}</p>
      <p className="text-2xl font-bold text-slate-900">{q.rate.toFixed(2)}%<span className="text-sm font-normal text-slate-500"> p.a.</span></p>
      <p className="text-xs text-slate-500">{Math.round(q.tenure_days / 365)} yr · {inr(q.maturity_value)} at maturity</p>
    </div>
  )
}

export default function FdCard({ rec }: { rec: Recommendation }) {
  const fd = rec.fd
  if (!fd?.best) return null
  return (
    <div className="card">
      <h2 className="font-semibold">Fixed deposit pick</h2>
      <p className="mt-1 text-sm text-slate-500">For {inr(fd.amount)}{fd.senior ? ' at senior-citizen rates' : ''}.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Quote q={fd.best} tag="Best rate" />
        {fd.safest && <Quote q={fd.safest} tag="Best large bank" />}
        {fd.tax_saver && <Quote q={fd.tax_saver} tag="Tax-saver (80C)" />}
      </div>
      {fd.alternatives.length > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          Also good: {fd.alternatives.map((a) => `${a.bank} ${a.rate.toFixed(2)}%`).join(' · ')}
        </p>
      )}
      <ul className="mt-3 space-y-1 text-xs text-slate-500">
        {fd.notes.map((n) => <li key={n}>ℹ {n}</li>)}
        <li>⚠ Indicative rates{fd.as_of ? ` as of ${new Date(fd.as_of + 'T00:00').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}` : ''}; confirm on the bank’s website.</li>
      </ul>
    </div>
  )
}
