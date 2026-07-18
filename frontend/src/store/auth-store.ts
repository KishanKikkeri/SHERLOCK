import { create } from 'zustand'
import type { TokenResponse, UserOut } from '@/lib/types'

const REFRESH_TOKEN_KEY = 'sherlock.refresh_token'

// Access token lives in memory only (this store), never in localStorage —
// limits the window an XSS payload could exfiltrate it. Refresh token is
// persisted so a page reload doesn't force a re-login; see the tradeoff
// noted in docs/stage-f/02-API-CONTRACTS.md (an httpOnly cookie would be
// stronger but changes backend CORS/cookie handling, out of scope here).
interface AuthState {
  accessToken: string | null
  accessTokenExpiresAt: string | null
  user: UserOut | null
  /** Whether the backend has SHERLOCK_AUTH_ENABLED on. Unknown until the
   *  first request resolves — see AuthProvider's boot probe. */
  authMode: 'enabled' | 'disabled' | 'unknown'
  setSession: (tokens: TokenResponse) => void
  setUser: (user: UserOut | null) => void
  setAuthMode: (mode: AuthState['authMode']) => void
  clearSession: () => void
  getStoredRefreshToken: () => string | null
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  accessTokenExpiresAt: null,
  user: null,
  authMode: 'unknown',

  setSession: (tokens) => {
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
    set({
      accessToken: tokens.access_token,
      accessTokenExpiresAt: tokens.expires_at,
    })
  },

  setUser: (user) => set({ user }),

  setAuthMode: (mode) => set({ authMode: mode }),

  clearSession: () => {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    set({ accessToken: null, accessTokenExpiresAt: null, user: null })
  },

  getStoredRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
}))
