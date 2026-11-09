import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../context/AuthContext'

/** Requires login. If `requireProfile`, users without a profile go to onboarding first. */
export default function ProtectedRoute({ children, requireProfile = false }: { children: ReactNode; requireProfile?: boolean }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <div className="grid min-h-screen place-items-center text-slate-500">Loading…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (requireProfile && !user.has_profile) return <Navigate to="/onboarding" replace />
  return <>{children}</>
}
