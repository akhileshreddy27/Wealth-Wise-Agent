import { inr, type Insights } from '../../lib/api'

const STYLE = {
  danger:  { box: 'border-red-200 bg-red-50',     icon: '⚠', iconCls: 'text-red-700',   label: 'Action needed' },
  warning: { box: 'border-amber-200 bg-amber-50', icon: '!', iconCls: 'text-amber-700', label: 'Watch' },
  info:    { box: 'border-slate-200 bg-white',    icon: 'i', iconCls: 'text-sky-700',   label: 'Tip' },
  success: { box: 'border-emerald-200 bg-emerald-50', icon: '✓', iconCls: 'text-emerald-700', label: 'Good' },
}

export default function InsightList({ data }: { data: Insights | null }) {
  if (!data) return null
  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Savings insights</h2>
        {data.potential_monthly_saving > 0 && (
          <p className="text-sm text-slate-600">
            You could save up to <span className="font-semibold text-brand-700">{inr(data.potential_monthly_saving)}/month</span>
          </p>
        )}
      </div>
      {data.insights.length === 0 ? (
        <p className="text-sm text-slate-500">Add some transactions to get personalised savings tips.</p>
      ) : (
        <ul className="space-y-2">
          {data.insights.map((i, idx) => {
            const s = STYLE[i.severity]
            return (
              <li key={idx} className={`flex gap-3 rounded-xl border p-3 ${s.box}`}>
                <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-current text-xs font-bold ${s.iconCls}`} aria-label={s.label}>{s.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-800">{i.title}</p>
                  <p className="text-sm text-slate-600">{i.detail}</p>
                </div>
                {i.potential_saving > 0 && (
                  <span className="shrink-0 self-center whitespace-nowrap text-xs font-semibold text-brand-700">save {inr(i.potential_saving)}</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
