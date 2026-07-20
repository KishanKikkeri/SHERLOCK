import { MessagesSquare } from 'lucide-react'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useDashboardDiscussions } from '@/lib/queries/collaboration'
import { formatRelativeTime } from '@/lib/format'
import type { InvestigationSession } from '@/lib/types'

export function RecentDiscussions({ sessions }: { sessions: InvestigationSession[] | undefined }) {
  const { items, isLoading } = useDashboardDiscussions(sessions)

  return (
    <Card>
      <CardHeader title="Recent discussions" />
      <CardBody>
        {isLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<MessagesSquare className="h-6 w-6" />}
            title="No discussions yet"
            description="Multi-agent discussion turns (enabled per query) will appear here."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {items.map((d) => (
              <li key={d.id} className="py-2.5">
                <p className="truncate text-sm font-medium text-text">{d.query}</p>
                <p className="truncate text-xs text-muted">
                  {d.consensus?.recommended_conclusion ?? 'No consensus reached'} · {formatRelativeTime(d.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}
