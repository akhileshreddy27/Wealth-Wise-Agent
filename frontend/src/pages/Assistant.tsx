import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, errorMessage, type AgentStatus, type ChatReply, type ChatTurn } from '../lib/api'
import Markdown from '../components/Markdown'

const SUGGESTIONS = [
  'Explain my investment plan in simple words',
  'Where is my money going this month?',
  'How much SIP do I need for ₹20 lakh in 8 years?',
  'Which large-cap or index fund ranks best, and why?',
  'What are the best FD rates for 2 years?',
]
const TOOL_LABEL: Record<string, string> = {
  get_financial_snapshot: 'your profile', get_investment_plan: 'your plan', get_stock_scores: 'stock scores',
  lookup_stock: 'stock lookup', get_fund_rankings: 'fund rankings', get_fd_options: 'FD rates',
  plan_goal_sip: 'goal planner', get_expense_summary: 'your expenses',
}

interface Turn extends ChatTurn { meta?: Omit<ChatReply, 'reply'> }

export default function Assistant() {
  const [status, setStatus] = useState<AgentStatus | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => { api.get<AgentStatus>('/agent/status').then((r) => setStatus(r.data)) }, [])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns, busy])

  const send = async (text: string) => {
    const q = text.trim()
    if (!q || busy) return
    const history: Turn[] = [...turns, { role: 'user', content: q }]
    setTurns(history); setInput(''); setBusy(true); setError('')
    try {
      // Send only the last 10 turns: enough context, and it keeps free-tier token use low.
      const { data } = await api.post<ChatReply>('/agent/chat', { messages: history.slice(-10).map(({ role, content }) => ({ role, content })) })
      const { reply, ...meta } = data
      setTurns([...history, { role: 'assistant', content: reply, meta }])
    } catch (e) {
      setError(errorMessage(e))
      setTurns(turns)   // put the question back so it can be retried
      setInput(q)
    } finally {
      setBusy(false)
    }
  }
  const onSubmit = (e: FormEvent) => { e.preventDefault(); send(input) }

  if (status && !status.enabled) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-bold">Assistant</h1>
        <div className="card space-y-3 text-sm text-slate-700">
          <p className="font-semibold">The AI assistant isn’t set up yet.</p>
          <p>{status.reason}</p>
          <ol className="list-decimal space-y-1 pl-5">
            <li>Create a free key at <a className="text-brand-700 underline" href="https://console.groq.com/keys" target="_blank" rel="noreferrer">console.groq.com/keys</a>.</li>
            <li>Add <code className="rounded bg-slate-100 px-1">GROQ_API_KEY=…</code> to <code>backend/.env</code> and restart the backend.</li>
          </ol>
          <p className="text-slate-500">Everything else in Wealth Wise works without it.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold">Assistant</h1>
        <p className="text-sm text-slate-500">
          Ask about your plan, spending, funds, stocks or FDs. Answers use your data and the app’s calculations; every figure is checked.
          {status?.model && <span className="text-slate-400"> · {status.provider} / {status.model}</span>}
        </p>
      </div>

      <div className="card min-h-[24rem] space-y-4" aria-live="polite">
        {turns.length === 0 && (
          <div>
            <p className="mb-3 text-sm text-slate-500">Try asking:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} className="rounded-full border border-slate-300 px-3 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-50">{s}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => t.role === 'user' ? (
          <div key={i} className="flex justify-end">
            <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2 text-sm text-white">{t.content}</p>
          </div>
        ) : (
          <div key={i} className="max-w-[90%] text-sm leading-relaxed text-slate-700">
            <Markdown text={t.content} />
            {t.meta && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                {[...new Set(t.meta.tool_calls.map((c) => c.name))].map((n) => (
                  <span key={n} className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">⚙ {TOOL_LABEL[n] ?? n}</span>
                ))}
                {t.meta.grounded
                  ? <span className="text-emerald-700">✓ figures verified</span>
                  : <span className="text-amber-700">! couldn’t verify: {t.meta.unverified.join(', ')}. Treat these with caution.</span>}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="text-sm text-slate-400">Thinking…</p>}
        <div ref={end} />
      </div>

      {error && <p className="text-sm text-red-700">{error}</p>}
      <form onSubmit={onSubmit} className="flex gap-2">
        <label htmlFor="ask" className="sr-only">Your question</label>
        <input id="ask" className="input" value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000}
          placeholder="e.g. Can I afford a ₹15 lakh car in 4 years?" disabled={busy} />
        <button className="btn-primary" disabled={busy || !input.trim()}>Ask</button>
      </form>
      <p className="text-xs text-slate-400">Educational assistant, not SEBI-registered advice. AI can make mistakes; check figures against the Recommendations page.</p>
    </div>
  )
}
