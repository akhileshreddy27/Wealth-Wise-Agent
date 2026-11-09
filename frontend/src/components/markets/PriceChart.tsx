import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts'
import type { PricePoint, Range } from '../../lib/api'

const S1 = 'var(--series-1)', S2 = 'var(--series-2)'
const RANGES: Range[] = ['1m', '6m', '1y', '3y', '5y']

/** Both series indexed to 100 at the start of the range so they share one axis. */
function indexTo100(points: PricePoint[], benchmark: PricePoint[]) {
  if (!points.length) return []
  const bench = new Map(benchmark.map((p) => [p.date, p.value]))
  const firstBench = benchmark.find((p) => p.date >= points[0].date)?.value
  const base = points[0].value
  let lastBench: number | undefined
  return points.map((p) => {
    const b = bench.get(p.date) ?? lastBench
    lastBench = b
    return {
      date: p.date,
      raw: p.value,
      asset: (p.value / base) * 100,
      bench: b != null && firstBench ? (b / firstBench) * 100 : null,
    }
  })
}

const fmtDate = (d: string, long = false) =>
  new Date(d + 'T00:00').toLocaleDateString('en-IN', long ? { day: 'numeric', month: 'short', year: 'numeric' } : { month: 'short', year: '2-digit' })

export default function PriceChart({ history, benchmark, label, range, onRange, valueLabel = 'Price' }: {
  history: PricePoint[]; benchmark: PricePoint[]; label: string; range: Range; onRange: (r: Range) => void; valueLabel?: string
}) {
  const data = useMemo(() => indexTo100(history, benchmark), [history, benchmark])
  const last = data.length ? data[data.length - 1] : undefined

  const Tip = ({ active, payload }: TooltipProps<number, string>) => {
    if (!active || !payload?.length) return null
    const d = payload[0].payload as (typeof data)[number]
    return (
      <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
        <p className="mb-1 font-semibold text-slate-700">{fmtDate(d.date, true)}</p>
        <p className="flex items-center gap-2 text-slate-600"><i className="h-0.5 w-3" style={{ background: S1 }} />{label}
          <span className="ml-auto pl-4 font-medium text-slate-800">{(d.asset - 100 >= 0 ? '+' : '')}{(d.asset - 100).toFixed(1)}%</span></p>
        {d.bench != null && (
          <p className="flex items-center gap-2 text-slate-600"><i className="h-0.5 w-3" style={{ background: S2 }} />NIFTY 50
            <span className="ml-auto pl-4 font-medium text-slate-800">{(d.bench - 100 >= 0 ? '+' : '')}{(d.bench - 100).toFixed(1)}%</span></p>
        )}
        <p className="mt-1 text-slate-400">{valueLabel} ₹{d.raw.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-4 text-xs text-slate-600">
          <span className="flex items-center gap-1.5"><i className="h-0.5 w-4" style={{ background: S1 }} />{label}</span>
          <span className="flex items-center gap-1.5"><i className="h-0.5 w-4" style={{ background: S2 }} />NIFTY 50</span>
        </div>
        <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs" role="group" aria-label="Chart range">
          {RANGES.map((r) => (
            <button key={r} onClick={() => onRange(r)} aria-pressed={r === range}
              className={`rounded-md px-2.5 py-1 font-medium uppercase ${r === range ? 'bg-white shadow-sm' : 'text-slate-500'}`}>{r}</button>
          ))}
        </div>
      </div>
      {data.length < 2 ? <p className="py-16 text-center text-sm text-slate-500">No price history for this range.</p> : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ left: -12, right: 48, top: 8 }}>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis dataKey="date" tickFormatter={(d) => fmtDate(d)} minTickGap={40} tickLine={false} axisLine={false}
                tick={{ fontSize: 12, fill: 'var(--chart-axis)' }} />
              <YAxis domain={['auto', 'auto']} tickFormatter={(v) => `${Math.round(v - 100)}%`} tickLine={false} axisLine={false}
                width={52} tick={{ fontSize: 12, fill: 'var(--chart-axis)' }} />
              <Tooltip content={<Tip />} cursor={{ stroke: '#94a3b8', strokeWidth: 1 }} />
              <Line type="monotone" dataKey="bench" stroke={S2} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
              <Line type="monotone" dataKey="asset" stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false}
                activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {last && (
        <p className="mt-1 text-xs text-slate-500">
          Over this period: {label} {(last.asset - 100 >= 0 ? '+' : '')}{(last.asset - 100).toFixed(1)}%
          {last.bench != null && <> · NIFTY 50 {(last.bench - 100 >= 0 ? '+' : '')}{(last.bench - 100).toFixed(1)}%</>}
        </p>
      )}
    </div>
  )
}
