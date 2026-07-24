import { CheckCircle2, CircleDashed, SkipForward, XCircle } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { TimelineStep } from '@/conversation/store'

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

export function AgentExecutionTimeline({ steps }: { steps: TimelineStep[] }) {
  if (steps.length === 0) return null

  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border bg-surface-sunken p-3 text-xs">
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
  )
}
