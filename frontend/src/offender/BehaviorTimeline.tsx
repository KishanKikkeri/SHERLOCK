import { Gavel, Scale, ShieldAlert, UserCheck, UserX } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { OffenderTimelineEvent } from '@/lib/types'

const TYPE_ICON: Record<OffenderTimelineEvent['type'], typeof Gavel> = {
  accused: ShieldAlert,
  arrest: UserX,
  chargesheet: Gavel,
  victim: UserCheck,
  witness: Scale,
}

const TYPE_CLASS: Record<OffenderTimelineEvent['type'], string> = {
  accused: 'text-critical',
  arrest: 'text-warning',
  chargesheet: 'text-info',
  victim: 'text-muted',
  witness: 'text-muted',
}

export function BehaviorTimeline({ events }: { events: OffenderTimelineEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-muted">No case-role history on record for this person.</p>
  }

  return (
    <ol className="flex flex-col gap-3">
      {events.map((e, i) => {
        const Icon = TYPE_ICON[e.type]
        return (
          <li key={i} className="flex items-start gap-3">
            <div
              className={cn(
                'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-raised',
                TYPE_CLASS[e.type],
              )}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden />
            </div>
            <div className="min-w-0">
              <p className="text-sm text-text">{e.label}</p>
              <p className="text-xs text-subtle">{new Date(e.date).toLocaleDateString()}</p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
