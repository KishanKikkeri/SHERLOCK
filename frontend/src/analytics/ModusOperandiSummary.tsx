import { Swords, Car, Clock, User, HelpCircle } from 'lucide-react'
import type { MoEnrichment } from '@/lib/queries/analytics-dashboard'
import { Card, CardHeader, CardBody, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'

function hourLabel(h: number): string {
  return `${String(h).padStart(2, '0')}:00`
}

function Stat({ icon, label, value, note }: { icon: React.ReactNode; label: string; value: string; note?: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="text-accent" aria-hidden>
        {icon}
      </span>
      <div>
        <p className="text-xs text-muted">{label}</p>
        <p className="mono text-sm text-text">{value}</p>
        {note && <p className="mt-0.5 text-[11px] italic text-muted">{note}</p>}
      </div>
    </div>
  )
}

export function ModusOperandiSummary({
  enrichment,
  isLoading,
}: {
  enrichment: MoEnrichment | undefined
  isLoading: boolean
}) {
  const hasAnySignal =
    enrichment && (enrichment.top_weapon || enrichment.top_vehicle || enrichment.peak_hour_window || enrichment.common_victim)

  return (
    <Card>
      <CardHeader title="Modus operandi profile" subtitle="Weapon/vehicle share, peak timing, and common victim profile" />
      <CardBody>
        {isLoading && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        )}

        {!isLoading && !hasAnySignal && (
          <EmptyState icon={<HelpCircle className="h-6 w-6" />} title="No MO signal yet" description="Not enough weapon/vehicle/victim data in the current filter scope." />
        )}

        {!isLoading && enrichment && hasAnySignal && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {enrichment.top_weapon && (
              <Stat icon={<Swords className="h-4 w-4" />} label="Top weapon" value={`${enrichment.top_weapon.weapon_type.replaceAll('_', ' ')} (${enrichment.top_weapon.pct}%)`} />
            )}
            {enrichment.top_vehicle && (
              <Stat icon={<Car className="h-4 w-4" />} label="Preferred vehicle" value={`${enrichment.top_vehicle.vehicle_type.replaceAll('_', ' ')} (${enrichment.top_vehicle.pct}%)`} />
            )}
            {enrichment.peak_hour_window && (
              <Stat
                icon={<Clock className="h-4 w-4" />}
                label="Peak hour"
                value={`${hourLabel(enrichment.peak_hour_window.start_hour)}\u2013${hourLabel(enrichment.peak_hour_window.end_hour)}`}
                note={`${(enrichment.peak_hour_window.share * 100).toFixed(0)}% of cases in this window`}
              />
            )}
            {enrichment.peak_hour_data_quality && (
              <Stat icon={<Clock className="h-4 w-4" />} label="Peak hour" value="Not available" note={enrichment.peak_hour_data_quality} />
            )}
            {enrichment.common_victim && (
              <Stat
                icon={<User className="h-4 w-4" />}
                label="Common victim"
                value={`${enrichment.common_victim.gender}, ${enrichment.common_victim.age_band}`}
                note={`${enrichment.common_victim.pct}% of identified victims`}
              />
            )}
          </div>
        )}

        {!isLoading && enrichment && !enrichment.preferred_escape_route_available && (
          <p className="mt-3 border-t border-border pt-2 text-[11px] italic text-muted">
            Preferred escape route: not available — there's no route/direction field in the current schema.
          </p>
        )}
      </CardBody>
    </Card>
  )
}
