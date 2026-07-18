import { Radio } from 'lucide-react'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useDashboardActivityFeed } from '@/lib/queries/collaboration'
import { formatRelativeTime } from '@/lib/format'
import type { InvestigationSession } from '@/lib/types'

export function ActivityFeed({ sessions }: { sessions: InvestigationSession[] | undefined }) {
  const { items, isLoading } = useDashboardActivityFeed(sessions)

  return (
    <Card>
      <CardHeader title="Activity feed" />
      <CardBody>
        {isLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Radio className="h-6 w-6" />}
            title="Nothing happening yet"
            description="Actions across your open investigations will stream in here."
          />
        ) : (
          <ul className="flex flex-col gap-2.5">
            {items.map((item) => (
              <li key={item.id} className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 truncate text-text">{item.detail ?? item.action}</span>
                <span className="shrink-0 font-mono text-xs text-muted">
                  {formatRelativeTime(item.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}
