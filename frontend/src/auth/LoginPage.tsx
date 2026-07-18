import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ScanSearch } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuth } from './AuthProvider'
import { useLogin } from '@/lib/queries/auth'
import { isApiError } from '@/lib/api-client'

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
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2 text-center">
          <ScanSearch className="h-8 w-8 text-accent" aria-hidden />
          <h1 className="text-xl font-semibold text-text">SHERLOCK</h1>
          <p className="text-sm text-muted">Sign in to continue your investigations.</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6"
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
            Sign in
          </Button>
        </form>
      </div>
    </div>
  )
}
