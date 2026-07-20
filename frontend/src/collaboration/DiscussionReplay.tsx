import { useState } from 'react'
import { ChevronDown, MessagesSquare, TriangleAlert } from 'lucide-react'
import { useSessionDiscussions } from '@/lib/queries/collaboration'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { confidenceTone } from '@/lib/status-tone'
import type { DiscussionRecord } from '@/lib/types'

function DiscussionRow({ discussion }: { discussion: DiscussionRecord }) {
  const [expanded, setExpanded] = useState(false)
  const { consensus, disagreements, opinions } = discussion

  return (
    <div className="rounded-md border border-border bg-surface-raised p-2.5">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full cursor-pointer items-start justify-between gap-2 text-left"
      >
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-text">{discussion.query}</p>
          <p className="truncate text-[11px] text-muted">{consensus.recommended_conclusion}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Badge tone={confidenceTone(consensus.overall_confidence).tone}>
            {Math.round(consensus.overall_confidence * 100)}%
          </Badge>
          <ChevronDown className={`h-3.5 w-3.5 text-muted transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {expanded && (
        <div className="mt-2 flex flex-col gap-2.5 border-t border-border pt-2.5">
          <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
            <div>
              <p className="font-mono text-sm text-text">{Math.round(consensus.consensus_score * 100)}%</p>
              <p className="text-muted">Agreement</p>
            </div>
            <div>
              <p className="font-mono text-sm text-text">{consensus.agreement_count}</p>
              <p className="text-muted">Aligned</p>
            </div>
            <div>
              <p className="font-mono text-sm text-text">{consensus.disagreement_count}</p>
              <p className="text-muted">Disputed</p>
            </div>
          </div>

          {disagreements.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <p className="flex items-center gap-1 text-[11px] font-semibold text-warning">
                <TriangleAlert className="h-3 w-3" /> Disagreements
              </p>
              {disagreements.map((d, i) => (
                <div key={i} className="rounded bg-surface p-2 text-[11px]">
                  <p className="text-text">
                    {d.entity_label} <span className="text-muted">(spread {Math.round(d.confidence_spread * 100)}%)</span>
                  </p>
                  <p className="text-muted">{d.explanation}</p>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <p className="text-[11px] font-semibold text-muted">Agent opinions ({opinions.length})</p>
            {opinions.map((o, i) => (
              <div key={i} className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="min-w-0 truncate text-text">
                  <span className="text-muted">{o.agent_name}:</span> {o.claim}
                </span>
                <Badge tone={confidenceTone(o.confidence).tone} className="shrink-0">
                  {Math.round(o.confidence * 100)}%
                </Badge>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function DiscussionReplay({ sessionId }: { sessionId: number }) {
  const { data, isLoading } = useSessionDiscussions(sessionId)

  return (
    <Card>
      <CardHeader title="Discussion replay" />
      <CardBody className="flex flex-col gap-2">
        {isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<MessagesSquare className="h-6 w-6" />}
            title="No discussions run"
            description='Ask a question with "enable discussion" turned on to see multi-agent debate here.'
          />
        ) : (
          data
            .slice()
            .sort((a, b) => b.turn_index - a.turn_index)
            .map((d) => <DiscussionRow key={d.id} discussion={d} />)
        )}
      </CardBody>
    </Card>
  )
}
