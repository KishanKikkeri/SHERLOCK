import { FolderOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useSessions } from '@/lib/queries/sessions'
import { priorityTone } from '@/lib/status-tone'
import { formatRelativeTime } from '@/lib/format'

export function ActiveInvestigations() {
  const { data, isLoading } = useSessions({ status: 'open' })

  return (
    <Card>
      <CardHeader
        title="Active investigations"
        action={
          <Link to="/investigations" className="text-xs font-medium text-accent hover:underline">
            View all
          </Link>
        }
      />
      <CardBody>
        {isLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<FolderOpen className="h-6 w-6" />}
            title="No active investigations"
            description="Open sessions will show up here once a case is started."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {data.map((session) => (
              <li key={session.id}>
                <Link
                  to={`/investigations/${session.id}`}
                  className="flex items-center justify-between gap-3 py-2.5 hover:opacity-80"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-text">{session.title}</p>
                    <p className="font-mono text-xs text-muted">
                      {session.session_code} · updated {formatRelativeTime(session.updated_at)}
                    </p>
                  </div>
                  <Badge tone={priorityTone(session.priority)} className="shrink-0 capitalize">
                    {session.priority}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}
