import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, utcDate, type MarketStatus } from '../lib/api'
import StocksTab from '../components/markets/StocksTab'
import FundsTab from '../components/markets/FundsTab'
import FdTab from '../components/markets/FdTab'

const TABS = [
  { id: 'stocks', label: 'Stocks' },
  { id: 'funds', label: 'Mutual funds' },
  { id: 'fds', label: 'Fixed deposits' },
] as const
type Tab = (typeof TABS)[number]['id']

const ago = (iso?: string) => {
  if (!iso) return 'never'
  const mins = Math.round((Date.now() - utcDate(iso).getTime()) / 60000)
  return mins < 60 ? `${Math.max(mins, 1)} min ago` : mins < 1440 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} d ago`
}

export default function Markets() {
  const [params, setParams] = useSearchParams()
  const tab = (TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'stocks') as Tab
  const [status, setStatus] = useState<MarketStatus | null>(null)
  useEffect(() => { api.get<MarketStatus>('/market/status').then((r) => setStatus(r.data)) }, [])

  const empty = status && ((tab === 'stocks' && !status.stocks.count) || (tab === 'funds' && !status.funds.count))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Markets</h1>
          <p className="text-sm text-slate-500">Live data behind your recommendations: NIFTY 50 stocks, popular Direct mutual funds and bank FDs.</p>
        </div>
        {status && (
          <p className="text-xs text-slate-400">
            Stocks updated {ago(status.stocks.last_refresh?.finished_at)} · Funds updated {ago(status.funds.last_refresh?.finished_at)}
          </p>
        )}
      </div>

      <div className="flex gap-1 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setParams({ tab: t.id })}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${tab === t.id ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {empty ? (
        <div className="card text-sm text-slate-600">
          No data yet. Run <code className="rounded bg-slate-100 px-1.5 py-0.5">python -m app.jobs.refresh all</code> in <code>backend/</code>,
          or set <code>ENABLE_SCHEDULER=true</code> to fetch it automatically.
        </div>
      ) : tab === 'stocks' ? <StocksTab /> : tab === 'funds' ? <FundsTab /> : <FdTab />}

      <p className="text-xs text-slate-400">
        Sources: Yahoo Finance (prices, fundamentals), AMFI via mfapi.in (NAVs). Prices are end-of-day; past returns don’t guarantee future returns.
      </p>
    </div>
  )
}
