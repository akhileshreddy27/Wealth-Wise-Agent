import { useEffect, useState } from 'react'
import { api, inr, type FdQuote } from '../../lib/api'

const TENURES = [
  { days: 180, label: '6 months' }, { days: 365, label: '1 year' }, { days: 730, label: '2 years' },
  { days: 1095, label: '3 years' }, { days: 1825, label: '5 years' },
]
const TYPE_LABEL: Record<string, string> = { public: 'Public sector', private: 'Private', small_finance: 'Small finance', government: 'Government' }

export default function FdTab() {
  const [amount, setAmount] = useState(100000)
  const [days, setDays] = useState(365)
  const [senior, setSenior] = useState(false)
  const [taxSaver, setTaxSaver] = useState(false)
  const [data, setData] = useState<{ items: FdQuote[]; as_of: string | null } | null>(null)

  const effDays = taxSaver ? 1825 : days
  useEffect(() => {
    if (!(amount > 0)) return
    const t = setTimeout(() => {
      api.get('/market/fds', { params: { days: effDays, amount, senior, tax_saver: taxSaver } }).then((r) => setData(r.data))
    }, 200)
    return () => clearTimeout(t)
  }, [amount, effDays, senior, taxSaver])

  const best = data?.items[0]
  return (
    <div className="space-y-4">
      <div className="card grid gap-4 sm:grid-cols-[1fr_2fr]">
        <div>
          <label className="label" htmlFor="fd-amount">Deposit amount (₹)</label>
          <input id="fd-amount" type="number" min={1000} step={1000} className="input" value={amount || ''}
            onChange={(e) => setAmount(Number(e.target.value))} />
        </div>
        <div>
          <p className="label">Tenure</p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Tenure">
            {TENURES.map((t) => (
              <button key={t.days} disabled={taxSaver} onClick={() => setDays(t.days)} aria-pressed={effDays === t.days}
                className={`rounded-full border px-3 py-1 text-sm disabled:opacity-40 ${effDays === t.days ? 'border-brand-600 bg-brand-50 font-semibold text-brand-700' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-6 text-sm sm:col-span-2">
          <label className="flex items-center gap-2"><input type="checkbox" checked={senior} onChange={(e) => setSenior(e.target.checked)} className="h-4 w-4 accent-emerald-600" />Senior citizen (60+)</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={taxSaver} onChange={(e) => setTaxSaver(e.target.checked)} className="h-4 w-4 accent-emerald-600" />Tax-saver FD (80C, 5-year lock-in)</label>
        </div>
      </div>

      {best && (
        <div className="rounded-xl border border-brand-100 bg-brand-50 p-4 text-sm text-slate-700">
          Best rate: <b>{best.bank}</b> at <b>{best.applied_rate.toFixed(2)}%</b>. {inr(amount)} grows to <b>{inr(best.maturity_value)}</b> (interest {inr(best.interest)}).
        </div>
      )}

      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Bank</th>
                <th className="px-3 py-2 text-right font-medium">Rate p.a.</th>
                <th className="px-3 py-2 text-right font-medium">Interest earned</th>
                <th className="px-4 py-2 text-right font-medium">Maturity value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.items.map((r, i) => (
                <tr key={r.id} className={i === 0 ? 'bg-brand-50/40' : ''}>
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-slate-800">{r.bank}</span>
                    <span className="block text-xs text-slate-400">{TYPE_LABEL[r.bank_type] ?? r.bank_type}</span>
                  </td>
                  <td className="px-3 py-2.5 text-right font-semibold tabular-nums">{r.applied_rate.toFixed(2)}%</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{inr(r.interest)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{inr(r.maturity_value)}</td>
                </tr>
              ))}
              {data && data.items.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-500">No banks offer this tenure.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-xs text-slate-500">
        ⚠ Indicative rates{data?.as_of ? ` as of ${new Date(data.as_of + 'T00:00').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}` : ''}. Banks revise FD rates often, so confirm on the bank’s website before investing.
        Maturity assumes quarterly compounding; interest above ₹40,000 a year (₹50,000 for seniors) attracts TDS. Small finance bank deposits are insured by DICGC only up to ₹5 lakh.
      </p>
    </div>
  )
}
