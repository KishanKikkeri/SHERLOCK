import { useAuthStore } from '@/store/auth-store'
import type { ApiError, TokenResponse } from './types'

export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Priority 26 — Global Language Context. Mirrors LanguageProvider's own
// storage key (frontend/src/providers/LanguageProvider.tsx) rather than
// importing the provider directly, since api-client.ts is a plain
// module (no React context) used from places outside any component
// tree. Every request carries whatever language is currently active, so
// the backend's `LanguageContextMiddleware` (backend/language/context.py)
// can resolve it for any AI-generating service that doesn't already take
// an explicit `language` argument — no per-call-site plumbing needed.
const LANGUAGE_STORAGE_KEY = 'sherlock.language'
const LANGUAGE_HEADER = 'X-App-Language'

function getActiveLanguage(): string {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY)
    return stored === 'en' || stored === 'kn' ? stored : 'en'
  } catch {
    return 'en'
  }
}

// Coalesce concurrent refresh attempts into a single in-flight request
// instead of firing one per failed call.
let refreshInFlight: Promise<boolean> | null = null

async function refreshAccessToken(): Promise<boolean> {
  const store = useAuthStore.getState()
  const refreshToken = store.getStoredRefreshToken()
  if (!refreshToken) return false

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (!res.ok) return false
        const tokens = (await res.json()) as TokenResponse
        useAuthStore.getState().setSession(tokens)
        return true
      } catch {
        return false
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** Skip the Authorization header entirely — for /auth/login itself. */
  skipAuth?: boolean
  /** Skip the 401 -> refresh -> retry dance — for /auth/refresh itself. */
  skipRefresh?: boolean
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    return JSON.stringify(data)
  } catch {
    return res.statusText || 'Request failed'
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, skipAuth, skipRefresh, headers, ...rest } = options
  const isFormData = body instanceof FormData

  const doFetch = async (): Promise<Response> => {
    const accessToken = useAuthStore.getState().accessToken
    const finalHeaders: Record<string, string> = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      [LANGUAGE_HEADER]: getActiveLanguage(),
      ...(headers as Record<string, string> | undefined),
    }
    if (!skipAuth && accessToken) {
      finalHeaders.Authorization = `Bearer ${accessToken}`
    }
    return fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    })
  }

  let res = await doFetch()

  // Auth-disabled backends never 401. Auth-enabled ones do once the
  // access token expires — try one silent refresh-and-retry before
  // giving up, per docs/stage-f/02-API-CONTRACTS.md.
  if (res.status === 401 && !skipAuth && !skipRefresh) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      res = await doFetch()
    } else {
      useAuthStore.getState().clearSession()
    }
  }

  if (!res.ok) {
    const detail = await parseErrorDetail(res)
    const error: ApiError = { status: res.status, detail }
    throw error
  }

  if (res.status === 204) return undefined as T
  const contentType = res.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) return undefined as T
  return (await res.json()) as T
}

export function isApiError(err: unknown): err is ApiError {
  return typeof err === 'object' && err !== null && 'status' in err && 'detail' in err
}
