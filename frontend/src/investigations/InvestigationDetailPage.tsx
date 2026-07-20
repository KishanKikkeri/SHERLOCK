import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Construction, LayoutDashboard, Network, Lightbulb, Mic } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { useSession } from '@/lib/queries/sessions'
import { priorityTone, statusTone } from '@/lib/status-tone'
import { formatRelativeTime } from '@/lib/format'
import { PresenceIndicator } from '@/collaboration/PresenceIndicator'
import { SessionActivityFeed } from '@/collaboration/SessionActivityFeed'
import { DiscussionReplay } from '@/collaboration/DiscussionReplay'

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

      {isLoading || !session || !sessionId ? (
        <Skeleton className="h-32 w-full" />
      ) : (
        <>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-lg font-semibold text-text">{session.title}</h1>
              <p className="font-mono text-sm text-muted">{session.session_code}</p>
            </div>
            <div className="flex items-center gap-2">
              <PresenceIndicator sessionId={sessionId} />
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

          <div className="flex flex-wrap gap-2">
            <Link to={`/investigations/${session.id}/board`}>
              <Button variant="secondary" size="sm">
                <LayoutDashboard className="h-3.5 w-3.5" /> Open board
              </Button>
            </Link>
            <Link to={`/investigations/${session.id}/findings`}>
              <Button variant="secondary" size="sm">
                <Lightbulb className="h-3.5 w-3.5" /> Findings
              </Button>
            </Link>
            <Link to="/graph">
              <Button variant="secondary" size="sm">
                <Network className="h-3.5 w-3.5" /> Open network graph
              </Button>
            </Link>
            <Link to="/voice">
              <Button variant="secondary" size="sm">
                <Mic className="h-3.5 w-3.5" /> Voice
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SessionActivityFeed sessionId={sessionId} />
            <DiscussionReplay sessionId={sessionId} />
          </div>

          <Card>
            <CardBody className="flex flex-col items-center gap-2 py-8 text-center">
              <Construction className="h-6 w-6 text-muted" aria-hidden />
              <p className="text-sm font-medium text-text">
                The live conversation panel isn't built yet
              </p>
              <p className="max-w-md text-xs text-muted">
                Board (F3), graph (F2), voice (F4), findings (F6), and this session's activity
                and discussion history (F5) are all real and linked above. The one piece still
                missing is a live WS-connected conversation/follow-up-chat panel — voice already
                covers most of what that would do (see the Voice page), so it's lower priority
                than it looked at the start of Stage F.
              </p>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
