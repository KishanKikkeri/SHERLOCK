import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FolderSearch,
  Users,
  ScrollText,
  ShieldCheck,
  Network,
  Mic,
  BarChart3,
} from 'lucide-react'
import { hasPermission } from '@/lib/permissions'
import type { Permission, Role } from '@/lib/types'
import { cn } from '@/lib/cn'

interface NavItem {
  label: string
  path: string
  icon: typeof LayoutDashboard
  requiredPermission?: Permission
}

// Nav is built as data filtered by permission, not hand-written per role —
// see 03-COMPONENT-ARCHITECTURE.md. Add a screen here once, and every
// role that can reach it will see it; no per-role branching elsewhere.
const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, requiredPermission: 'view_case' },
  { label: 'Investigations', path: '/investigations', icon: FolderSearch, requiredPermission: 'view_case' },
  { label: 'Network', path: '/graph', icon: Network, requiredPermission: 'view_case' },
  { label: 'Voice', path: '/voice', icon: Mic, requiredPermission: 'use_voice' },
  { label: 'Analytics', path: '/analytics', icon: BarChart3, requiredPermission: 'view_case' },
  { label: 'Users', path: '/admin/users', icon: Users, requiredPermission: 'manage_users' },
  { label: 'Audit log', path: '/admin/audit', icon: ScrollText, requiredPermission: 'view_audit' },
  { label: 'Governance', path: '/admin/governance', icon: ShieldCheck, requiredPermission: 'administer_system' },
]

export function Nav({ roles, onNavigate }: { roles: Role[]; onNavigate?: () => void }) {
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.requiredPermission || hasPermission(roles, item.requiredPermission),
  )

  return (
    <nav aria-label="Primary" className="flex flex-col gap-1 p-3">
      {visibleItems.map(({ label, path, icon: Icon }) => (
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
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
