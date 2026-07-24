import { ClipboardList } from 'lucide-react'
import type { OffenderRecommendation } from '@/lib/types'

export function RecommendationPanel({ recommendations }: { recommendations: OffenderRecommendation[] }) {
  return (
    <ul className="flex flex-col gap-2.5">
      {recommendations.map((r, i) => (
        <li key={i} className="flex gap-2.5 rounded-md border border-border bg-surface-raised p-3">
          <ClipboardList className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
          <div>
            <p className="text-sm font-medium text-text">{r.action}</p>
            <p className="text-xs text-muted">{r.because}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}
