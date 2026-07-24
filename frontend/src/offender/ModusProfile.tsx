import { Badge } from '@/components/ui/Badge'
import type { OffenderModusOperandi } from '@/lib/types'

function Chips({ label, values, tone = 'neutral' }: { label: string; values: string[]; tone?: 'neutral' | 'warning' | 'info' | 'critical' }) {
  if (values.length === 0) return null
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {values.map((v) => (
          <Badge key={v} tone={tone}>
            {v}
          </Badge>
        ))}
      </div>
    </div>
  )
}

export function ModusProfile({ modus }: { modus: OffenderModusOperandi }) {
  return (
    <div className="flex flex-col gap-3">
      <Chips label="Weapons used" values={modus.weapon_usage} tone="critical" />
      <Chips label="Vehicles used" values={modus.vehicle_usage} tone="info" />

      {modus.financial_method && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted">Financial method</p>
          <p className="text-sm text-text">{modus.financial_method}</p>
        </div>
      )}

      {modus.location_preference && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted">Location preference</p>
          <p className="text-sm text-text">
            {modus.location_preference.most_common_district} ({modus.location_preference.occurrences} offence(s))
          </p>
        </div>
      )}

      {modus.crime_sequence.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted">Crime sequence</p>
          <p className="text-sm text-text">{modus.crime_sequence.join(' → ')}</p>
        </div>
      )}

      {Object.entries(modus.mo_keyword_buckets).map(([bucket, keywords]) => (
        <Chips key={bucket} label={bucket.replace(/_/g, ' ')} values={keywords} />
      ))}

      {modus.mo_repeat_keywords.length > 0 && (
        <Chips label="Recurring MO terms" values={modus.mo_repeat_keywords} />
      )}

      <p className="text-[11px] italic text-subtle">{modus.mo_clustering_method}</p>
    </div>
  )
}
