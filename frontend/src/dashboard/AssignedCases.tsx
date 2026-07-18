import { UserRoundCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useSessions } from '@/lib/queries/sessions'
import { statusTone } from '@/lib/status-tone'
import { useAuth } from '@/auth/AuthProvider'

export function AssignedCases() {
  const { user } = useAuth()
  const officerId = user?.officer_id ?? undefined
  const { data, isLoading } = useSessions({ ownerOfficerId: officerId })

  return (
    <Card>
      <CardHeader title="Assigned to me" />
      <CardBody>
        {!officerId ? (
          <EmptyState
            icon={<UserRoundCheck className="h-6 w-6" />}
            title="No officer profile linked"
            description="This account isn't linked to an officer record, so case assignments can't be shown."
          />
        ) : isLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<UserRoundCheck className="h-6 w-6" />}
            title="Nothing assigned to you"
            description="Cases a supervisor assigns to you will appear here."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {data.map((session) => (
              <li key={session.id}>
                <Link
                  to={`/investigations/${session.id}`}
                  className="flex items-center justify-between gap-3 py-2.5 hover:opacity-80"
                >
                  <p className="truncate text-sm font-medium text-text">{session.title}</p>
                  <Badge tone={statusTone(session.status)} className="shrink-0 capitalize">
                    {session.status}
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
