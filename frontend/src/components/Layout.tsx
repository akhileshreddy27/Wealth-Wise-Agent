import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/recommendations', label: 'Recommendations' },
  { to: '/expenses', label: 'Expenses' },
  { to: '/markets', label: 'Markets' },
  { to: '/onboarding', label: 'My Profile' },
  // Coming in later phases:
  // { to: '/learn', label: 'Learn' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/dashboard" className="text-lg font-bold text-brand-700">Wealth Wise</Link>
          <nav className="flex items-center gap-1">
            {navItems.map((n) => (
              <NavLink key={n.to} to={n.to}
                className={({ isActive }) => `rounded-lg px-3 py-1.5 text-sm ${isActive ? 'bg-brand-50 font-semibold text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`}>
                {n.label}
              </NavLink>
            ))}
            <span className="mx-2 hidden text-sm text-slate-400 sm:inline">{user?.full_name}</span>
            <button className="btn-ghost" onClick={() => { logout(); navigate('/login') }}>Log out</button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8"><Outlet /></main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-slate-400">
        Wealth Wise is an educational tool, not SEBI-registered investment advice.
      </footer>
    </div>
  )
}
