import { useEffect, useState } from 'react'
import { api, mcap, num, pct, shortName, type PricePoint, type Range, type Stock } from '../../lib/api'
import Change from './Change'
import DetailDrawer, { Stat } from './DetailDrawer'
import PriceChart from './PriceChart'
import SortHeader, { type SortState } from './SortHeader'

const inr2 = (n: number | null) => (n == null ? '—' : `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`)

function StockDetail({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [range, setRange] = useState<Range>('1y')
  const [data, setData] = useState<{ stock: Stock; history: PricePoint[]; benchmark: { history: PricePoint[] } } | null>(null)
  useEffect(() => { api.get(`/market/stocks/${encodeURIComponent(symbol)}`, { params: { range } }).then((r) => setData(r.data)) }, [symbol, range])
  const s = data?.stock
  return (
    <DetailDrawer title={s?.name ?? symbol} onClose={onClose}
      subtitle={s && <>NSE: {s.symbol} · {s.sector ?? '—'}{s.industry ? ` · ${s.industry}` : ''}</>}>
      {!s ? <p className="text-slate-500">Loading…</p> : (
        <div className="space-y-6">
          <div className="flex items-baseline gap-3">
            <span className="text-3xl font-bold text-slate-800">{inr2(s.price)}</span>
            <Change value={s.change_pct_1d} digits={2} /><span className="text-xs text-slate-400">today</span>
          </div>
          <PriceChart history={data.history} benchmark={data.benchmark.history} label={s.symbol} range={range} onRange={setRange} />
          <section>
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Returns & risk</h3>
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="1 month"><Change value={s.return_1m} /></Stat>
              <Stat label="6 months"><Change value={s.return_6m} /></Stat>
              <Stat label="1 year"><Change value={s.return_1y} /></Stat>
              <Stat label="3Y CAGR"><Change value={s.cagr_3y} /></Stat>
              <Stat label="Volatility (1Y)" hint="Annualised standard deviation of daily returns">{pct(s.volatility_1y)}</Stat>
              <Stat label="Max drawdown (1Y)" hint="Largest peak-to-trough fall in the last year">{pct(s.max_drawdown_1y)}</Stat>
              <Stat label="Sharpe (1Y)" hint="Return above the risk-free rate per unit of volatility">{num(s.sharpe_1y)}</Stat>
              <Stat label="Beta vs NIFTY" hint="1 = moves with the market; above 1 = swings more">{num(s.beta_1y)}</Stat>
            </dl>
          </section>
          <section>
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Fundamentals</h3>
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="Market cap">{mcap(s.market_cap)}</Stat>
              <Stat label="P/E">{num(s.pe, 1)}</Stat>
              <Stat label="P/B">{num(s.pb, 1)}</Stat>
              <Stat label="ROE">{pct(s.roe)}</Stat>
              <Stat label="Debt / equity">{num(s.debt_to_equity)}</Stat>
              <Stat label="Dividend yield">{pct(s.dividend_yield, 2)}</Stat>
              <Stat label="Profit margin">{pct(s.profit_margin)}</Stat>
              <Stat label="Earnings growth">{pct(s.earnings_growth)}</Stat>
              <Stat label="52-week high">{inr2(s.high_52w)}</Stat>
              <Stat label="52-week low">{inr2(s.low_52w)}</Stat>
            </dl>
          </section>
        </div>
      )}
    </DetailDrawer>
  )
}

export default function StocksTab() {
  const [items, setItems] = useState<Stock[]>([])
  const [sectors, setSectors] = useState<string[]>([])
  const [sector, setSector] = useState('')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState<SortState>({ key: 'market_cap', order: 'desc' })
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    const t = setTimeout(() => {
      api.get('/market/stocks', { params: { sector: sector || undefined, q: q || undefined, sort: sort.key, order: sort.order } })
        .then((r) => { setItems(r.data.items); setSectors(r.data.sectors) })
    }, 200)
    return () => clearTimeout(t)
  }, [sector, q, sort])

  const h = (label: string, k: string, title?: string) => <SortHeader label={label} k={k} sort={sort} onSort={setSort} title={title} />

  return (
    <div className="card overflow-hidden p-0">
      <div className="flex flex-wrap items-center gap-2 p-4">
        <input className="input max-w-xs" placeholder="Search name or symbol" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search stocks" />
        <select className="input w-auto" value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Sector">
          <option value="">All sectors</option>
          {sectors.map((s) => <option key={s}>{s}</option>)}
        </select>
        <span className="ml-auto text-xs text-slate-400">{items.length} NIFTY 50 stocks</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-y border-slate-200 bg-slate-50 text-xs text-slate-500">
            <tr>
              <SortHeader label="Company" k="name" sort={sort} onSort={setSort} align="left" />
              {h('Price', 'price')}{h('1D', 'change_pct_1d')}{h('Mkt cap', 'market_cap')}{h('P/E', 'pe')}{h('ROE', 'roe')}
              {h('1Y', 'return_1y')}{h('3Y CAGR', 'cagr_3y')}{h('Vol', 'volatility_1y', 'Annualised volatility, last year')}{h('Beta', 'beta_1y')}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((s) => (
              <tr key={s.symbol} className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(s.symbol)}>
                <td className="px-3 py-2.5">
                  <button className="text-left" onClick={(e) => { e.stopPropagation(); setOpen(s.symbol) }}>
                    <span className="block font-medium text-slate-800">{shortName(s.name)}</span>
                    <span className="text-xs text-slate-400">{s.symbol} · {s.sector ?? '—'}</span>
                  </button>
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">{inr2(s.price)}</td>
                <td className="px-3 py-2.5 text-right"><Change value={s.change_pct_1d} digits={2} /></td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{mcap(s.market_cap)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{num(s.pe, 1)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{pct(s.roe)}</td>
                <td className="px-3 py-2.5 text-right"><Change value={s.return_1y} /></td>
                <td className="px-3 py-2.5 text-right"><Change value={s.cagr_3y} /></td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{pct(s.volatility_1y)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{num(s.beta_1y)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && <StockDetail symbol={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
