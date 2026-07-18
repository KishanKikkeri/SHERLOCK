import { Outlet } from 'react-router-dom'
import { ScanSearch, Moon, Sun, LogOut } from 'lucide-react'
import { Nav } from './Nav'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { HealthStatusBadge } from '@/dashboard/HealthStatusBadge'
import { useAuth } from '@/auth/AuthProvider'
import { useLogout } from '@/lib/queries/auth'
import { useTheme } from '@/lib/use-theme'

export function AppShell() {
  const { user, authMode } = useAuth()
  const logout = useLogout()
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="grid h-screen grid-cols-[220px_1fr] grid-rows-[56px_1fr] bg-background text-text">
      <header className="col-span-2 flex items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2">
          <ScanSearch className="h-5 w-5 text-accent" aria-hidden />
          <span className="font-semibold tracking-tight">SHERLOCK</span>
          {authMode === 'disabled' && (
            <Badge tone="warning" title="SHERLOCK_AUTH_ENABLED is off on this backend">
              Auth disabled — dev mode
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          <HealthStatusBadge />
          <Button
            variant="ghost"
            size="icon"
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            onClick={toggleTheme}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <div className="flex items-center gap-2 border-l border-border pl-3">
            <div className="text-right">
              <p className="text-sm leading-tight text-text">{user?.full_name ?? user?.username}</p>
              <p className="text-xs leading-tight text-muted">{user?.roles.join(', ')}</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Log out"
              onClick={() => logout.mutate()}
              disabled={authMode === 'disabled'}
              title={authMode === 'disabled' ? 'Logout is a no-op with auth disabled' : 'Log out'}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <aside className="overflow-y-auto border-r border-border">
        <Nav roles={user?.roles ?? []} />
      </aside>

      <main className="overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
