import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Construction, LayoutDashboard, Network, Lightbulb, Mic, Clock, FileText, CircleUser as UserCircle } from 'lucide-react'
import { Card, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { useSession } from '@/lib/queries/sessions'
import { priorityTone, statusTone } from '@/lib/status-tone'
import { formatRelativeTime } from '@/lib/format'
import { PresenceIndicator } from '@/collaboration/PresenceIndicator'
import { SessionActivityFeed } from '@/collaboration/SessionActivityFeed'
import { DiscussionReplay } from '@/collaboration/DiscussionReplay'
import { useLanguage } from '@/providers/LanguageProvider'

/**
 * Investigation detail — mission-control header, not a form.
 * Reference: Defender XDR's incident workspace — key metadata
 * (ID, priority, status, timestamps, presence) in a dense header
 * strip, actions as a toolbar, body content below.
 */
export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const sessionId = id ? Number(id) : undefined
  const { data: session, isLoading } = useSession(sessionId)
  const { t } = useLanguage()

  return (
    <div className="flex flex-col gap-4">
      <Link
        to="/investigations"
        className="flex w-fit items-center gap-1 text-sm text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t('investigations.back_to_investigations', 'Back to investigations')}
      </Link>

      {isLoading || !session || !sessionId ? (
        <Skeleton className="h-32 w-full" />
      ) : (
        <>
          {/* Mission-control header */}
          <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-sm">
            <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-semibold text-text">{session.title}</h1>
                  <Badge tone={priorityTone(session.priority)} className="capitalize">
                    {session.priority}
                  </Badge>
                  <Badge tone={statusTone(session.status)} className="capitalize">
                    {session.status}
                  </Badge>
                </div>
                <p className="mt-1 font-mono text-sm text-muted">{session.session_code}</p>
              </div>
              <PresenceIndicator sessionId={sessionId} />
            </div>

            {/* Metadata strip — dense, scannable */}
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3 text-sm">
              <div className="flex items-center gap-1.5 text-muted">
                <Clock className="h-3.5 w-3.5" aria-hidden />
                <span>{t('investigations.opened', 'Opened')} {formatRelativeTime(session.opened_at)}</span>
              </div>
              <div className="flex items-center gap-1.5 text-muted">
                <FileText className="h-3.5 w-3.5" aria-hidden />
                <span>{t('investigations.fir_number', 'FIR #')}{session.fir_id ?? '—'}</span>
              </div>
              <div className="flex items-center gap-1.5 text-muted">
                <UserCircle className="h-3.5 w-3.5" aria-hidden />
                <span>{t('investigations.updated', 'Updated')} {formatRelativeTime(session.updated_at)}</span>
              </div>
              {session.notes && (
                <div className="flex min-w-0 items-center gap-1.5 text-muted">
                  <span className="truncate">{session.notes}</span>
                </div>
              )}
            </div>

            {/* Action toolbar */}
            <div className="flex flex-wrap gap-2 border-t border-border px-5 py-3">
              <Link to={`/investigations/${session.id}/board`}>
                <Button variant="secondary" size="sm">
                  <LayoutDashboard className="h-3.5 w-3.5" /> {t('investigations.board_button', 'Board')}
                </Button>
              </Link>
              <Link to={`/investigations/${session.id}/findings`}>
                <Button variant="secondary" size="sm">
                  <Lightbulb className="h-3.5 w-3.5" /> {t('investigations.findings_button', 'Findings')}
                </Button>
              </Link>
              <Link to="/graph">
                <Button variant="ghost" size="sm">
                  <Network className="h-3.5 w-3.5" /> {t('investigations.network_graph_button', 'Network graph')}
                </Button>
              </Link>
              <Link to="/voice">
                <Button variant="ghost" size="sm">
                  <Mic className="h-3.5 w-3.5" /> {t('investigations.voice_button', 'Voice')}
                </Button>
              </Link>
            </div>
          </div>

          {/* Body: activity + discussion */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SessionActivityFeed sessionId={sessionId} />
            <DiscussionReplay sessionId={sessionId} />
          </div>

          {/* Placeholder for live conversation */}
          <Card>
            <CardBody className="flex flex-col items-center gap-2 py-8 text-center">
              <Construction className="h-6 w-6 text-muted" aria-hidden />
              <p className="text-sm font-medium text-text">
                {t('investigations.conversation_panel_missing_title', "The live conversation panel isn't built yet")}
              </p>
              <p className="max-w-md text-xs text-muted">
                {t(
                  'investigations.conversation_panel_missing_description',
                  "Board, graph, voice, findings, and this session's activity and discussion "
                  + "history are all real and linked above. The one piece still missing is a live "
                  + "WS-connected conversation panel — voice already covers most of what that would do.",
                )}
              </p>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
