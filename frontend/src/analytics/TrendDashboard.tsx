import { useState } from 'react'
import { useAnalyticsDashboard, type Granularity } from '@/lib/queries/analytics-dashboard'
import { SummaryCards } from './SummaryCards'
import { CrimeTimeline } from './CrimeTimeline'
import { CrimeTypeCharts } from './CrimeTypeCharts'
import { HotspotMap } from './HotspotMap'
import { ClusterView } from './ClusterView'
import { ModusOperandiSummary } from './ModusOperandiSummary'

// Mirrors backend/database/models/enums.py CrimeType — kept in sync
// manually since there's no /enums or /metadata endpoint exposing this
// yet. If crime types change often, that's worth adding.
const CRIME_TYPES = ['theft', 'burglary', 'fraud', 'cybercrime', 'assault', 'drug_trafficking'] as const
const GRANULARITIES: { value: Granularity; label: string }[] = [
  { value: 'day', label: 'Daily' },
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
  { value: 'quarter', label: 'Quarterly' },
  { value: 'year', label: 'Yearly' },
]
// Mirrors backend/database/models/enums.py Gender.
const GENDERS = ['male', 'female', 'other'] as const
// Age BANDS as ranges, not a stored field — matches modus_engine._age_band's
// cutoffs so "18-30" here means the same thing as in the MO enrichment card.
const AGE_BANDS: { value: string; label: string; min: number; max: number }[] = [
  { value: 'under18', label: 'Under 18', min: 0, max: 17 },
  { value: '18-30', label: '18-30', min: 18, max: 30 },
  { value: '31-45', label: '31-45', min: 31, max: 45 },
  { value: '46-60', label: '46-60', min: 46, max: 60 },
  { value: '60plus', label: '60+', min: 61, max: 120 },
]

function FilterSelect<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: T | ''
  onChange: (v: T | '') => void
  options: { value: T; label: string }[]
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T | '')}
        className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function TrendDashboard() {
  const [crimeType, setCrimeType] = useState<string>('')
  const [district, setDistrict] = useState<string>('')
  const [granularity, setGranularity] = useState<Granularity>('month')
  const [victimGender, setVictimGender] = useState<string>('')
  const [ageBand, setAgeBand] = useState<string>('')

  const selectedAgeBand = AGE_BANDS.find((b) => b.value === ageBand)

  const { data, isLoading, isError } = useAnalyticsDashboard({
    crimeType: crimeType || undefined,
    district: district || undefined,
    granularity,
    victimGender: (victimGender || undefined) as 'male' | 'female' | 'other' | undefined,
    victimAgeMin: selectedAgeBand?.min,
    victimAgeMax: selectedAgeBand?.max,
  })

  // District options come from the payload itself (top_districts) rather
  // than a separate lookup — once loaded once, switching the district
  // filter doesn't need a new list; it's re-derived each response.
  const districtOptions = (data?.tables.top_districts ?? []).map((d) => ({ value: d.district, label: d.district }))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-text">Crime Pattern &amp; Trend Analytics</h2>
          <p className="text-xs text-muted">Computed directly from crime records — no agent query in the loop.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <FilterSelect
            label="Crime type"
            value={crimeType}
            onChange={setCrimeType}
            options={CRIME_TYPES.map((t) => ({ value: t, label: t.replaceAll('_', ' ') }))}
          />
          <FilterSelect label="District" value={district} onChange={setDistrict} options={districtOptions} />
          <FilterSelect
            label="Victim gender"
            value={victimGender}
            onChange={setVictimGender}
            options={GENDERS.map((g) => ({ value: g, label: g }))}
          />
          <FilterSelect
            label="Victim age"
            value={ageBand}
            onChange={setAgeBand}
            options={AGE_BANDS.map((b) => ({ value: b.value, label: b.label }))}
          />
          <FilterSelect
            label="Granularity"
            value={granularity}
            onChange={(v) => setGranularity((v || 'month') as Granularity)}
            options={GRANULARITIES}
          />
        </div>
      </div>

      {isError && (
        <p className="text-xs text-critical">Dashboard failed to load — check the backend is reachable.</p>
      )}

      <SummaryCards
        kpiCards={data?.kpi_cards}
        executiveSummary={data?.executive_summary}
        recommendations={data?.recommendations}
        isLoading={isLoading}
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <CrimeTimeline trend={data?.charts.trend} isLoading={isLoading} />
        <CrimeTypeCharts typeDistribution={data?.charts.type_distribution} isLoading={isLoading} />
      </div>

      <HotspotMap heatmap={data?.charts.heatmap} topHotspots={data?.tables.top_hotspots} isLoading={isLoading} />

      <ModusOperandiSummary enrichment={data?.mo_enrichment} isLoading={isLoading} />

      <ClusterView
        spikes={data?.insights.spikes}
        outbreaks={data?.insights.outbreaks}
        emergingCategories={data?.insights.emerging_categories}
        repeatIncidentClusters={data?.insights.repeat_incident_clusters}
        festivalConcentration={data?.insights.festival_concentration}
        isLoading={isLoading}
      />
    </div>
  )
}
