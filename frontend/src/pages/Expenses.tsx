import { useCallback, useEffect, useState } from 'react'
import {
  api, currentMonth, inr, monthLabel, shiftMonth,
  type Budget, type Categories, type Insights, type Summary, type Transaction,
} from '../lib/api'
import TransactionForm from '../components/expenses/TransactionForm'
import CsvImport from '../components/expenses/CsvImport'
import BudgetEditor from '../components/expenses/BudgetEditor'
import InsightList from '../components/expenses/InsightList'
import { BucketBar, CategoryBars, TrendChart } from '../components/expenses/Charts'

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'good' | 'bad' }) {
  return (
    <div className="card py-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{value}</p>
      {sub && <p className={`mt-0.5 text-xs ${tone === 'bad' ? 'text-red-700' : tone === 'good' ? 'text-brand-700' : 'text-slate-400'}`}>{sub}</p>}
    </div>
  )
}

export default function Expenses() {
  const [month, setMonth] = useState(currentMonth())
  const [categories, setCategories] = useState<Categories | null>(null)
  const [txns, setTxns] = useState<Transaction[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [insights, setInsights] = useState<Insights | null>(null)
  const [budgets, setBudgets] = useState<Budget[]>([])
  const [editing, setEditing] = useState<Transaction | null | undefined>(undefined) // undefined = closed, null = new
  const [budgetOpen, setBudgetOpen] = useState(false)

  useEffect(() => { api.get<Categories>('/transactions/categories').then((r) => setCategories(r.data)) }, [])

  const load = useCallback(async () => {
    const [t, s, i, b] = await Promise.all([
      api.get<Transaction[]>('/transactions', { params: { month } }),
      api.get<Summary>('/expenses/summary', { params: { month } }),
      api.get<Insights>('/expenses/insights', { params: { month } }),
      api.get<Budget[]>('/budgets'),
    ])
    setTxns(t.data); setSummary(s.data); setInsights(i.data); setBudgets(b.data)
  }, [month])

  useEffect(() => { load() }, [load])

  const remove = async (t: Transaction) => {
    if (!confirm(`Delete "${t.note || 'transaction'}" (${inr(t.amount)})?`)) return
    await api.delete(`/transactions/${t.id}`)
    load()
  }

  const catLabel = (t: Transaction) => categories?.[t.kind][t.category]?.label ?? t.category
  const isFuture = month >= currentMonth()

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Expenses</h1>
          <div className="mt-1 flex items-center gap-1 text-sm">
            <button className="btn-ghost px-2 py-1" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">‹</button>
            <span className="min-w-32 text-center font-medium text-slate-700">{monthLabel(month)}</span>
            <button className="btn-ghost px-2 py-1" disabled={isFuture} onClick={() => setMonth(shiftMonth(month, 1))} aria-label="Next month">›</button>
          </div>
        </div>
        <div className="flex items-start gap-2">
          <CsvImport onImported={load} />
          <button className="btn-primary" onClick={() => setEditing(null)} disabled={!categories}>+ Add transaction</button>
        </div>
      </div>

      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="Income" value={inr(summary.income_base)} sub={summary.income_is_estimate ? 'From your profile (none logged)' : 'Logged this month'} />
          <Kpi label="Spent" value={inr(summary.expense)} sub={`${txns.filter((t) => t.kind === 'expense').length} transactions`} />
          <Kpi label="Saved" value={inr(summary.net)}
            sub={summary.savings_rate != null ? `${(summary.savings_rate * 100).toFixed(0)}% savings rate${summary.invested ? ` · incl. ${inr(summary.invested)} invested` : ''}` : undefined}
            tone={summary.net < 0 ? 'bad' : summary.savings_rate != null && summary.savings_rate >= 0.2 ? 'good' : undefined} />
          <Kpi label="Could save" value={inr(insights?.potential_monthly_saving ?? 0)} sub="Per month, from the insights below" tone="good" />
        </div>
      )}

      {summary && (
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="space-y-6 lg:col-span-3">
            <InsightList data={insights} />
            <TrendChart data={summary.trend} />
          </div>
          <div className="space-y-6 lg:col-span-2">
            <BucketBar summary={summary} />
            <CategoryBars summary={summary} onEditBudgets={() => setBudgetOpen(true)} />
          </div>
        </div>
      )}

      <div className="card overflow-hidden p-0">
        <h2 className="px-6 pt-5 font-semibold">Transactions</h2>
        {txns.length === 0 ? (
          <p className="px-6 pb-6 pt-2 text-sm text-slate-500">No transactions in {monthLabel(month)}. Add one or import a CSV.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="mt-3 w-full text-sm">
              <thead className="border-y border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-6 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2 font-medium">Category</th>
                  <th className="px-3 py-2 font-medium">Via</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                  <th className="px-6 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {txns.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-6 py-2.5 text-slate-500">
                      {new Date(t.date + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                    </td>
                    <td className="px-3 py-2.5 text-slate-800">{t.note || <span className="text-slate-400">—</span>}</td>
                    <td className="px-3 py-2.5"><span className="whitespace-nowrap rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{catLabel(t)}</span></td>
                    <td className="px-3 py-2.5 uppercase text-xs text-slate-400">{t.payment_mode}</td>
                    <td className={`whitespace-nowrap px-3 py-2.5 text-right font-medium ${t.kind === 'income' ? 'text-brand-700' : 'text-slate-800'}`}>
                      {t.kind === 'income' ? '+' : '−'}{inr(t.amount)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-2.5 text-right">
                      <button className="text-xs font-medium text-slate-500 hover:text-brand-700" onClick={() => setEditing(t)}>Edit</button>
                      <button className="ml-3 text-xs font-medium text-slate-500 hover:text-red-700" onClick={() => remove(t)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editing !== undefined && categories && (
        <TransactionForm categories={categories} initial={editing} onClose={() => setEditing(undefined)}
          onSaved={() => { setEditing(undefined); load() }} />
      )}
      {budgetOpen && categories && (
        <BudgetEditor categories={categories} budgets={budgets} onClose={() => setBudgetOpen(false)}
          onSaved={() => { setBudgetOpen(false); load() }} />
      )}
    </div>
  )
}
