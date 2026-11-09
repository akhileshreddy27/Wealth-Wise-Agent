import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import AuthPage from './pages/AuthPage'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Expenses from './pages/Expenses'
import Markets from './pages/Markets'
import Recommendations from './pages/Recommendations'
import Assistant from './pages/Assistant'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/expenses" element={<ProtectedRoute requireProfile><Expenses /></ProtectedRoute>} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/recommendations" element={<ProtectedRoute requireProfile><Recommendations /></ProtectedRoute>} />
            <Route path="/assistant" element={<ProtectedRoute requireProfile><Assistant /></ProtectedRoute>} />
            <Route path="/dashboard" element={<ProtectedRoute requireProfile><Dashboard /></ProtectedRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
