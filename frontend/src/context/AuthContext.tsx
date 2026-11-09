import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, tokenStore, type User } from '../lib/api'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  signup: (fullName: string, email: string, password: string) => Promise<User>
  logout: () => void
  refresh: () => Promise<User | null>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) { setUser(null); return null }
    try {
      const { data } = await api.get<User>('/auth/me')
      setUser(data)
      return data
    } catch {
      tokenStore.clear()
      setUser(null)
      return null
    }
  }, [])

  useEffect(() => { refresh().finally(() => setLoading(false)) }, [refresh])

  const login = async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password })
    tokenStore.set(data.access_token)
    return (await refresh())!
  }

  const signup = async (full_name: string, email: string, password: string) => {
    const { data } = await api.post('/auth/signup', { full_name, email, password })
    tokenStore.set(data.access_token)
    return (await refresh())!
  }

  const logout = () => { tokenStore.clear(); setUser(null) }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
