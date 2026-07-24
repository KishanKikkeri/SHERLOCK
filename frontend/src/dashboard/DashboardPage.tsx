import { Users, MailWarning as FileWarning, Network, Gavel, FolderOpen } from 'lucide-react'
import { useSessions } from '@/lib/queries/sessions'
import { useMetrics } from '@/lib/queries/system'
import { Skeleton } from '@/components/ui/Skeleton'
import { ActiveInvestigations } from './ActiveInvestigations'
import { AssignedCases } from './AssignedCases'
import { NotificationsPanel } from './NotificationsPanel'
import { ActivityFeed } from './ActivityFeed'
import { RecentDiscussions } from './RecentDiscussions'
import { useLanguage } from '@/providers/LanguageProvider'
import { cn } from '@/lib/cn'

/**
 * KPI strip — not equal-sized boxes. The first tile (open investigations)
 * gets double width because it's the most actionable. Metrics get a
 * compact, scannable row. Reference: Defender XDR's severity-weighted
 * KPI hierarchy, Linear's dashboard density.
 */
function KpiStrip({
  metrics,
  metricsLoading,
  openCount,
}: {
  metrics: { persons?: number; firs?: number; relationships?: number; repeat_offenders?: number } | undefined
  metricsLoading: boolean
  openCount: number
}) {
  const { t } = useLanguage()
  const tiles = [
    { icon: FolderOpen, label: t('dashboard.kpi_open_investigations', 'Open investigations'), value: openCount, accent: true, span: 'lg:col-span-2' },
    { icon: Users, label: t('dashboard.kpi_persons_of_interest', 'Persons of interest'), value: metrics?.persons },
    { icon: FileWarning, label: t('dashboard.kpi_open_firs', 'Open FIRs'), value: metrics?.firs },
    { icon: Network, label: t('dashboard.kpi_known_relationships', 'Known relationships'), value: metrics?.relationships },
    { icon: Gavel, label: t('dashboard.kpi_repeat_offenders', 'Repeat offenders'), value: metrics?.repeat_offenders },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
      {tiles.map((t) => (
        <div
          key={t.label}
          className={cn(
            'flex items-center gap-3 rounded-lg border bg-surface p-4 transition-colors',
            t.accent
              ? 'border-accent/30 bg-accent/5'
              : 'border-border hover:border-border-strong',
            t.span,
          )}
        >
          <t.icon
            className={cn('h-5 w-5 shrink-0', t.accent ? 'text-accent' : 'text-muted')}
            aria-hidden
          />
          <div className="min-w-0">
            {metricsLoading && !t.accent ? (
              <Skeleton className="h-6 w-12" />
            ) : (
              <p
                className={cn(
                  'font-mono font-semibold text-text',
                  t.accent ? 'text-2xl' : 'text-lg',
                )}
              >
                {t.value ?? '—'}
              </p>
            )}
            <p className="truncate text-xs text-muted">{t.label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

export function DashboardPage() {
  const { data: openSessions } = useSessions({ status: 'open' })
  const { data: metrics, isLoading: metricsLoading } = useMetrics(true)
  const { t } = useLanguage()

  const openCount = openSessions?.length ?? 0
  const criticalCount = openSessions?.filter((s) => s.priority === 'critical').length ?? 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">{t('dashboard.title', 'Dashboard')}</h1>
          <p className="mt-1 text-sm text-muted">
            {t('dashboard.subtitle', 'Operational overview across all active investigations.')}
          </p>
        </div>
        {criticalCount > 0 && (
          <div className="flex items-center gap-2 rounded-md border border-critical/30 bg-critical-dim px-3 py-1.5">
            <span className="h-2 w-2 animate-pulse rounded-full bg-critical" aria-hidden />
            <span className="text-sm font-medium text-critical">
              {criticalCount} {t('dashboard.critical_priority', 'critical priority')}
            </span>
          </div>
        )}
      </div>

      <KpiStrip metrics={metrics} metricsLoading={metricsLoading} openCount={openCount} />

      {/* Primary workspace: 2/3 width active investigations + assigned,
          1/3 width notifications. Reference: Linear's dashboard —
          activity-forward, not a stat dump. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <ActiveInvestigations />
          <AssignedCases />
        </div>
        <div className="flex flex-col gap-4">
          <NotificationsPanel />
        </div>
      </div>

      {/* Secondary row: discussions + activity feed — equal weight,
          both are temporal streams. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RecentDiscussions sessions={openSessions} />
        <ActivityFeed sessions={openSessions} />
      </div>
    </div>
  )
}
