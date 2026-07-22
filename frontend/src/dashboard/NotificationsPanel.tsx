import { Bell, BellOff } from 'lucide-react'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useMarkNotificationRead, useNotifications } from '@/lib/queries/collaboration'
import { formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/cn'
import { useAuth } from '@/auth/AuthProvider'

export function NotificationsPanel() {
  const { user } = useAuth()
  const { data, isLoading } = useNotifications(user?.officer_id)
  const markRead = useMarkNotificationRead(user?.officer_id)

  return (
    <Card>
      <CardHeader title="Notifications" />
      <CardBody>
        {!user?.officer_id ? (
          <EmptyState
            icon={<BellOff className="h-6 w-6" />}
            title="No officer profile linked"
            description="Notifications are delivered per officer record."
          />
        ) : isLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<Bell className="h-6 w-6" />}
            title="You're all caught up"
            description="New comments, mentions, and review requests will show up here."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {data.slice(0, 8).map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => !n.read_at && markRead.mutate(n.id)}
                  aria-label={n.read_at ? `Notification: ${n.message}` : `Unread notification: ${n.message}. Activate to mark as read.`}
                  className="flex w-full cursor-pointer items-start gap-2 py-2.5 text-left hover:bg-surface-raised"
                >
                  <span
                    className={cn('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full', n.read_at ? 'bg-transparent' : 'bg-accent')}
                    aria-hidden
                  />
                  <div className="min-w-0">
                    <p className="text-sm text-text">{n.message}</p>
                    <p className="text-xs text-muted">{formatRelativeTime(n.created_at)}</p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}
