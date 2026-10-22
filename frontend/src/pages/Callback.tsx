import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { userManager } from '../auth'
import { useAuth } from '../AuthContext'
import { BrailleSpinner, StepProgress } from '../components/Ui'

export function Callback() {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const started = useRef(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (started.current) return
    started.current = true
    void userManager.signinRedirectCallback().then(async user => {
      await refresh()
      const state = user.state as { returnTo?: string } | undefined
      const returnTo = state?.returnTo?.startsWith('/') && !state.returnTo.startsWith('//') ? state.returnTo : '/links'
      navigate(returnTo, { replace: true })
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Sign in failed'))
  }, [navigate, refresh])
  if (error) return <main className="auth-page auth-state"><p role="alert">{error}</p><Link to="/">try again</Link></main>
  return <main className="auth-page auth-state"><BrailleSpinner /><p>finishing sign in</p><StepProgress step={3} /></main>
}
