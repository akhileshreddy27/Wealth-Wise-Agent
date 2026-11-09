import type { Asset } from '../../lib/api'

/** Asset classes in fixed chart-palette order (series 1-4). */
export const ASSETS: { key: Asset; label: string; color: string; hint: string }[] = [
  { key: 'equity', label: 'Equity', color: 'var(--series-1)', hint: 'Equity funds and stocks: growth, with ups and downs' },
  { key: 'debt', label: 'Debt funds', color: 'var(--series-2)', hint: 'Bond funds: steadier, withdraw any time' },
  { key: 'fd', label: 'Fixed deposits', color: 'var(--series-3)', hint: 'Bank FDs: guaranteed rate, fixed tenure' },
  { key: 'liquid', label: 'Liquid', color: 'var(--series-4)', hint: 'Liquid funds: parking money for near-term needs' },
]
