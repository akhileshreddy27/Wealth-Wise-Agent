import { useState } from 'react'
import { api, errorMessage, type PlanExplanation } from '../../lib/api'
import Markdown from '../Markdown'

/** "Explain my plan": AI explanation of the plan, or a rule-based summary when AI is off or unverifiable. */
export default function ExplainCard({ regime }: { regime: 'new' | 'old' }) {
  const [data, setData] = useState<PlanExplanation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = () => {
    setBusy(true); setError('')
    api.get<PlanExplanation>('/agent/explain-plan', { params: { tax_regime: regime } })
      .then((r) => setData(r.data))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setBusy(false))
  }

  return (
    <div className="card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Explain my plan</h2>
          <p className="text-sm text-slate-500">A plain-language walkthrough. Every figure is checked against the numbers above.</p>
        </div>
        <button className="btn-primary" onClick={run} disabled={busy}>{busy ? 'Thinking…' : data ? 'Explain again' : 'Explain'}</button>
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {data && (
        <div className="mt-4 border-t border-slate-100 pt-4 text-sm leading-relaxed text-slate-700">
          <p className="mb-3">
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${data.source === 'ai' ? 'bg-brand-50 text-brand-700' : 'bg-slate-100 text-slate-600'}`}>
              {data.source === 'ai' ? '✦ AI explanation · figures verified' : 'Rule-based summary'}
            </span>
            {data.reason && <span className="ml-2 text-xs text-slate-400">{data.reason}</span>}
          </p>
          <Markdown text={data.text} />
        </div>
      )}
    </div>
  )
}
