import { useRef, useState } from 'react'
import { api, errorMessage } from '../../lib/api'

export default function CsvImport({ onImported }: { onImported: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const upload = async (file: File) => {
    setBusy(true); setMsg(null)
    const fd = new FormData()
    fd.append('file', file)
    try {
      const { data } = await api.post('/transactions/import', fd)
      const parts = [`Imported ${data.imported}`]
      if (data.skipped) parts.push(`${data.skipped} duplicates skipped`)
      if (data.ai_categorized) parts.push(`${data.ai_categorized} categorised by AI`)
      if (data.errors.length) parts.push(`${data.errors.length} rows had errors (${data.errors[0]})`)
      setMsg({ ok: data.errors.length === 0, text: parts.join(' · ') })
      onImported()
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) })
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <input ref={input} type="file" accept=".csv,text/csv" className="hidden"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      <button className="btn-ghost border border-slate-300" disabled={busy} onClick={() => input.current?.click()}
        title="Columns: date, description, amount (or debit/credit). Categories are auto-detected.">
        {busy ? 'Importing…' : 'Import CSV'}
      </button>
      {msg && <p className={`max-w-xs text-right text-xs ${msg.ok ? 'text-brand-700' : 'text-amber-700'}`}>{msg.text}</p>}
    </div>
  )
}
