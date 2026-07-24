import { Sparkles, Link2, GitBranch, AlertTriangle, FileQuestion, Layers, Plus, Clock } from 'lucide-react'
import type { BoardIntelligence, DecisionTimelineEntry } from '@/lib/types'
import type { BoardCard } from './board-types'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { confidenceTone } from '@/lib/status-tone'
import { useLanguage } from '@/providers/LanguageProvider'

interface Props {
  intelligence: BoardIntelligence | undefined
  decisions: DecisionTimelineEntry[] | undefined
  isLoading: boolean
  onAddCard: (partial: Partial<BoardCard> & { kind: BoardCard['kind'] }) => void
}

function Section({
  icon: Icon,
  title,
  count,
  children,
}: {
  icon: typeof Sparkles
  title: string
  count: number
  children: React.ReactNode
}) {
  if (count === 0) return null
  return (
    <div className="flex flex-col gap-1.5">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-muted">
        <Icon className="h-3.5 w-3.5" /> {title} ({count})
      </p>
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  )
}

function SuggestionRow({
  title,
  body,
  badge,
  onAdd,
  addLabel,
}: {
  title: string
  body?: string
  badge?: React.ReactNode
  onAdd: () => void
  addLabel: string
}) {
  return (
    <div className="flex items-start justify-between gap-2 rounded-md border border-border bg-surface-raised p-2">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="truncate text-xs font-medium text-text">{title}</p>
          {badge}
        </div>
        {body && <p className="line-clamp-2 text-[11px] text-muted">{body}</p>}
      </div>
      <Button variant="ghost" size="icon" onClick={onAdd} aria-label={addLabel} title={addLabel}>
        <Plus className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

export function AiSuggestionsPanel({ intelligence, decisions, isLoading, onAddCard }: Props) {
  const { t } = useLanguage()
  const addLabel = t('ai_suggestions.add_to_board', 'Add to board')

  if (isLoading) {
    return (
      <Card>
        <CardHeader title={t('ai_suggestions.title', 'AI suggestions')} />
        <CardBody className="flex flex-col gap-2">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </CardBody>
      </Card>
    )
  }

  if (!intelligence) return null

  const {
    evidence_summary,
    suggested_links,
    hidden_connections,
    contradictions,
    missing_evidence,
    ai_generated_hypotheses,
    evidence_clusters,
  } = intelligence

  const totalSuggestions =
    suggested_links.length +
    hidden_connections.length +
    contradictions.length +
    missing_evidence.length +
    ai_generated_hypotheses.length

  return (
    <Card>
      <CardHeader
        title={t('ai_suggestions.title', 'AI suggestions')}
        action={
          <span className="text-[11px] text-muted">
            {evidence_summary.finding_count} {t('ai_suggestions.findings_summary', 'findings')} ·{' '}
            {evidence_summary.persons_referenced} {t('ai_suggestions.people_summary', 'people')}
          </span>
        }
      />
      <CardBody className="flex flex-col gap-4">
        {totalSuggestions === 0 ? (
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title={t('ai_suggestions.nothing_yet_title', 'Nothing to suggest yet')}
            description={t(
              'ai_suggestions.nothing_yet_description',
              'Run an investigation query in this session — suggestions build up from its findings.',
            )}
          />
        ) : (
          <>
            <Section icon={GitBranch} title={t('ai_suggestions.hypotheses', 'Hypotheses')} count={ai_generated_hypotheses.length}>
              {ai_generated_hypotheses.map((h, i) => (
                <SuggestionRow
                  key={i}
                  title={h.title}
                  body={h.body}
                  addLabel={addLabel}
                  badge={
                    <Badge tone={confidenceTone(h.confidence).tone} className="text-[10px]">
                      {Math.round(h.confidence * 100)}%
                    </Badge>
                  }
                  onAdd={() =>
                    onAddCard({
                      kind: 'hypothesis',
                      title: h.title,
                      body: h.body,
                      confidence: h.confidence,
                      x: 200 + Math.random() * 300,
                      y: 160 + Math.random() * 200,
                    })
                  }
                />
              ))}
            </Section>

            <Section icon={Link2} title={t('ai_suggestions.suggested_links', 'Suggested links')} count={suggested_links.length}>
              {suggested_links.map((l, i) => (
                <SuggestionRow
                  key={i}
                  title={`${l.from} ↔ ${l.to}`}
                  body={l.reason}
                  addLabel={addLabel}
                  badge={
                    l.confidence !== null ? (
                      <Badge tone={confidenceTone(l.confidence).tone} className="text-[10px]">
                        {Math.round(l.confidence * 100)}%
                      </Badge>
                    ) : undefined
                  }
                  onAdd={() =>
                    onAddCard({
                      kind: 'note',
                      title: `Suggested link: ${l.label ?? 'connection'}`,
                      body: `${l.from} ↔ ${l.to}\n${l.reason}`,
                      x: 200 + Math.random() * 300,
                      y: 160 + Math.random() * 200,
                    })
                  }
                />
              ))}
            </Section>

            <Section icon={GitBranch} title={t('ai_suggestions.hidden_connections', 'Hidden connections')} count={hidden_connections.length}>
              {hidden_connections.map((h, i) => (
                <SuggestionRow
                  key={i}
                  title={`${h.from} ↔ ${h.to} (${h.hops} hops)`}
                  body={h.path.join(' → ')}
                  addLabel={addLabel}
                  onAdd={() =>
                    onAddCard({
                      kind: 'note',
                      title: `Hidden connection (${h.hops} hops)`,
                      body: `${h.from} ↔ ${h.to}\nPath: ${h.path.join(' → ')}`,
                      x: 200 + Math.random() * 300,
                      y: 160 + Math.random() * 200,
                    })
                  }
                />
              ))}
            </Section>

            <Section icon={AlertTriangle} title={t('ai_suggestions.contradictions', 'Contradictions')} count={contradictions.length}>
              {contradictions.map((c, i) => (
                <SuggestionRow
                  key={i}
                  title={`${c.rejected_finding.agent} vs ${c.conflicts_with.agent}`}
                  body={`${c.rejected_finding.summary} — conflicts with: ${c.conflicts_with.summary}`}
                  addLabel={addLabel}
                  badge={
                    <Badge tone="critical" className="text-[10px]">
                      {t('ai_suggestions.contradiction_badge', 'Contradiction')}
                    </Badge>
                  }
                  onAdd={() =>
                    onAddCard({
                      kind: 'note',
                      title: '⚠ Contradiction',
                      body: `${c.rejected_finding.summary}\n\nConflicts with:\n${c.conflicts_with.summary}`,
                      color: '#EF4444',
                      x: 200 + Math.random() * 300,
                      y: 160 + Math.random() * 200,
                    })
                  }
                />
              ))}
            </Section>

            <Section icon={FileQuestion} title={t('ai_suggestions.missing_evidence', 'Missing evidence')} count={missing_evidence.length}>
              {missing_evidence.map((m, i) => (
                <SuggestionRow
                  key={i}
                  title={m.agent}
                  body={m.gap}
                  addLabel={addLabel}
                  onAdd={() =>
                    onAddCard({
                      kind: 'note',
                      title: `Gap: ${m.agent}`,
                      body: m.gap,
                      x: 200 + Math.random() * 300,
                      y: 160 + Math.random() * 200,
                    })
                  }
                />
              ))}
            </Section>
          </>
        )}

        {evidence_clusters.length > 0 && (
          <Section icon={Layers} title={t('ai_suggestions.clusters', 'Clusters')} count={evidence_clusters.length}>
            {evidence_clusters.map((cl, i) => (
              <div key={i} className="rounded-md border border-border bg-surface-raised p-2">
                <p className="text-xs font-medium text-text">
                  {cl.label} <span className="text-muted">({cl.member_count})</span>
                </p>
                <p className="truncate text-[11px] text-muted">{cl.finding_types.join(', ')}</p>
              </div>
            ))}
          </Section>
        )}

        {decisions && decisions.length > 0 && (
          <Section icon={Clock} title={t('ai_suggestions.timeline_decisions', 'Timeline (decisions)')} count={decisions.length}>
            {decisions.map((d) => (
              <SuggestionRow
                key={d.turn_index}
                title={d.conclusion}
                body={`${d.query} · ${d.finding_count} finding(s)`}
                addLabel={addLabel}
                badge={
                  <span className="font-mono text-[10px] text-muted">
                    {new Date(d.created_at).toLocaleDateString()}
                  </span>
                }
                onAdd={() =>
                  onAddCard({
                    kind: 'timeline',
                    title: d.conclusion.length > 40 ? `${d.conclusion.slice(0, 40)}…` : d.conclusion,
                    body: d.conclusion,
                    timestamp: d.created_at,
                    x: 200 + Math.random() * 300,
                    y: 160 + Math.random() * 200,
                  })
                }
              />
            ))}
          </Section>
        )}
      </CardBody>
    </Card>
  )
}
