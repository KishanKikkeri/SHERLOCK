import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, FileText, Lightbulb, ListChecks, Network, ShieldCheck } from 'lucide-react'
import type { DisplayFinding } from './display-finding'
import { personSourceEntities } from './display-finding'
import { Badge } from '@/components/ui/Badge'
import { confidenceTone } from '@/lib/status-tone'

function ChainStep({
  icon: Icon,
  label,
  children,
}: {
  icon: typeof FileText
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex gap-2.5 border-l-2 border-border pl-3">
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold text-muted">{label}</p>
        {children}
      </div>
    </div>
  )
}

function NotExposed() {
  return <p className="text-[11px] italic text-muted">Not exposed by the API yet — see known limitations.</p>
}

export function FindingCard({ finding }: { finding: DisplayFinding }) {
  const [expanded, setExpanded] = useState(false)
  const tone = confidenceTone(finding.confidence)
  const personIds = personSourceEntities(finding.source_entities)
  const nonPersonEntities = finding.source_entities.filter((e) => !e.startsWith('person_'))

  return (
    <div className="rounded-lg border border-border bg-surface">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full cursor-pointer items-start justify-between gap-3 p-3 text-left"
      >
        <div className="min-w-0">
          <p className="text-sm font-medium text-text">{finding.summary}</p>
          <p className="text-xs text-muted">{finding.agent_name}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Badge tone={tone.tone}>{Math.round(finding.confidence * 100)}%</Badge>
          {finding.validated !== undefined && (
            <Badge tone={finding.validated ? 'positive' : 'neutral'}>
              {finding.validated ? 'Validated' : 'Unvalidated'}
            </Badge>
          )}
          <ChevronDown className={`h-4 w-4 text-muted transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {expanded && (
        <div className="flex flex-col gap-3 border-t border-border p-3">
          <ChainStep icon={FileText} label="Finding">
            <p className="text-xs text-text">{finding.summary}</p>
          </ChainStep>

          <ChainStep icon={ListChecks} label="Evidence">
            {finding.evidence && finding.evidence.length > 0 ? (
              <ul className="list-inside list-disc text-xs text-text">
                {finding.evidence.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            ) : finding.body ? (
              <p className="text-xs text-text">{finding.body}</p>
            ) : (
              <NotExposed />
            )}
          </ChainStep>

          <ChainStep icon={Lightbulb} label="Reasoning">
            {finding.reasoning ? <p className="text-xs text-text">{finding.reasoning}</p> : <NotExposed />}
          </ChainStep>

          <ChainStep icon={Network} label="Graph links">
            {personIds.length > 0 || nonPersonEntities.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {personIds.map((id) => (
                  <Link key={id} to={`/graph/${id}`}>
                    <Badge tone="info" className="cursor-pointer hover:bg-info/20">
                      View Person:{id} in graph
                    </Badge>
                  </Link>
                ))}
                {nonPersonEntities.map((e) => (
                  <Badge key={e} tone="neutral" title="Graph can only center on a person — see F2's constraint">
                    {e}
                  </Badge>
                ))}
              </div>
            ) : (
              <NotExposed />
            )}
          </ChainStep>

          <ChainStep icon={ShieldCheck} label="Related FIR / supporting documents">
            {finding.related_documents && finding.related_documents.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {finding.related_documents.map((d) => (
                  <Badge key={d} tone="warning">
                    {d}
                  </Badge>
                ))}
              </div>
            ) : (
              <NotExposed />
            )}
          </ChainStep>
        </div>
      )}
    </div>
  )
}
