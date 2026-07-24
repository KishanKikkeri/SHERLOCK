import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { ScanSearch, Moon, Sun, LogOut, Menu, X, Keyboard } from 'lucide-react'
import { Nav } from './Nav'
import { ConnectivityBanner } from './ConnectivityBanner'
import { KeyboardShortcutsHelp } from './KeyboardShortcutsHelp'
import { LanguageToggle } from './LanguageToggle'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { HealthStatusBadge } from '@/dashboard/HealthStatusBadge'
import { useAuth } from '@/auth/AuthProvider'
import { useLogout } from '@/lib/queries/auth'
import { useTheme } from '@/lib/use-theme'
import { useKeyboardShortcuts } from '@/lib/use-keyboard-shortcuts'
import { useLanguage } from '@/providers/LanguageProvider'
import { cn } from '@/lib/cn'

export function AppShell() {
  const { user, authMode } = useAuth()
  const logout = useLogout()
  const { theme, toggleTheme } = useTheme()
  const { helpOpen, setHelpOpen } = useKeyboardShortcuts()
  const { t } = useLanguage()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen flex-col bg-background text-text">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-sm focus:text-white"
      >
        {t('navigation.skip_to_main_content')}
      </a>

      <ConnectivityBanner />

      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label={sidebarOpen ? t('navigation.close_menu') : t('navigation.open_menu')}
            onClick={() => setSidebarOpen((v) => !v)}
          >
            {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
          <ScanSearch className="h-5 w-5 text-accent" aria-hidden />
          <span className="font-semibold tracking-tight">{t('labels.app_name')}</span>
          {authMode === 'disabled' && (
            <Badge tone="warning" title="SHERLOCK_AUTH_ENABLED is off on this backend">
              {t('navigation.auth_disabled_badge')}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          <LanguageToggle />
          <HealthStatusBadge />
          <Button
            variant="ghost"
            size="icon"
            className="hidden sm:inline-flex"
            aria-label={t('navigation.keyboard_shortcuts')}
            title={`${t('navigation.keyboard_shortcuts')} (?)`}
            onClick={() => setHelpOpen(true)}
          >
            <Keyboard className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={theme === 'dark' ? t('navigation.switch_to_light_mode') : t('navigation.switch_to_dark_mode')}
            onClick={toggleTheme}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <div className="flex items-center gap-2 border-l border-border pl-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm leading-tight text-text">{user?.full_name ?? user?.username}</p>
              <p className="text-xs leading-tight text-muted">{user?.roles.join(', ')}</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t('navigation.log_out')}
              onClick={() => logout.mutate()}
              disabled={authMode === 'disabled'}
              title={authMode === 'disabled' ? 'Logout is a no-op with auth disabled' : t('navigation.log_out')}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Below lg: sidebar becomes an overlay drawer instead of eating
            fixed width from a tablet-sized viewport. Above lg: static
            220px column, same as before F8. */}
        {sidebarOpen && (
          <button
            type="button"
            aria-label="Close menu"
            className="fixed inset-0 z-30 bg-black/40 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <aside
          className={cn(
            'z-40 overflow-y-auto border-r border-border bg-background transition-transform duration-200',
            'fixed inset-y-14 left-0 w-64 lg:static lg:inset-y-auto lg:w-[220px] lg:translate-x-0',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          <Nav roles={user?.roles ?? []} onNavigate={() => setSidebarOpen(false)} />
        </aside>

        <main id="main-content" className="min-w-0 flex-1 overflow-y-auto p-6">
          {/* Constrained on ultra-wide monitors so content doesn't stretch
              into unreadable line lengths — F8's "large monitors" item. */}
          <div className="mx-auto max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>

      {helpOpen && <KeyboardShortcutsHelp onClose={() => setHelpOpen(false)} />}
    </div>
  )
}
