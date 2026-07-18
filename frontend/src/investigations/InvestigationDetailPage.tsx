import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Construction } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useSession } from '@/lib/queries/sessions'
import { priorityTone, statusTone } from '@/lib/status-tone'
import { formatRelativeTime } from '@/lib/format'

export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const sessionId = id ? Number(id) : undefined
  const { data: session, isLoading } = useSession(sessionId)

  return (
    <div className="flex flex-col gap-4">
      <Link
        to="/investigations"
        className="flex w-fit items-center gap-1 text-sm text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to investigations
      </Link>

      {isLoading || !session ? (
        <Skeleton className="h-32 w-full" />
      ) : (
        <>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-lg font-semibold text-text">{session.title}</h1>
              <p className="font-mono text-sm text-muted">{session.session_code}</p>
            </div>
            <div className="flex gap-2">
              <Badge tone={priorityTone(session.priority)} className="capitalize">
                {session.priority}
              </Badge>
              <Badge tone={statusTone(session.status)} className="capitalize">
                {session.status}
              </Badge>
            </div>
          </div>

          <Card>
            <CardHeader title="Session details" />
            <CardBody className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted">Opened</p>
                <p className="text-text">{formatRelativeTime(session.opened_at)}</p>
              </div>
              <div>
                <p className="text-muted">Last updated</p>
                <p className="text-text">{formatRelativeTime(session.updated_at)}</p>
              </div>
              {session.notes && (
                <div className="col-span-2">
                  <p className="text-muted">Notes</p>
                  <p className="text-text">{session.notes}</p>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardBody className="flex flex-col items-center gap-2 py-10 text-center">
              <Construction className="h-6 w-6 text-muted" aria-hidden />
              <p className="text-sm font-medium text-text">
                The full investigation workspace isn't built yet
              </p>
              <p className="max-w-md text-xs text-muted">
                Conversation, follow-up chat, voice, the evidence board, the graph, findings, and
                the timeline ship in Sprints F2–F6 (see docs/stage-f/03-COMPONENT-ARCHITECTURE.md).
                This page intentionally shows real session data only — no mocked panels.
              </p>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
