import { useState } from 'react'
import { CheckCircle2, CircleDashed, SkipForward, XCircle, ChevronDown, ChevronUp, Terminal } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { TimelineStep } from '@/conversation/storeV2'

const STATUS_ICON: Record<TimelineStep['status'], typeof CheckCircle2> = {
  started: CircleDashed,
  completed: CheckCircle2,
  skipped: SkipForward,
  failed: XCircle,
}

const STATUS_CLASS: Record<TimelineStep['status'], string> = {
  started: 'text-muted animate-pulse',
  completed: 'text-positive',
  skipped: 'text-muted',
  failed: 'text-critical',
}

export function AgentExecutionTimelineV2({ steps }: { steps: TimelineStep[] }) {
  const [expanded, setExpanded] = useState(false)
  if (steps.length === 0) return null

  const lastStep = steps[steps.length - 1]
  const isRunning = steps.some((s) => s.status === 'started')

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-surface-sunken p-3 text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-medium text-text">
          <Terminal className="h-3.5 w-3.5 text-accent" />
          <span>
            {isRunning
              ? `Investigation in progress: ${lastStep.message || lastStep.agent}...`
              : 'Investigation completed.'}
          </span>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 font-semibold text-accent hover:text-accent-hover transition-colors"
        >
          {expanded ? (
            <>
              Hide Developer Trace <ChevronUp className="h-3 w-3" />
            </>
          ) : (
            <>
              Show Developer Trace <ChevronDown className="h-3 w-3" />
            </>
          )}
        </button>
      </div>

      {expanded && (
        <div className="mt-2 flex flex-col gap-1.5 border-t border-border pt-2.5">
          {steps.map((step, i) => {
            const Icon = STATUS_ICON[step.status]
            return (
              <div key={i} className="flex items-start gap-2">
                <Icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', STATUS_CLASS[step.status])} aria-hidden />
                <div className="min-w-0">
                  <span className="font-medium text-text">{step.agent}</span>
                  {step.message && <span className="text-muted"> — {step.message}</span>}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
