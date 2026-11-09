import { useState, type FormEvent } from 'react'
import { api, errorMessage, type Categories, type Transaction, type TransactionInput, type TxnKind } from '../../lib/api'

const MODES = [['upi', 'UPI'], ['card', 'Card'], ['cash', 'Cash'], ['netbanking', 'Net banking'], ['other', 'Other']]

export default function TransactionForm({ categories, initial, onClose, onSaved }: {
  categories: Categories
  initial?: Transaction | null
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState<TransactionInput>(() => initial
    ? { ...initial }
    : { kind: 'expense', amount: 0, category: null, date: new Date().toISOString().slice(0, 10), note: '', payment_mode: 'upi' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof TransactionInput>(k: K, v: TransactionInput[K]) => setForm((f) => ({ ...f, [k]: v }))
  const cats = categories[form.kind]

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      if (initial) await api.put(`/transactions/${initial.id}`, form)
      else await api.post('/transactions', form)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 px-4" onMouseDown={onClose}>
      <form onSubmit={submit} onMouseDown={(e) => e.stopPropagation()} className="card w-full max-w-md space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{initial ? 'Edit transaction' : 'Add transaction'}</h2>
          <button type="button" className="btn-ghost px-2" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
          {(['expense', 'income'] as TxnKind[]).map((k) => (
            <button type="button" key={k} onClick={() => setForm((f) => ({ ...f, kind: k, category: null }))}
              className={`rounded-md py-1.5 text-sm font-medium capitalize ${form.kind === k ? 'bg-white shadow-sm' : 'text-slate-500'}`}>{k}</button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="amount">Amount (₹)</label>
            <input id="amount" type="number" min="0.01" step="0.01" required className="input"
              value={form.amount || ''} onChange={(e) => set('amount', Number(e.target.value))} />
          </div>
          <div>
            <label className="label" htmlFor="date">Date</label>
            <input id="date" type="date" required className="input" value={form.date} onChange={(e) => set('date', e.target.value)} />
          </div>
        </div>

        <div>
          <label className="label" htmlFor="note">Description</label>
          <input id="note" className="input" placeholder="e.g. Swiggy, Uber, Netflix" maxLength={255}
            value={form.note} onChange={(e) => set('note', e.target.value)} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="category">Category</label>
            <select id="category" className="input" value={form.category ?? ''} onChange={(e) => set('category', e.target.value || null)}>
              <option value="">Auto-detect</option>
              {Object.entries(cats).map(([id, c]) => <option key={id} value={id}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="mode">Paid via</label>
            <select id="mode" className="input" value={form.payment_mode} onChange={(e) => set('payment_mode', e.target.value)}>
              {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        </div>

        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </div>
  )
}
