import { useState } from 'react'
import { api, errorMessage, type Budget, type Categories } from '../../lib/api'

export default function BudgetEditor({ categories, budgets, onClose, onSaved }: {
  categories: Categories; budgets: Budget[]; onClose: () => void; onSaved: () => void
}) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(budgets.map((b) => [b.category, String(b.monthly_limit)])))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    setBusy(true); setError('')
    try {
      const body = Object.keys(categories.expense).map((c) => ({ category: c, monthly_limit: Number(values[c] || 0) }))
      await api.put('/budgets', body)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 px-4" onMouseDown={onClose}>
      <div className="card flex max-h-[85vh] w-full max-w-md flex-col" onMouseDown={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">Monthly budgets</h2>
        <p className="mb-4 text-sm text-slate-500">Leave blank or 0 for no budget.</p>
        <div className="-mx-2 flex-1 space-y-2 overflow-y-auto px-2">
          {Object.entries(categories.expense).map(([id, c]) => (
            <label key={id} className="flex items-center justify-between gap-4 text-sm">
              <span className="text-slate-700">{c.label}</span>
              <input type="number" min="0" step="100" className="input w-36" placeholder="No budget"
                value={values[id] ?? ''} onChange={(e) => setValues((v) => ({ ...v, [id]: e.target.value }))} />
            </label>
          ))}
        </div>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save budgets'}</button>
        </div>
      </div>
    </div>
  )
}
