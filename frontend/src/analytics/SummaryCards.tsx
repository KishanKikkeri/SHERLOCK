import { TrendingUp, TrendingDown, Minus, Lightbulb } from 'lucide-react'
import type { KpiCard, RecommendationEntry, ConfidenceTier } from '@/lib/queries/analytics-dashboard'
import { Card, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'

function directionOf(value: string | number): 'up' | 'down' | 'flat' | null {
  if (typeof value !== 'string') return null
  if (value.startsWith('up')) return 'up'
  if (value.startsWith('down')) return 'down'
  return null
}

function confidenceTone(tier: ConfidenceTier['tier']): 'positive' | 'warning' | 'neutral' {
  if (tier === 'high') return 'positive'
  if (tier === 'medium') return 'warning'
  return 'neutral'
}

function KpiTile({ card }: { card: KpiCard }) {
  const direction = directionOf(card.value)
  const Icon = direction === 'up' ? TrendingUp : direction === 'down' ? TrendingDown : Minus

  return (
    <Card>
      <CardBody className="flex flex-col gap-1.5 p-4">
        <p className="text-xs text-muted">{card.label}</p>
        <div className="flex items-center gap-1.5">
          {direction && (
            <Icon
              className={`h-4 w-4 shrink-0 ${direction === 'up' ? 'text-critical' : 'text-positive'}`}
              aria-hidden
            />
          )}
          <p className="mono truncate text-lg font-semibold text-text">{card.value}</p>
        </div>
      </CardBody>
    </Card>
  )
}

export function SummaryCards({
  kpiCards,
  executiveSummary,
  recommendations,
  isLoading,
}: {
  kpiCards: KpiCard[] | undefined
  executiveSummary: string | undefined
  recommendations: RecommendationEntry[] | undefined
  isLoading: boolean
}) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[72px] w-full" />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {kpiCards?.map((card) => (
          <KpiTile key={card.label} card={card} />
        ))}
      </div>

      <Card>
        <CardBody className="flex flex-col gap-3">
          <div>
            <p className="text-xs font-semibold text-muted">Executive summary</p>
            <p className="mt-1 text-sm text-text">{executiveSummary}</p>
          </div>

          {recommendations && recommendations.length > 0 && (
            <div className="border-t border-border pt-3">
              <p className="text-xs font-semibold text-muted">Recommendations</p>
              <ul className="mt-1.5 flex flex-col gap-1.5">
                {recommendations.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text">
                    <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />
                    <span className="flex-1">{rec.text}</span>
                    <Badge tone={confidenceTone(rec.confidence.tier)} className="shrink-0" title={rec.confidence.reason}>
                      {rec.confidence.tier} confidence
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
