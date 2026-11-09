import type { ReactNode } from 'react'

/** Tiny, safe renderer for the AI's markdown: **bold**, "- " bullets and paragraphs. No HTML is injected. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i} className="font-semibold text-slate-800">{part.slice(2, -2)}</strong> : part)
}

export default function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []
  const flush = () => {
    if (bullets.length) {
      blocks.push(<ul key={blocks.length} className="list-disc space-y-1 pl-5">{bullets.map((b, i) => <li key={i}>{inline(b)}</li>)}</ul>)
      bullets = []
    }
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const bullet = line.match(/^(?:[-*•]|\d+\.)\s+(.*)$/)
    if (bullet) { bullets.push(bullet[1]); continue }
    flush()
    if (line) blocks.push(<p key={blocks.length}>{inline(line)}</p>)
  }
  flush()
  return <div className="space-y-2">{blocks}</div>
}
