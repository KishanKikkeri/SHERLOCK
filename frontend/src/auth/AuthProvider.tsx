import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiFetch } from '@/lib/api-client'
import type { TokenResponse, UserOut } from '@/lib/types'
import { useAuthStore } from '@/store/auth-store'

interface AuthContextValue {
  user: UserOut | null
  authMode: 'enabled' | 'disabled' | 'unknown'
  isBooting: boolean
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Boot sequence (see docs/stage-f/02-API-CONTRACTS.md):
 *   1. Stored refresh token? -> POST /auth/refresh, then GET /auth/me
 *      with the new access token.
 *   2. No stored token, or refresh failed -> GET /auth/me with no auth
 *      header at all. This works in *both* backend modes: if
 *      SHERLOCK_AUTH_ENABLED=false it returns the synthetic
 *      `{ username: "system", roles: [...all roles] }` identity and we
 *      treat that as "logged in, dev mode"; if auth is enabled, an
 *      unauthenticated call 401s and we show the login screen.
 * There's no separate "is auth enabled" endpoint — /auth/me doubles as
 * the probe, so boot only ever needs the one or two calls above.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [isBooting, setIsBooting] = useState(true)
  const user = useAuthStore((s) => s.user)
  const authMode = useAuthStore((s) => s.authMode)
  const setUser = useAuthStore((s) => s.setUser)
  const setAuthMode = useAuthStore((s) => s.setAuthMode)
  const setSession = useAuthStore((s) => s.setSession)
  const clearSession = useAuthStore((s) => s.clearSession)

  useEffect(() => {
    let cancelled = false

    async function boot() {
      const storedRefreshToken = useAuthStore.getState().getStoredRefreshToken()

      if (storedRefreshToken) {
        try {
          const tokens = await apiFetch<TokenResponse>('/auth/refresh', {
            method: 'POST',
            body: { refresh_token: storedRefreshToken },
            skipRefresh: true,
          })
          if (cancelled) return
          setSession(tokens)
          const me = await apiFetch<UserOut>('/auth/me')
          if (cancelled) return
          setUser(me)
          setAuthMode(me.username === 'system' ? 'disabled' : 'enabled')
          setIsBooting(false)
          return
        } catch {
          clearSession()
          // fall through to the unauthenticated probe below
        }
      }

      try {
        const me = await apiFetch<UserOut>('/auth/me', { skipAuth: true, skipRefresh: true })
        if (cancelled) return
        if (me.username === 'system') {
          setUser(me)
          setAuthMode('disabled')
        } else {
          // Shouldn't normally happen without a token, but honor it if it does.
          setUser(me)
          setAuthMode('enabled')
        }
      } catch {
        if (cancelled) return
        setAuthMode('enabled')
        setUser(null)
      } finally {
        if (!cancelled) setIsBooting(false)
      }
    }

    boot()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const value: AuthContextValue = {
    user,
    authMode,
    isBooting,
    isAuthenticated: authMode === 'disabled' ? true : user !== null,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
