import { useEffect, useState } from 'react'
import { api, num, pct, type Fund, type PricePoint, type Range } from '../../lib/api'
import Change from './Change'
import DetailDrawer, { Stat } from './DetailDrawer'
import PriceChart from './PriceChart'
import SortHeader, { type SortState } from './SortHeader'

function FundDetail({ code, onClose }: { code: number; onClose: () => void }) {
  const [range, setRange] = useState<Range>('3y')
  const [data, setData] = useState<{ fund: Fund; history: PricePoint[]; benchmark: { history: PricePoint[] } } | null>(null)
  useEffect(() => { api.get(`/market/funds/${code}`, { params: { range } }).then((r) => setData(r.data)) }, [code, range])
  const f = data?.fund
  return (
    <DetailDrawer title={f?.name ?? 'Fund'} onClose={onClose}
      subtitle={f && <>{f.fund_house} · {f.scheme_category}</>}>
      {!f ? <p className="text-slate-500">Loading…</p> : (
        <div className="space-y-6">
          <div className="flex items-baseline gap-3">
            <span className="text-3xl font-bold text-slate-800">₹{f.nav?.toLocaleString('en-IN', { maximumFractionDigits: 4 })}</span>
            <span className="text-xs text-slate-400">NAV on {f.nav_date && new Date(f.nav_date + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
          </div>
          <PriceChart history={data.history} benchmark={data.benchmark.history} label="This fund" range={range} onRange={setRange} valueLabel="NAV" />
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="1Y return"><Change value={f.return_1y} /></Stat>
            <Stat label="3Y CAGR"><Change value={f.cagr_3y} /></Stat>
            <Stat label="5Y CAGR"><Change value={f.cagr_5y} /></Stat>
            <Stat label="Volatility (3Y)" hint="Annualised standard deviation of daily NAV changes">{pct(f.volatility_3y)}</Stat>
            <Stat label="Sharpe (3Y)" hint="Return above the risk-free rate per unit of volatility. Higher is better.">{num(f.sharpe_3y)}</Stat>
            <Stat label="Sortino (3Y)" hint="Like Sharpe, but only penalises downside swings">{num(f.sortino_3y)}</Stat>
            <Stat label="Max drawdown (3Y)" hint="Largest peak-to-trough fall in 3 years">{pct(f.max_drawdown_3y)}</Stat>
            <Stat label="Positive 1Y periods" hint="Share of rolling 1-year windows in the last 3 years that ended with a gain">{pct(f.rolling_1y_positive_pct, 0)}</Stat>
          </dl>
          <p className="text-xs text-slate-400">Since {f.inception_date && new Date(f.inception_date + 'T00:00').getFullYear()} (Direct plan, Growth option). Expense ratio isn’t in the free NAV feed; check the AMC factsheet.</p>
        </div>
      )}
    </DetailDrawer>
  )
}

export default function FundsTab() {
  const [items, setItems] = useState<Fund[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<SortState>({ key: 'cagr_3y', order: 'desc' })
  const [open, setOpen] = useState<number | null>(null)

  useEffect(() => {
    api.get('/market/funds', { params: { category: category || undefined, sort: sort.key, order: sort.order } })
      .then((r) => { setItems(r.data.items); setCategories(r.data.categories) })
  }, [category, sort])

  const h = (label: string, k: string, title?: string) => <SortHeader label={label} k={k} sort={sort} onSort={setSort} title={title} />

  return (
    <div className="card overflow-hidden p-0">
      <div className="flex flex-wrap gap-2 p-4" role="group" aria-label="Fund category">
        {['', ...categories].map((c) => (
          <button key={c || 'all'} onClick={() => setCategory(c)} aria-pressed={category === c}
            className={`rounded-full border px-3 py-1 text-sm ${category === c ? 'border-brand-600 bg-brand-50 font-semibold text-brand-700' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>
            {c || 'All'}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-y border-slate-200 bg-slate-50 text-xs text-slate-500">
            <tr>
              <SortHeader label="Fund" k="name" sort={sort} onSort={setSort} align="left" />
              {h('1Y', 'return_1y')}{h('3Y CAGR', 'cagr_3y')}{h('5Y CAGR', 'cagr_5y')}
              {h('Vol', 'volatility_3y', 'Annualised volatility, 3 years')}{h('Sharpe', 'sharpe_3y', '3-year Sharpe ratio')}
              {h('Max DD', 'max_drawdown_3y', 'Max drawdown, 3 years')}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((f) => (
              <tr key={f.scheme_code} className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(f.scheme_code)}>
                <td className="px-3 py-2.5">
                  <button className="text-left" onClick={(e) => { e.stopPropagation(); setOpen(f.scheme_code) }}>
                    <span className="block font-medium text-slate-800">{f.name.replace(/\s*-\s*Direct Plan.*$/i, '').replace(/\s*\(erstwhile.*?\)/i, '')}</span>
                    <span className="text-xs text-slate-400">{f.category} · {f.fund_house}</span>
                  </button>
                </td>
                <td className="px-3 py-2.5 text-right"><Change value={f.return_1y} /></td>
                <td className="px-3 py-2.5 text-right"><Change value={f.cagr_3y} /></td>
                <td className="px-3 py-2.5 text-right"><Change value={f.cagr_5y} /></td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{pct(f.volatility_3y)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{num(f.sharpe_3y)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{pct(f.max_drawdown_3y)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open != null && <FundDetail code={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
