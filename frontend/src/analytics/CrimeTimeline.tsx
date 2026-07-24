import { useMemo, useState } from 'react'
import type { TrendSeries } from '@/lib/queries/analytics-dashboard'
import { Card, CardHeader, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { TrendingUp } from 'lucide-react'

const WIDTH = 640
const HEIGHT = 220
const PAD = { top: 16, right: 16, bottom: 28, left: 36 }

function buildPath(values: number[], scaleX: (i: number) => number, scaleY: (v: number) => number): string {
  return values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${scaleX(i)} ${scaleY(v)}`).join(' ')
}

export function CrimeTimeline({ trend, isLoading }: { trend: TrendSeries | undefined; isLoading: boolean }) {
  const [showRollingAvg, setShowRollingAvg] = useState(true)

  const chart = useMemo(() => {
    if (!trend || trend.series.length === 0) return null

    const counts = trend.series.map((p) => p.count)
    const avgs = trend.series.map((p) => p.rolling_avg)
    const maxVal = Math.max(...counts, ...avgs, 1)
    const n = trend.series.length

    const innerW = WIDTH - PAD.left - PAD.right
    const innerH = HEIGHT - PAD.top - PAD.bottom

    const scaleX = (i: number) => PAD.left + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW)
    const scaleY = (v: number) => PAD.top + innerH - (v / maxVal) * innerH

    const linePath = buildPath(counts, scaleX, scaleY)
    const areaPath = `${linePath} L ${scaleX(n - 1)} ${PAD.top + innerH} L ${scaleX(0)} ${PAD.top + innerH} Z`
    const avgPath = buildPath(avgs, scaleX, scaleY)

    // Sparse x-axis labels — every Nth period, capped at ~6 labels
    const labelStep = Math.max(1, Math.ceil(n / 6))

    return { linePath, areaPath, avgPath, scaleX, scaleY, maxVal, labelStep }
  }, [trend])

  return (
    <Card>
      <CardHeader
        title="Crime trend over time"
        subtitle={trend ? `${trend.granularity} buckets · ${trend.total} total` : undefined}
        action={
          trend && (
            <Badge tone={trend.growth.direction === 'up' ? 'critical' : trend.growth.direction === 'down' ? 'positive' : 'neutral'}>
              {trend.growth.direction === 'up' ? '+' : ''}
              {trend.growth.pct_change}% {trend.growth.partial_excluded ? 'vs. last complete period' : 'vs. previous'}
            </Badge>
          )
        }
      />
      <CardBody>
        {isLoading && <Skeleton className="h-[220px] w-full" />}

        {!isLoading && !chart && (
          <EmptyState
            icon={<TrendingUp className="h-6 w-6" />}
            title="No trend data"
            description="No crimes recorded in the current filter scope."
          />
        )}

        {!isLoading && chart && trend && (
          <div className="flex flex-col gap-2">
            <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" role="img" aria-label="Crime count trend over time">
              {/* gridlines */}
              {[0, 0.25, 0.5, 0.75, 1].map((f) => (
                <line
                  key={f}
                  x1={PAD.left}
                  x2={WIDTH - PAD.right}
                  y1={PAD.top + f * (HEIGHT - PAD.top - PAD.bottom)}
                  y2={PAD.top + f * (HEIGHT - PAD.top - PAD.bottom)}
                  stroke="var(--border)"
                  strokeWidth={1}
                />
              ))}

              <path d={chart.areaPath} fill="var(--accent)" opacity={0.12} />
              <path d={chart.linePath} fill="none" stroke="var(--accent)" strokeWidth={2} />
              {showRollingAvg && (
                <path d={chart.avgPath} fill="none" stroke="var(--text-subtle, var(--muted))" strokeWidth={1.5} strokeDasharray="4 3" />
              )}

              {trend.series.map((p, i) => (
                <g key={p.period}>
                  <circle
                    cx={chart.scaleX(i)}
                    cy={chart.scaleY(p.count)}
                    r={p.partial ? 3.5 : 2.5}
                    fill={p.partial ? 'var(--surface)' : 'var(--accent)'}
                    stroke="var(--accent)"
                    strokeWidth={p.partial ? 1.5 : 0}
                  >
                    <title>{`${p.period}${p.partial ? ' (in progress)' : ''}: ${p.count} (rolling avg ${p.rolling_avg})`}</title>
                  </circle>
                  {(i % chart.labelStep === 0 || p.partial) && (
                    <text
                      x={chart.scaleX(i)}
                      y={HEIGHT - 8}
                      textAnchor="middle"
                      fontSize={9}
                      fill="var(--muted)"
                      fontStyle={p.partial ? 'italic' : 'normal'}
                      className="font-mono"
                    >
                      {p.period}
                      {p.partial ? '*' : ''}
                    </text>
                  )}
                </g>
              ))}
            </svg>

            {trend.partial_period && (
              <p className="text-[11px] italic text-muted">* {trend.partial_period} is still in progress — excluded from the trend comparison above.</p>
            )}

            <button
              type="button"
              onClick={() => setShowRollingAvg((v) => !v)}
              className="self-start text-[11px] text-muted hover:text-text"
            >
              {showRollingAvg ? 'Hide' : 'Show'} rolling average
            </button>
          </div>
        )}
      </CardBody>
    </Card>
  )
}
