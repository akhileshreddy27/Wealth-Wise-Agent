export interface SortState { key: string; order: 'asc' | 'desc' }

export default function SortHeader({ label, k, sort, onSort, align = 'right', title }: {
  label: string; k: string; sort: SortState; onSort: (s: SortState) => void; align?: 'left' | 'right'; title?: string
}) {
  const active = sort.key === k
  return (
    <th className={`px-3 py-2 font-medium ${align === 'right' ? 'text-right' : 'text-left'}`} title={title}
      aria-sort={active ? (sort.order === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button className={`inline-flex items-center gap-1 uppercase tracking-wide hover:text-slate-800 ${active ? 'text-slate-800' : ''}`}
        onClick={() => onSort({ key: k, order: active && sort.order === 'desc' ? 'asc' : 'desc' })}>
        {label}<span className="text-[10px]">{active ? (sort.order === 'desc' ? '▼' : '▲') : ''}</span>
      </button>
    </th>
  )
}
