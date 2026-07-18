import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { hasPermission } from '@/lib/permissions'
import type { Permission } from '@/lib/types'
import { ShieldAlert } from 'lucide-react'

interface RequirePermissionProps {
  /** Omit to just require "logged in", no specific permission. */
  permission?: Permission | Permission[]
  children?: ReactNode
}

export function RequirePermission({ permission, children }: RequirePermissionProps) {
  const { isAuthenticated, isBooting, user } = useAuth()
  const location = useLocation()

  if (isBooting) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-muted">
        <p className="font-mono text-sm">Checking session…</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  const roles = user?.roles ?? []
  if (permission && !hasPermission(roles, permission)) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-background text-center">
        <ShieldAlert className="h-10 w-10 text-warning" aria-hidden />
        <p className="text-text">You don't have access to this area.</p>
        <p className="max-w-sm text-sm text-muted">
          Your assigned role doesn't include the permission this page requires. If you
          think that's wrong, ask a supervisor to check your role assignment.
        </p>
      </div>
    )
  }

  return children ? <>{children}</> : <Outlet />
}
