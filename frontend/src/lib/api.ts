import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'ww_token'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export function errorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join(', ')
    return err.message
  }
  return 'Something went wrong'
}

// ---- Types mirroring the backend schemas ----
export interface User { id: number; email: string; full_name: string; has_profile: boolean }

export interface QuestionOption { value: number; label: string }
export interface Question { id: string; question: string; options: QuestionOption[] }

export interface ProfileInput {
  age: number
  monthly_income: number
  monthly_expenses: number
  current_savings: number
  dependents: number
  horizon_years: number
  goals: string[]
  risk_answers: Record<string, number>
}

export interface Profile extends ProfileInput {
  risk_score: number
  risk_category: 'conservative' | 'moderate' | 'aggressive'
  updated_at: string | null
  snapshot: {
    monthly_surplus: number
    savings_rate: number
    emergency_fund_target: number
    emergency_fund_months: number | null
    emergency_fund_ok: boolean
  }
}

export const inr = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)

// ---- Phase 2: expenses ----
export type TxnKind = 'expense' | 'income'
export interface Transaction {
  id: number
  kind: TxnKind
  amount: number
  category: string
  date: string
  note: string
  payment_mode: string
}
export type TransactionInput = Omit<Transaction, 'id' | 'category'> & { category: string | null }

export interface CategoryMeta { label: string; bucket?: 'needs' | 'wants' | 'savings' }
export interface Categories { expense: Record<string, CategoryMeta>; income: Record<string, CategoryMeta> }

export interface CategorySummary {
  category: string; label: string; bucket: 'needs' | 'wants' | 'savings'
  amount: number; share: number; budget: number | null; budget_used: number | null
}
export interface Summary {
  month: string
  income: number
  income_is_estimate: boolean
  income_base: number
  expense: number
  net: number
  invested: number
  savings_rate: number | null
  categories: CategorySummary[]
  buckets: { needs: number; wants: number; savings: number }
  bucket_share: { needs: number | null; wants: number | null; savings: number | null }
  daily: { date: string; amount: number }[]
  trend: { month: string; income: number; expense: number }[]
}
export interface Insight {
  type: string
  severity: 'danger' | 'warning' | 'info' | 'success'
  title: string
  detail: string
  potential_saving: number
  category: string | null
}
export interface Insights {
  month: string
  insights: Insight[]
  potential_monthly_saving: number
  recurring: { name: string; category: string; monthly_amount: number; months_seen: number }[]
}
export interface Budget { category: string; monthly_limit: number }

export const currentMonth = () => new Date().toISOString().slice(0, 7)
export const shiftMonth = (m: string, delta: number) => {
  const [y, mo] = m.split('-').map(Number)
  const d = new Date(y, mo - 1 + delta, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
export const monthLabel = (m: string, style: 'long' | 'short' = 'long') => {
  const [y, mo] = m.split('-').map(Number)
  return new Date(y, mo - 1, 1).toLocaleDateString('en-IN', { month: style, year: style === 'long' ? 'numeric' : '2-digit' })
}
export const inrCompact = (n: number) =>
  n >= 1e7 ? `₹${(n / 1e7).toFixed(1)}Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)}L` : n >= 1e3 ? `₹${(n / 1e3).toFixed(0)}k` : `₹${Math.round(n)}`

// ---- Phase 3: market data ----
export interface Stock {
  symbol: string; name: string; sector: string | null; industry: string | null
  price: number | null; change_pct_1d: number | null; market_cap: number | null
  pe: number | null; pb: number | null; roe: number | null; debt_to_equity: number | null
  dividend_yield: number | null; profit_margin: number | null; revenue_growth: number | null; earnings_growth: number | null
  return_1m: number | null; return_6m: number | null; return_1y: number | null; cagr_3y: number | null; cagr_5y: number | null
  volatility_1y: number | null; max_drawdown_1y: number | null; sharpe_1y: number | null; beta_1y: number | null
  high_52w: number | null; low_52w: number | null; updated_at: string
}
export interface Fund {
  scheme_code: number; name: string; fund_house: string | null; category: string; scheme_category: string | null
  nav: number | null; nav_date: string | null; inception_date: string | null
  return_1y: number | null; cagr_3y: number | null; cagr_5y: number | null
  volatility_3y: number | null; sharpe_3y: number | null; sortino_3y: number | null; max_drawdown_3y: number | null
  rolling_1y_positive_pct: number | null; updated_at: string
}
export interface FdQuote {
  id: number; bank: string; bank_type: string; min_days: number; max_days: number; rate: number; senior_rate: number
  tax_saver: boolean; as_of: string; source_url: string | null; applied_rate: number; maturity_value: number; interest: number
}
export interface PricePoint { date: string; value: number }
export interface MarketStatus {
  stocks: { count: number; last_refresh: { status: string; finished_at: string; ok: number; failures: string[] } | null }
  funds: { count: number; last_refresh: { status: string; finished_at: string; ok: number; failures: string[] } | null }
  fds: { count: number; as_of: string | null; indicative: boolean }
}
export type Range = '1m' | '6m' | '1y' | '3y' | '5y'

/** 0.1234 -> "12.3%" (signed adds a + for gains). */
export const pct = (x: number | null | undefined, digits = 1, signed = false) =>
  x == null ? '—' : `${signed && x > 0 ? '+' : ''}${(x * 100).toFixed(digits)}%`
export const num = (x: number | null | undefined, digits = 2) => (x == null ? '—' : x.toFixed(digits))
/** Backend timestamps from SQLite come without a zone; they are UTC. */
export const utcDate = (s: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`)
/** Market cap in the way Indian markets quote it: ₹17.92L Cr (lakh crore) or ₹45,210 Cr. */
export const mcap = (n: number | null | undefined) => {
  if (n == null) return '—'
  const cr = n / 1e7
  return cr >= 1e5 ? `₹${(cr / 1e5).toFixed(2)}L Cr` : `₹${Math.round(cr).toLocaleString('en-IN')} Cr`
}
export const shortName = (name: string) => name.replace(/\s+(Limited|Ltd\.?)$/i, '')
