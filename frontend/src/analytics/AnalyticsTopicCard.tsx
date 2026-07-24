import { useEffect, useState } from 'react'
import { ChevronDown, Play, ShieldAlert, Gauge } from 'lucide-react'
import type { AnalyticsTopic } from './topics'
import type { ExecutiveReport } from '@/lib/types'
import { useAnalyticsQuery } from '@/lib/queries/analytics'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge, type BadgeProps } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useLanguage } from '@/providers/LanguageProvider'

function fieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const RISK_TONE: Record<ExecutiveReport['risk_level'], BadgeProps['tone']> = {
  High: 'critical',
  Medium: 'warning',
  Low: 'positive',
  Unknown: 'neutral',
}

/** The Chief Agent / Executive Summarizer always generate their output
 * in English (see backend/intelligence/executive_summary.py). This is
 * the ONLY place that content gets translated for display — via the
 * existing POST /language/translate (through LanguageProvider's
 * translateDynamic, which caches so the same finding is never sent
 * twice) — never recomputed, and the static chrome around it (labels
 * like "Key findings") comes from the resource bundle via t(), not from
 * this call. English UI renders the original text with no extra
 * round-trip. */
function useTranslatedExecutiveReport(report: ExecutiveReport | undefined) {
  const { language, translateDynamic } = useLanguage()
  const [translated, setTranslated] = useState<ExecutiveReport | undefined>(report)

  useEffect(() => {
    if (!report) {
      setTranslated(undefined)
      return
    }
    if (language === 'en') {
      setTranslated(report)
      return
    }
    let cancelled = false
    setTranslated(report) // show the English original immediately while translating
    async function run() {
      const [summary, keyFindings, recommendations, supportingEvidence] = await Promise.all([
        translateDynamic(report!.summary),
        Promise.all(report!.key_findings.map((f) => translateDynamic(f))),
        Promise.all(report!.recommendations.map((r) => translateDynamic(r))),
        Promise.all(report!.supporting_evidence.map((e) => translateDynamic(e))),
      ])
      if (!cancelled) {
        setTranslated({
          ...report!,
          summary,
          key_findings: keyFindings,
          recommendations,
          supporting_evidence: supportingEvidence,
        })
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [report, language, translateDynamic])

  return translated
}

/** The executive report — the default, decision-oriented view every
 * analytics card renders. No raw agent findings appear here; those live
 * behind the "Show agent trace" accordion below. */
function ExecutiveReportView({ report }: { report: ExecutiveReport }) {
  const { t } = useLanguage()
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={RISK_TONE[report.risk_level]}>
          <ShieldAlert className="h-3 w-3" aria-hidden /> {t('analytics.risk', 'Risk')}: {report.risk_level}
        </Badge>
        <Badge tone="info">
          <Gauge className="h-3 w-3" aria-hidden /> {t('analytics.confidence', 'Confidence')} {report.confidence}%
        </Badge>
      </div>

      <p className="text-xs leading-relaxed text-text">{report.summary}</p>

      {report.key_findings.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('analytics.key_findings', 'Key findings')}</p>
          <ul className="flex flex-col gap-1">
            {report.key_findings.map((f, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-text">
                <span className="text-accent">•</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.recommendations.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('analytics.recommendations', 'Recommendations')}</p>
          <ul className="flex flex-col gap-1">
            {report.recommendations.map((r, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-text">
                <span className="text-positive">✓</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.supporting_evidence.length > 0 && (
        <div className="rounded-md border border-border bg-surface-raised p-2">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('analytics.supporting_evidence', 'Supporting evidence')}</p>
          <p className="text-[11px] text-muted">{report.supporting_evidence.join(' · ')}</p>
        </div>
      )}

      {Object.keys(report.metrics).length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {Object.entries(report.metrics).map(([k, v]) => (
            <div key={k} className="rounded-md border border-border bg-surface-raised px-2 py-1.5">
              <p className="font-mono text-sm font-semibold text-text">{v}</p>
              <p className="truncate text-[10px] text-muted">{k.replaceAll('_', ' ')}</p>
            </div>
          ))}
        </div>
      )}

      {report.sources.length > 0 && (
        <p className="text-[11px] text-muted">{t('analytics.sources', 'Sources')}: {report.sources.join(', ')}</p>
      )}
    </div>
  )
}

export function AnalyticsTopicCard({
  topic,
  sessionId,
}: {
  topic: AnalyticsTopic
  sessionId: number | undefined
}) {
  const query = useAnalyticsQuery()
  const { t } = useLanguage()
  const [traceOpen, setTraceOpen] = useState(false)
  const Icon = topic.icon
  const disabled = topic.requiresSession && !sessionId

  const rawExecutiveReport = query.data?.data?.executive_report as ExecutiveReport | undefined
  const executiveReport = useTranslatedExecutiveReport(rawExecutiveReport)

  const narrative =
    query.data?.data && typeof query.data.data.final_report === 'object' && query.data.data.final_report !== null
      ? (query.data.data.final_report as Record<string, unknown>).narrative
      : undefined
  const otherFields = Object.entries(query.data?.data ?? {}).filter(
    ([k]) => k !== 'final_report' && k !== 'executive_report',
  )

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
            <Play className="h-3.5 w-3.5" /> {t('common.run_analysis', 'Run analysis')}
          </Button>
          <Badge tone="neutral" title={`Real backend capability: ${topic.agentHint}`}>
            {topic.agentHint}
          </Badge>
        </div>

        {query.isError && <p className="text-xs text-critical">Query failed — check the backend is reachable.</p>}

        {query.isPending && <Skeleton className="h-24 w-full" />}

        {query.data && (
          <div className="rounded-md border border-border bg-surface-raised p-2.5">
            {executiveReport ? (
              <ExecutiveReportView report={executiveReport} />
            ) : (
              // Fallback for any intent that hasn't been wired to the
              // summarizer yet — still shows the spoken response, never
              // a blank card.
              <p className="text-xs text-text">{query.data.spoken_response}</p>
            )}

            {(typeof narrative === 'string' || otherFields.length > 0) && (
              <div className="mt-2 border-t border-border pt-2">
                <button
                  type="button"
                  onClick={() => setTraceOpen((v) => !v)}
                  className="flex cursor-pointer items-center gap-1 text-[11px] text-muted hover:text-text"
                >
                  <ChevronDown className={`h-3 w-3 transition-transform ${traceOpen ? 'rotate-180' : ''}`} />
                  {traceOpen ? t('analytics.hide_agent_trace', 'Hide agent trace') : t('analytics.show_agent_trace', 'Show agent trace')}
                </button>
                {traceOpen && (
                  <div className="mt-1.5 flex flex-col gap-1">
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
      </CardBody>
    </Card>
  )
}
