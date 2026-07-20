import { useState } from 'react'
import { ChevronDown, Volume2, Radio, Mic } from 'lucide-react'
import type { VoiceConversationTurn } from './conversation-turn'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'

const INTENT_LABELS: Record<string, string> = {
  empty: 'No input',
  open_case: 'Opened case',
  close_case: 'Closed case',
  reopen_case: 'Reopened case',
  archive_case: 'Archived case',
  assign: 'Assigned officer',
  open_board: 'Opened board',
  read_report: 'Read report',
  generate_report: 'Generated report',
  vehicle_owner: 'Vehicle lookup',
  freeze_account: 'Freeze account',
  investigate: 'Investigation query',
}

function fieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function VoiceTurnCard({
  turn,
  onReplay,
}: {
  turn: VoiceConversationTurn
  onReplay?: (text: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const narrative =
    turn.data && typeof turn.data.final_report === 'object' && turn.data.final_report !== null
      ? (turn.data.final_report as Record<string, unknown>).narrative
      : undefined
  const otherFields = Object.entries(turn.data ?? {}).filter(([k]) => k !== 'final_report')

  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border bg-surface-raised p-2.5">
      <div className="flex items-center gap-1.5">
        {turn.path === 'server' ? (
          <Mic className="h-3 w-3 text-muted" aria-label="Server audio path" />
        ) : (
          <Radio className="h-3 w-3 text-muted" aria-label="Browser speech path" />
        )}
        <p className="min-w-0 flex-1 truncate text-xs font-medium text-text">{turn.query}</p>
        <span className="shrink-0 font-mono text-[10px] text-muted">
          {new Date(turn.timestamp).toLocaleTimeString()}
        </span>
      </div>

      {turn.pending ? (
        <Skeleton className="h-8 w-full" />
      ) : turn.error ? (
        <p className="text-xs text-critical">{turn.error}</p>
      ) : (
        <>
          <div className="flex items-center gap-1.5">
            {turn.intent && <Badge tone="info">{INTENT_LABELS[turn.intent] ?? turn.intent}</Badge>}
            {onReplay && turn.spokenResponse && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Replay response"
                onClick={() => onReplay(turn.spokenResponse!)}
              >
                <Volume2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
          {turn.spokenResponse && <p className="text-xs text-text">{turn.spokenResponse}</p>}

          {(typeof narrative === 'string' || otherFields.length > 0) && (
            <div>
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
        </>
      )}
    </div>
  )
}
