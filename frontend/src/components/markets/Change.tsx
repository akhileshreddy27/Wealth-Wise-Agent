import { pct } from '../../lib/api'

/** A return with an arrow, so gain/loss never relies on colour alone. */
export default function Change({ value, digits = 1 }: { value: number | null | undefined; digits?: number }) {
  if (value == null) return <span className="text-slate-400">—</span>
  const up = value > 0, flat = value === 0
  return (
    <span className={`whitespace-nowrap tabular-nums ${flat ? 'text-slate-600' : up ? 'text-emerald-700' : 'text-red-700'}`}>
      {flat ? '' : up ? '▲ ' : '▼ '}{pct(Math.abs(value), digits)}
    </span>
  )
}
