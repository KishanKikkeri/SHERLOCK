import { useState } from 'react'
import { ChevronDown, Volume2, Radio, Mic } from 'lucide-react'
import type { VoiceConversationTurn } from './conversation-turn'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { useLanguage } from '@/providers/LanguageProvider'

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
  const { t } = useLanguage()
  const intentLabel = turn.intent
    ? t(`voice_turn.intent_${turn.intent}`, turn.intent)
    : undefined
  const narrative =
    turn.data && typeof turn.data.final_report === 'object' && turn.data.final_report !== null
      ? (turn.data.final_report as Record<string, unknown>).narrative
      : undefined
  const otherFields = Object.entries(turn.data ?? {}).filter(([k]) => k !== 'final_report')

  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border bg-surface-raised p-2.5">
      <div className="flex items-center gap-1.5">
        {turn.path === 'server' ? (
          <Mic className="h-3 w-3 text-muted" aria-label={t('voice_turn.server_audio_path', 'Server audio path')} />
        ) : (
          <Radio className="h-3 w-3 text-muted" aria-label={t('voice_turn.browser_speech_path', 'Browser speech path')} />
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
            {intentLabel && <Badge tone="info">{intentLabel}</Badge>}
            {onReplay && turn.spokenResponse && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('voice_turn.replay_response', 'Replay response')}
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
                {expanded ? t('voice_turn.hide_details', 'Hide details') : t('voice_turn.show_details', 'Show details')}
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
