import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Lightbulb, TriangleAlert as AlertTriangle, FileQuestionMark as FileQuestion } from 'lucide-react'
import { useBoardIntelligence } from '@/lib/queries/board'
import { useSession } from '@/lib/queries/sessions'
import { FindingCard } from './FindingCard'
import type { DisplayFinding } from './display-finding'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'

export function FindingsPage() {
  const { id } = useParams<{ id: string }>()
  const sessionId = id ? Number(id) : undefined
  const { data: session } = useSession(sessionId)
  const { data: intelligence, isLoading } = useBoardIntelligence(sessionId)

  const findings: DisplayFinding[] =
    intelligence?.ai_generated_hypotheses.map((h, i) => ({
      id: `hyp-${i}`,
      summary: h.title,
      body: h.body,
      agent_name: h.agent,
      confidence: h.confidence,
      source_entities: h.source_entities,
    })) ?? []

  return (
    <div className="flex flex-col gap-4">
      <Link
        to={sessionId ? `/investigations/${sessionId}` : '/investigations'}
        className="flex w-fit items-center gap-1 text-sm text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to session
      </Link>

      <div>
        <h1 className="text-2xl font-semibold text-text">Findings</h1>
        <p className="text-xs text-muted">{session?.title ?? `Session #${sessionId}`}</p>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-2">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-muted">
              <Lightbulb className="h-3.5 w-3.5" /> Findings ({findings.length})
            </p>
            {findings.length === 0 ? (
              <Card>
                <CardBody>
                  <EmptyState
                    icon={<Lightbulb className="h-6 w-6" />}
                    title="No findings yet"
                    description="Run an investigation query in this session to generate findings."
                  />
                </CardBody>
              </Card>
            ) : (
              findings.map((f) => <FindingCard key={f.id} finding={f} />)
            )}
          </div>

          {intelligence && intelligence.contradictions.length > 0 && (
            <Card>
              <CardHeader title="Contradictions" />
              <CardBody className="flex flex-col gap-2">
                {intelligence.contradictions.map((c, i) => (
                  <div key={i} className="rounded-md border border-critical/30 bg-critical/5 p-2.5">
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 text-critical" />
                      <p className="text-xs font-medium text-text">
                        {c.rejected_finding.agent} vs {c.conflicts_with.agent}
                      </p>
                    </div>
                    <p className="mt-1 text-xs text-muted">{c.rejected_finding.summary}</p>
                    <p className="text-xs text-muted">Conflicts with: {c.conflicts_with.summary}</p>
                    {c.shared_entities.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {c.shared_entities.map((e) => (
                          <Badge key={e} tone="neutral">
                            {e}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </CardBody>
            </Card>
          )}

          {intelligence && intelligence.missing_evidence.length > 0 && (
            <Card>
              <CardHeader title="Missing evidence" />
              <CardBody className="flex flex-col gap-2">
                {intelligence.missing_evidence.map((m, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <FileQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                    <div>
                      <p className="font-medium text-text">{m.agent}</p>
                      <p className="text-muted">{m.gap}</p>
                    </div>
                  </div>
                ))}
              </CardBody>
            </Card>
          )}

          {sessionId && (
            <Link to={`/investigations/${sessionId}/board`}>
              <Button variant="ghost" size="sm">
                Open the board to act on these →
              </Button>
            </Link>
          )}
        </>
      )}
    </div>
  )
}
