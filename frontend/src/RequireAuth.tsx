import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { BrailleSpinner } from './components/Ui'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <main className="content-page"><BrailleSpinner /> restoring session</main>
  if (!user) return <Navigate to="/" replace state={{ from: location.pathname }} />
  return children
}
