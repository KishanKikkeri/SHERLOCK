import { useState } from 'react'
import { ChevronDown, Play } from 'lucide-react'
import type { AnalyticsTopic } from './topics'
import { useAnalyticsQuery } from '@/lib/queries/analytics'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'

function fieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function AnalyticsTopicCard({
  topic,
  sessionId,
}: {
  topic: AnalyticsTopic
  sessionId: number | undefined
}) {
  const query = useAnalyticsQuery()
  const [expanded, setExpanded] = useState(false)
  const Icon = topic.icon
  const disabled = topic.requiresSession && !sessionId

  const narrative =
    query.data?.data && typeof query.data.data.final_report === 'object' && query.data.data.final_report !== null
      ? (query.data.data.final_report as Record<string, unknown>).narrative
      : undefined
  const otherFields = Object.entries(query.data?.data ?? {}).filter(([k]) => k !== 'final_report')

  return (
    <Card>
      <CardBody className="flex flex-col gap-2.5">
        <div className="flex items-start gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
            <Icon className="h-4 w-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-text">{topic.label}</p>
            <p className="text-xs text-muted">{topic.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => query.mutate({ query: topic.query, session_id: sessionId })}
            isLoading={query.isPending}
            disabled={disabled}
            title={disabled ? 'Decision support needs a session selected above' : undefined}
          >
            <Play className="h-3.5 w-3.5" /> Run analysis
          </Button>
          <Badge tone="neutral" title={`Real backend capability: ${topic.agentHint}`}>
            {topic.agentHint}
          </Badge>
        </div>

        {query.isError && <p className="text-xs text-critical">Query failed — check the backend is reachable.</p>}

        {query.data && (
          <div className="rounded-md border border-border bg-surface-raised p-2.5">
            <p className="text-xs text-text">{query.data.spoken_response}</p>
            {(typeof narrative === 'string' || otherFields.length > 0) && (
              <div className="mt-1.5">
                <button
                  type="button"
                  onClick={() => setExpanded((v) => !v)}
                  className="flex cursor-pointer items-center gap-1 text-[11px] text-muted hover:text-text"
                >
                  <ChevronDown className={`h-3 w-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
                  {expanded ? 'Hide details' : 'Show details'}
                </button>
                {expanded && (
                  <div className="mt-1.5 flex flex-col gap-1 border-t border-border pt-1.5">
                    {typeof narrative === 'string' && (
                      <p className="whitespace-pre-wrap text-[11px] text-muted">{narrative}</p>
                    )}
                    {otherFields.map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-2 text-[11px]">
                        <span className="text-muted">{k.replaceAll('_', ' ')}</span>
                        <span className="truncate font-mono text-text">{fieldValue(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {query.isPending && <Skeleton className="h-10 w-full" />}
      </CardBody>
    </Card>
  )
}
