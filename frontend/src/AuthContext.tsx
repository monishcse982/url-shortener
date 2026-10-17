import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import type { User } from 'oidc-client-ts'
import { userManager } from './auth'

type AuthState = { user: User | null; loading: boolean; error: string | null; refresh: () => Promise<void> }
const AuthContext = createContext<AuthState | null>(null)

async function currentUser() {
  const current = await userManager.getUser()
  return current?.expired ? userManager.signinSilent() : current
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setUser(await currentUser())
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not restore your session')
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void currentUser().then(current => {
      setUser(current)
      setLoading(false)
    }).catch(cause => {
      setError(cause instanceof Error ? cause.message : 'Could not restore your session')
      setLoading(false)
    })
    const onLoaded = (current: User) => { setUser(current); setError(null) }
    const onUnloaded = () => setUser(null)
    userManager.events.addUserLoaded(onLoaded)
    userManager.events.addUserUnloaded(onUnloaded)
    const onExpired = () => { void userManager.signinSilent().then(current => current ? onLoaded(current) : onUnloaded()).catch(onUnloaded) }
    userManager.events.addAccessTokenExpired(onExpired)
    return () => {
      userManager.events.removeUserLoaded(onLoaded)
      userManager.events.removeUserUnloaded(onUnloaded)
      userManager.events.removeAccessTokenExpired(onExpired)
    }
  }, [])

  return <AuthContext.Provider value={{ user, loading, error, refresh }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider missing')
  return value
}
