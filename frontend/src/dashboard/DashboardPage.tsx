import { Users, FileWarning, Gavel, Network } from 'lucide-react'
import { useSessions } from '@/lib/queries/sessions'
import { useMetrics } from '@/lib/queries/system'
import { Skeleton } from '@/components/ui/Skeleton'
import { ActiveInvestigations } from './ActiveInvestigations'
import { AssignedCases } from './AssignedCases'
import { NotificationsPanel } from './NotificationsPanel'
import { ActivityFeed } from './ActivityFeed'
import { RecentDiscussions } from './RecentDiscussions'

function MetricTile({
  icon: Icon,
  label,
  value,
  isLoading,
}: {
  icon: typeof Users
  label: string
  value: number | undefined
  isLoading: boolean
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-4">
      <Icon className="h-5 w-5 text-accent" aria-hidden />
      <div>
        {isLoading ? (
          <Skeleton className="h-6 w-12" />
        ) : (
          <p className="font-mono text-lg font-semibold text-text">{value ?? '—'}</p>
        )}
        <p className="text-xs text-muted">{label}</p>
      </div>
    </div>
  )
}

export function DashboardPage() {
  // All open + owned sessions feed the activity/discussions composition
  // panels too, so fetch once here and pass down rather than each panel
  // re-fetching its own copy of "recent sessions."
  const { data: openSessions } = useSessions({ status: 'open' })
  const { data: metrics, isLoading: metricsLoading } = useMetrics(true)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-text">Dashboard</h1>
        <p className="text-sm text-muted">An overview of what's active across SHERLOCK.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricTile icon={Users} label="Persons of interest" value={metrics?.persons} isLoading={metricsLoading} />
        <MetricTile icon={FileWarning} label="Open FIRs" value={metrics?.firs} isLoading={metricsLoading} />
        <MetricTile icon={Network} label="Known relationships" value={metrics?.relationships} isLoading={metricsLoading} />
        <MetricTile icon={Gavel} label="Repeat offenders" value={metrics?.repeat_offenders} isLoading={metricsLoading} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ActiveInvestigations />
        <AssignedCases />
        <NotificationsPanel />
        <RecentDiscussions sessions={openSessions} />
        <ActivityFeed sessions={openSessions} />
      </div>
    </div>
  )
}
