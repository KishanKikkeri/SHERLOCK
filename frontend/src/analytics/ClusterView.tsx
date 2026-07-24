import { AlertTriangle, Flame, Sparkles, Repeat, PartyPopper } from 'lucide-react'
import type {
  SpikeFlag, OutbreakFlag, EmergingCategory, RepeatIncidentCluster, FestivalConcentration,
} from '@/lib/queries/analytics-dashboard'
import { Card, CardHeader, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'

function InsightRow({ icon, children, tone }: { icon: React.ReactNode; children: React.ReactNode; tone: 'critical' | 'warning' }) {
  return (
    <div className="flex items-start gap-2.5 rounded-md border border-border bg-surface-raised p-2.5">
      <span className={tone === 'critical' ? 'text-critical' : 'text-warning'} aria-hidden>
        {icon}
      </span>
      <p className="text-sm text-text">{children}</p>
    </div>
  )
}

export function ClusterView({
  spikes,
  outbreaks,
  emergingCategories,
  repeatIncidentClusters,
  festivalConcentration,
  isLoading,
}: {
  spikes: SpikeFlag[] | undefined
  outbreaks: OutbreakFlag[] | undefined
  emergingCategories: EmergingCategory[] | undefined
  repeatIncidentClusters: RepeatIncidentCluster[] | undefined
  festivalConcentration: FestivalConcentration[] | undefined
  isLoading: boolean
}) {
  const flaggedFestivals = festivalConcentration?.filter((f) => f.flagged) ?? []
  const totalInsights =
    (spikes?.length ?? 0) + (outbreaks?.length ?? 0) + (emergingCategories?.length ?? 0) +
    (repeatIncidentClusters?.length ?? 0) + flaggedFestivals.length

  return (
    <Card>
      <CardHeader
        title="Emerging crime clusters"
        subtitle="Spikes, outbreaks, new categories, and repeat-incident sites — flagged against rolling historical baselines"
        action={totalInsights > 0 ? <Badge tone="critical">{totalInsights} flagged</Badge> : undefined}
      />
      <CardBody>
        {isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        )}

        {!isLoading && totalInsights === 0 && (
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="Nothing flagged"
            description="No spikes, outbreaks, new categories, or repeat-incident sites in the current filter scope."
          />
        )}

        {!isLoading && totalInsights > 0 && (
          <div className="flex flex-col gap-2">
            {spikes?.map((s) => (
              <InsightRow key={`spike-${s.crime_type}-${s.period}`} icon={<AlertTriangle className="h-4 w-4" />} tone="critical">
                Spike in <strong>{s.crime_type.replaceAll('_', ' ')}</strong> during {s.period} — {s.current} cases vs. a baseline of{' '}
                {s.baseline_mean}
                {s.z_score !== null ? ` (z = ${s.z_score})` : ''}.
              </InsightRow>
            ))}

            {outbreaks?.map((o) => (
              <InsightRow key={`outbreak-${o.district}-${o.period}`} icon={<Flame className="h-4 w-4" />} tone="critical">
                Localized outbreak in <strong>{o.district}</strong> during {o.period} — {o.current} cases vs. a baseline of{' '}
                {o.baseline_mean}
                {o.z_score !== null ? ` (z = ${o.z_score})` : ''}.
              </InsightRow>
            ))}

            {emergingCategories?.map((e) => (
              <InsightRow key={`emerging-${e.crime_type}`} icon={<Sparkles className="h-4 w-4" />} tone="warning">
                New crime category <strong>{e.crime_type.replaceAll('_', ' ')}</strong> first appeared {e.first_seen_period} —{' '}
                {e.count_since_first_seen} case(s) since.
              </InsightRow>
            ))}

            {repeatIncidentClusters?.map((r) => (
              <InsightRow key={`repeat-${r.location}-${r.crime_type}`} icon={<Repeat className="h-4 w-4" />} tone="warning">
                <strong>{r.location}</strong> ({r.district}) — {r.occurrences} {r.crime_type.replaceAll('_', ' ')} incidents between{' '}
                {r.window_start} and {r.window_end}.
              </InsightRow>
            ))}

            {flaggedFestivals.map((f) => (
              <InsightRow key={`festival-${f.district}`} icon={<PartyPopper className="h-4 w-4" />} tone="warning">
                <strong>{f.district}</strong> — {(f.festival_share * 100).toFixed(0)}% of cases ({f.festival_count} of {f.total}) fall in
                festival season (Sep–Nov).
              </InsightRow>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
