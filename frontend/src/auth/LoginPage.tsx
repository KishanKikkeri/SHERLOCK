import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ScanSearch, Lock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuth } from './AuthProvider'
import { useLogin } from '@/lib/queries/auth'
import { isApiError } from '@/lib/api-client'

/**
 * Login — single focal action, no marketing chrome.
 * Reference: Linear's login — centered card, ambient gradient backdrop,
 * brand mark above the fold, error state inline.
 */
export function LoginPage() {
  const { isAuthenticated, isBooting } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const login = useLogin()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  if (isBooting) return null
  if (isAuthenticated) {
    const from = (location.state as { from?: { pathname?: string } })?.from?.pathname ?? '/dashboard'
    return <Navigate to={from} replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      await login.mutateAsync({ username, password })
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setFormError(
        isApiError(err) && err.status === 401
          ? 'Incorrect username or password.'
          : 'Could not reach SHERLOCK. Check your connection and try again.',
      )
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      {/* Ambient backdrop — subtle radial gradient, not a marketing hero.
          Reference: Vercel dashboard login's quiet depth. */}
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% 0%, var(--accent-dim), transparent 70%)',
        }}
      />

      <div className="relative z-10 w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-surface shadow-md">
            <ScanSearch className="h-6 w-6 text-accent" aria-hidden />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-text">SHERLOCK</h1>
            <p className="mt-1 text-sm text-muted">
              Sign in to continue your investigations.
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6 shadow-lg"
        >
          <Input
            label="Username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
          <Input
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            error={formError ?? undefined}
          />
          <Button type="submit" isLoading={login.isPending} className="mt-2 w-full">
            <Lock className="h-4 w-4" /> Sign in
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-subtle">
          Authorized personnel only. All access is logged and audited.
        </p>
      </div>
    </div>
  )
}
