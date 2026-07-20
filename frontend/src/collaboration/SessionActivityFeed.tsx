import { Radio, User, MessagesSquare, Sparkles } from 'lucide-react'
import { useSessionActivityFeed } from '@/lib/queries/collaboration'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { formatRelativeTime } from '@/lib/format'
import type { ActivityFeedKind } from '@/lib/types'

const KIND_ICON: Record<ActivityFeedKind, typeof User> = {
  session: User,
  ai_conversation: MessagesSquare,
  discussion: Sparkles,
}

export function SessionActivityFeed({ sessionId }: { sessionId: number }) {
  const { data, isLoading } = useSessionActivityFeed(sessionId)

  return (
    <Card>
      <CardHeader title="Activity" />
      <CardBody>
        {isLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<Radio className="h-6 w-6" />}
            title="Nothing yet"
            description="Case actions, queries asked, and discussions run will show up here."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {data
              .slice()
              .reverse()
              .map((item, i) => {
                const Icon = KIND_ICON[item.kind]
                return (
                  <li key={`${item.kind}-${item.created_at}-${i}`} className="flex items-start gap-2 text-sm">
                    <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
                    <span className="min-w-0 flex-1 text-text">{item.detail ?? item.event_type}</span>
                    <span className="shrink-0 font-mono text-xs text-muted">
                      {formatRelativeTime(item.created_at)}
                    </span>
                  </li>
                )
              })}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}
