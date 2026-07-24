import { NavLink } from 'react-router-dom'
import { LayoutDashboard, FolderSearch, Users, ShieldCheck, Network, MessageSquare, Mic, ShieldAlert, Users2, TrendingUp, ClipboardList, ChartBar as BarChart3 } from 'lucide-react'
import { hasPermission } from '@/lib/permissions'
import { useLanguage } from '@/providers/LanguageProvider'
import type { Permission, Role } from '@/lib/types'
import { cn } from '@/lib/cn'

interface NavItem {
  labelKey: string
  fallbackLabel: string
  path: string
  icon: typeof LayoutDashboard
  requiredPermission?: Permission
}

// Nav is built as data filtered by permission, not hand-written per role —
// see 03-COMPONENT-ARCHITECTURE.md. Add a screen here once, and every
// role that can reach it will see it; no per-role branching elsewhere.
//
// Stage F2: "Conversation" is the primary entry point (Chief + every
// specialist agent, reachable by just asking — see
// frontend/src/conversation/ConversationPage.tsx), placed first, right
// after Dashboard. "Voice" stays as its own item rather than being
// removed — it's still the right screen for someone who specifically
// wants the dedicated hands-free/server-audio experience (waveform, VU
// meter, push-to-talk without any typing) — but it's no longer the only
// way to talk to SHERLOCK, and Conversation embeds the same microphone
// control for anyone who lands there first.
//
// labelKey/fallbackLabel: t(labelKey, fallbackLabel) — see
// frontend/src/providers/LanguageProvider.tsx. "offenders",
// "sociological_insights", and "forecasting" are new keys added to
// backend/language/resources.py's "navigation" section alongside this
// merge; their Kannada strings are a best-effort translation, not yet
// reviewed by a native speaker — see the integration report.
const NAV_ITEMS: NavItem[] = [
  { labelKey: 'navigation.dashboard', fallbackLabel: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, requiredPermission: 'view_case' },
  { labelKey: 'navigation.conversation', fallbackLabel: 'Conversation', path: '/conversation', icon: MessageSquare, requiredPermission: 'view_case' },
  { labelKey: 'navigation.investigations', fallbackLabel: 'Investigations', path: '/investigations', icon: FolderSearch, requiredPermission: 'view_case' },
  { labelKey: 'navigation.network', fallbackLabel: 'Network', path: '/graph', icon: Network, requiredPermission: 'view_case' },
  { labelKey: 'navigation.offenders', fallbackLabel: 'Offenders', path: '/offender', icon: ShieldAlert, requiredPermission: 'view_case' },
  { labelKey: 'navigation.voice', fallbackLabel: 'Voice', path: '/voice', icon: Mic, requiredPermission: 'use_voice' },
  { labelKey: 'navigation.analytics', fallbackLabel: 'Analytics', path: '/analytics', icon: BarChart3, requiredPermission: 'view_case' },
  { labelKey: 'navigation.sociological_insights', fallbackLabel: 'Sociological Insights', path: '/analytics/sociological', icon: Users2, requiredPermission: 'view_case' },
  { labelKey: 'navigation.forecasting', fallbackLabel: 'Forecasting', path: '/forecast', icon: TrendingUp, requiredPermission: 'view_case' },
  { labelKey: 'navigation.users', fallbackLabel: 'Users', path: '/admin/users', icon: Users, requiredPermission: 'manage_users' },
  { labelKey: 'navigation.governance', fallbackLabel: 'Governance', path: '/admin/governance', icon: ShieldCheck, requiredPermission: 'administer_system' },
  { labelKey: 'navigation.audit_log', fallbackLabel: 'Audit Log', path: '/admin/audit', icon: ClipboardList, requiredPermission: 'view_audit' },
]

export function Nav({ roles, onNavigate }: { roles: Role[]; onNavigate?: () => void }) {
  const { t } = useLanguage()
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.requiredPermission || hasPermission(roles, item.requiredPermission),
  )

  return (
    <nav aria-label="Primary" className="flex flex-col gap-1 p-3">
      {visibleItems.map(({ labelKey, fallbackLabel, path, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150',
              isActive
                ? 'bg-accent/15 text-accent'
                : 'text-muted hover:bg-surface-raised hover:text-text',
            )
          }
        >
          <Icon className="h-4 w-4" aria-hidden />
          {t(labelKey, fallbackLabel)}
        </NavLink>
      ))}
    </nav>
  )
}
