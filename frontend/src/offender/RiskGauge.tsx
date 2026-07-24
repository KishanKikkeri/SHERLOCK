import { cn } from '@/lib/cn'
import type { OffenderRiskProfile } from '@/lib/types'

const BAND_COLOR: Record<OffenderRiskProfile['band'], string> = {
  'Very Low': 'var(--color-positive)',
  Low: 'var(--color-positive)',
  Medium: 'var(--color-warning)',
  High: 'var(--color-critical)',
  Critical: 'var(--color-critical)',
}

const BAND_TEXT_CLASS: Record<OffenderRiskProfile['band'], string> = {
  'Very Low': 'text-positive',
  Low: 'text-positive',
  Medium: 'text-warning',
  High: 'text-critical',
  Critical: 'text-critical',
}

export function RiskGauge({ risk }: { risk: OffenderRiskProfile }) {
  const radius = 46
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - risk.overall_score / 100)
  const color = BAND_COLOR[risk.band]

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-32 w-32">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="var(--color-border)" strokeWidth="8" />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 400ms ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold text-text">{risk.overall_score}</span>
          <span className="text-[10px] text-muted">/ 100</span>
        </div>
      </div>
      <span className={cn('text-sm font-medium', BAND_TEXT_CLASS[risk.band])}>{risk.band} risk</span>
    </div>
  )
}
