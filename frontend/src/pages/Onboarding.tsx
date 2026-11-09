import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api, errorMessage, type Profile, type ProfileInput, type Question } from '../lib/api'

const GOALS: { id: string; label: string }[] = [
  { id: 'emergency_fund', label: 'Emergency fund' },
  { id: 'retirement', label: 'Retirement' },
  { id: 'house', label: 'Buy a house' },
  { id: 'education', label: 'Education' },
  { id: 'car', label: 'Buy a car' },
  { id: 'travel', label: 'Travel' },
  { id: 'wealth_creation', label: 'Wealth creation' },
]

const EMPTY: ProfileInput = {
  age: 25, monthly_income: 0, monthly_expenses: 0, current_savings: 0,
  dependents: 0, horizon_years: 5, goals: [], risk_answers: {},
}

const NUMBER_FIELDS: { key: keyof ProfileInput; label: string; hint?: string; min: number }[] = [
  { key: 'age', label: 'Age', min: 18 },
  { key: 'dependents', label: 'Dependents', hint: 'People who rely on your income', min: 0 },
  { key: 'monthly_income', label: 'Monthly income (₹)', hint: 'Take-home, after tax', min: 0 },
  { key: 'monthly_expenses', label: 'Monthly expenses (₹)', min: 0 },
  { key: 'current_savings', label: 'Current savings (₹)', hint: 'Bank + FDs + investments', min: 0 },
  { key: 'horizon_years', label: 'Investment horizon (years)', hint: 'How long before you need this money', min: 1 },
]

export default function Onboarding() {
  const { refresh } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [form, setForm] = useState<ProfileInput>(EMPTY)
  const [questions, setQuestions] = useState<Question[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [isEdit, setIsEdit] = useState(false)

  useEffect(() => {
    api.get<Question[]>('/profile/questionnaire').then((r) => setQuestions(r.data))
    api.get<Profile>('/profile').then(({ data }) => {
      const { risk_score: _s, risk_category: _c, updated_at: _u, snapshot: _sn, ...input } = data
      setForm(input); setIsEdit(true)
    }).catch(() => { /* no profile yet */ })
  }, [])

  const set = <K extends keyof ProfileInput>(k: K, v: ProfileInput[K]) => setForm((f) => ({ ...f, [k]: v }))
  const toggleGoal = (g: string) =>
    set('goals', form.goals.includes(g) ? form.goals.filter((x) => x !== g) : [...form.goals, g])

  const allAnswered = questions.length > 0 && questions.every((q) => form.risk_answers[q.id])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (step < 3) { setStep((s) => (s + 1) as 2 | 3); return }
    setError(''); setBusy(true)
    try {
      await api.put('/profile', form)
      await refresh()
      navigate('/dashboard')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold">{isEdit ? 'Update your profile' : "Let's build your financial profile"}</h1>
      <p className="mt-1 text-sm text-slate-500">This drives every recommendation Wealth Wise makes for you.</p>

      <ol className="my-6 flex gap-2 text-xs font-medium">
        {['Finances', 'Goals', 'Risk'].map((label, i) => (
          <li key={label} className={`flex-1 rounded-full px-3 py-1.5 text-center ${step > i ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      <form onSubmit={onSubmit} className="card space-y-6">
        {step === 1 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {NUMBER_FIELDS.map((f) => (
              <div key={f.key}>
                <label className="label" htmlFor={f.key}>{f.label}</label>
                <input id={f.key} type="number" className="input" min={f.min} required
                  value={form[f.key] as number}
                  onChange={(e) => set(f.key, Number(e.target.value) as never)} />
                {f.hint && <p className="mt-1 text-xs text-slate-400">{f.hint}</p>}
              </div>
            ))}
          </div>
        )}

        {step === 2 && (
          <div>
            <p className="label">What are you saving for? (pick any)</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {GOALS.map((g) => {
                const on = form.goals.includes(g.id)
                return (
                  <button type="button" key={g.id} onClick={() => toggleGoal(g.id)}
                    className={`rounded-full border px-4 py-1.5 text-sm ${on ? 'border-brand-600 bg-brand-50 font-semibold text-brand-700' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>
                    {g.label}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            {questions.map((q, qi) => (
              <fieldset key={q.id}>
                <legend className="label">{qi + 1}. {q.question}</legend>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {q.options.map((o) => (
                    <label key={o.value}
                      className={`cursor-pointer rounded-lg border px-3 py-2 text-sm ${form.risk_answers[q.id] === o.value ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-slate-300 hover:bg-slate-50'}`}>
                      <input type="radio" className="sr-only" name={q.id} checked={form.risk_answers[q.id] === o.value}
                        onChange={() => set('risk_answers', { ...form.risk_answers, [q.id]: o.value })} />
                      {o.label}
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}
          </div>
        )}

        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <div className="flex justify-between">
          <button type="button" className="btn-ghost" disabled={step === 1} onClick={() => setStep((s) => (s - 1) as 1 | 2)}>Back</button>
          <button className="btn-primary" disabled={busy || (step === 3 && !allAnswered)}>
            {step < 3 ? 'Next' : busy ? 'Saving…' : 'Save profile'}
          </button>
        </div>
      </form>
    </div>
  )
}
