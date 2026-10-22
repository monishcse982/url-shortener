import { lazy, Suspense, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { signIn } from '../auth'
import { useAuth } from '../AuthContext'
import { BrailleSpinner, Button, StatusLine, StepProgress } from '../components/Ui'

const DotOrb = lazy(() => import('../components/DotOrb'))

export function SignIn() {
  const { user, loading, error: authError } = useAuth()
  const location = useLocation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const from = (location.state as { from?: string } | null)?.from || '/links'
  if (loading) return <div className="auth-page auth-state"><Suspense fallback={null}><DotOrb /></Suspense><p>restoring session <BrailleSpinner /></p></div>
  if (user) return <Navigate to={from} replace />
  async function start() {
    setBusy(true)
    setError(null)
    try { await signIn(from) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not start sign in'); setBusy(false) }
  }
  return <main className="auth-page">
    <div className="auth-top"><span>~/zipp</span><span>signed out</span></div>
    <div className="auth-center"><Suspense fallback={<BrailleSpinner />}><DotOrb /></Suspense><h1 className="auth-title">zipp<span className="cursor">_</span></h1><p>short links.<br />full control.</p></div>
    <div className="auth-bottom"><StatusLine error={error || authError} /><Button onClick={start} disabled={busy}>{busy ? <>signing in <BrailleSpinner /></> : '> sign in'}</Button>{busy && <StepProgress step={2} />}<small>redirects to hosted login</small></div>
  </main>
}
