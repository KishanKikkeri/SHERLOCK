import type { TypeDistribution, ConfidenceTier } from '@/lib/queries/analytics-dashboard'
import { Card, CardHeader, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { PieChart } from 'lucide-react'

function confidenceTone(tier: ConfidenceTier['tier']): 'positive' | 'warning' | 'neutral' {
  if (tier === 'high') return 'positive'
  if (tier === 'medium') return 'warning'
  return 'neutral'
}

export function CrimeTypeCharts({
  typeDistribution,
  isLoading,
}: {
  typeDistribution: TypeDistribution | undefined
  isLoading: boolean
}) {
  const entries = typeDistribution
    ? Object.entries(typeDistribution.distribution).sort((a, b) => b[1] - a[1])
    : []
  const maxCount = Math.max(...entries.map(([, n]) => n), 1)
  const growthByType = new Map(typeDistribution?.type_growth.map((g) => [g.crime_type, g]) ?? [])

  return (
    <Card>
      <CardHeader
        title="Crime type distribution"
        subtitle={
          typeDistribution?.excluded_partial_period
            ? `Share of total · growth excludes in-progress ${typeDistribution.excluded_partial_period}`
            : 'Share of total, with month-over-month growth'
        }
      />
      <CardBody>
        {isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        )}

        {!isLoading && entries.length === 0 && (
          <EmptyState icon={<PieChart className="h-6 w-6" />} title="No crime types" description="No crimes recorded in the current filter scope." />
        )}

        {!isLoading && entries.length > 0 && (
          <div className="flex flex-col gap-2.5">
            {entries.map(([type, count]) => {
              const widthPct = (count / maxCount) * 100
              const growth = growthByType.get(type)

              return (
                <div key={type} className="flex items-center gap-3">
                  <span className="w-32 shrink-0 truncate text-xs text-muted" title={type}>
                    {type.replaceAll('_', ' ')}
                  </span>
                  <div className="relative h-5 flex-1 overflow-hidden rounded-sm bg-surface-raised">
                    <div
                      className="h-full rounded-sm bg-accent/70"
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                  <span className="mono w-8 shrink-0 text-right text-xs text-text">{count}</span>
                  {growth && growth.direction !== 'flat' && (
                    <span
                      className={`mono shrink-0 text-xs ${growth.direction === 'up' ? 'text-critical' : 'text-positive'}`}
                      title={`${growth.current} vs. ${growth.previous} previous period`}
                    >
                      {growth.direction === 'up' ? '↑' : '↓'} {Math.abs(growth.pct_change)}%
                    </span>
                  )}
                  {growth && (
                    <Badge tone={confidenceTone(growth.confidence.tier)} className="shrink-0" title={growth.confidence.reason}>
                      {growth.confidence.tier} confidence
                    </Badge>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
