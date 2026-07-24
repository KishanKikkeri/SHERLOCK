import { FileText, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import type { ConversationCitation } from '@/lib/types'

function confidenceTone(confidence: number): 'positive' | 'warning' | 'critical' {
  if (confidence >= 0.75) return 'positive'
  if (confidence >= 0.5) return 'warning'
  return 'critical'
}

export function EvidenceCard({ citation }: { citation: ConversationCitation }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised p-3 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 font-medium text-text">
          <ShieldCheck className="h-3.5 w-3.5 text-positive" aria-hidden />
          {citation.agent_name} — {citation.finding_type}
        </div>
        <Badge tone={confidenceTone(citation.confidence)}>{Math.round(citation.confidence * 100)}%</Badge>
      </div>

      <p className="mt-1.5 text-text">{citation.summary}</p>

      {citation.entities.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {citation.entities.map((e) => (
            <Badge key={`${e.kind}-${e.id}`} tone="info">
              {e.label}
            </Badge>
          ))}
        </div>
      )}

      {citation.evidence.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-4 text-muted">
          {citation.evidence.slice(0, 3).map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}

      {citation.related_documents.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1 text-muted">
          <FileText className="h-3 w-3" aria-hidden />
          {citation.related_documents.join(', ')}
        </div>
      )}
    </div>
  )
}
