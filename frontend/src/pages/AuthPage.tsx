import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../lib/api'

export default function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { login, signup } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const isSignup = mode === 'signup'

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const user = isSignup ? await signup(fullName, email, password) : await login(email, password)
      const from = (location.state as { from?: { pathname: string } })?.from?.pathname
      navigate(user.has_profile ? from ?? '/dashboard' : '/onboarding', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-gradient-to-br from-brand-50 to-slate-100 px-4">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold text-brand-700">Wealth Wise</h1>
        <p className="mb-6 mt-1 text-sm text-slate-500">
          {isSignup ? 'Create your account to get a personalised financial plan.' : 'Welcome back. Log in to continue.'}
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          {isSignup && (
            <div>
              <label className="label" htmlFor="name">Full name</label>
              <input id="name" className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </div>
          )}
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" className="input" minLength={8} value={password}
              onChange={(e) => setPassword(e.target.value)} required />
            {isSignup && <p className="mt-1 text-xs text-slate-400">At least 8 characters.</p>}
          </div>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>{busy ? 'Please wait…' : isSignup ? 'Create account' : 'Log in'}</button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-500">
          {isSignup ? <>Already have an account? <Link className="font-semibold text-brand-700" to="/login">Log in</Link></>
            : <>New here? <Link className="font-semibold text-brand-700" to="/signup">Create an account</Link></>}
        </p>
      </div>
    </div>
  )
}
