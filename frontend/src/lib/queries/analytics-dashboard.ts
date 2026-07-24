import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'

export type Granularity = 'day' | 'week' | 'month' | 'quarter' | 'year'

export interface DashboardFilters {
  crimeType?: string
  district?: string
  granularity?: Granularity
  victimGender?: 'male' | 'female' | 'other'
  victimAgeMin?: number
  victimAgeMax?: number
}

export interface KpiCard {
  label: string
  value: string | number
}

export interface TrendPoint {
  period: string
  count: number
  rolling_avg: number
  partial: boolean
}

export interface ConfidenceTier {
  tier: 'high' | 'medium' | 'low'
  periods_of_history: number
  reason: string
}

export interface GrowthIndicator {
  direction: 'up' | 'down' | 'flat'
  pct_change: number
  current: number
  previous: number
  partial_excluded: boolean
  confidence: ConfidenceTier
}

export interface TrendSeries {
  granularity: Granularity
  crime_type: string | null
  district: string | null
  series: TrendPoint[]
  growth: GrowthIndicator
  total: number
  partial_period: string | null
}

export interface YearOverYear {
  current_year: number | null
  previous_year: number | null
  months: { month: number; current: number; previous: number; pct_change: number }[]
  current_year_total: number
  previous_year_total: number
  yoy_pct_change: number
}

export interface TypeGrowthEntry {
  crime_type: string
  direction: 'up' | 'down' | 'flat'
  pct_change: number
  current: number
  previous: number
  confidence: ConfidenceTier
}

export interface TypeDistribution {
  distribution: Record<string, number>
  emerging: string[]
  declining: string[]
  type_growth: TypeGrowthEntry[]
  excluded_partial_period: string | null
}

export interface HeatmapPoint {
  lat: number
  lng: number
  weight: number
  location: string
}

export interface SeasonalDistribution {
  distribution: Record<string, number>
  dominant_season: string | null
  dominant_share: number
}

export interface WeekendVsWeekday {
  weekend_total: number
  weekday_total: number
  weekend_avg_per_day: number
  weekday_avg_per_day: number
  distinct_weekend_days: number
  distinct_weekday_days: number
}

export interface DistrictCount {
  district: string
  count: number
}

export interface HotspotEntry {
  location: string
  district: string
  latitude: number
  longitude: number
  count: number
}

export interface ModusOperandiKeyword {
  keyword: string
  count: number
}

export interface SpikeFlag {
  crime_type: string
  period: string
  z_score: number | null
  method: string
  baseline_mean: number
  baseline_stdev?: number
  current: number
  delta?: number
  expected: number
  observed: number
}

export interface OutbreakFlag {
  district: string
  period: string
  z_score: number | null
  method: string
  baseline_mean: number
  baseline_stdev?: number
  current: number
  delta?: number
  expected: number
  observed: number
}

export interface EmergingCategory {
  crime_type: string
  first_seen_period: string
  count_since_first_seen: number
}

export interface RepeatIncidentCluster {
  location: string
  district: string
  crime_type: string
  occurrences: number
  window_start: string
  window_end: string
}

export interface FestivalConcentration {
  district: string
  festival_count: number
  total: number
  festival_share: number
  flagged: boolean
}

export interface MoEnrichment {
  top_weapon: { weapon_type: string; pct: number } | null
  top_vehicle: { vehicle_type: string; pct: number } | null
  peak_hour_window: { start_hour: number; end_hour: number; share: number } | null
  peak_hour_data_quality: string | null
  common_victim: { gender: string; age_band: string; pct: number } | null
  preferred_escape_route: null
  preferred_escape_route_available: false
}

export interface RecommendationEntry {
  text: string
  confidence: ConfidenceTier
}

export interface DashboardPayload {
  kpi_cards: KpiCard[]
  executive_summary: string
  charts: {
    trend: TrendSeries
    year_over_year: YearOverYear
    type_distribution: TypeDistribution
    heatmap: HeatmapPoint[]
    seasonal: SeasonalDistribution
    weekend_vs_weekday: WeekendVsWeekday
  }
  tables: {
    top_districts: DistrictCount[]
    top_hotspots: HotspotEntry[]
    top_modus_operandi: ModusOperandiKeyword[]
  }
  insights: {
    spikes: SpikeFlag[]
    outbreaks: OutbreakFlag[]
    emerging_categories: EmergingCategory[]
    repeat_incident_clusters: RepeatIncidentCluster[]
    festival_concentration: FestivalConcentration[]
  }
  mo_enrichment: MoEnrichment
  recommendations: RecommendationEntry[]
}

export interface LocationBreakdown {
  location: string
  district: string
  total: number
  by_crime_type: { crime_type: string; count: number }[]
  monthly_timeline: { period: string; count: number }[]
}

export function useAnalyticsDashboard(filters: DashboardFilters = {}) {
  const params = new URLSearchParams()
  if (filters.crimeType) params.set('crime_type', filters.crimeType)
  if (filters.district) params.set('district', filters.district)
  params.set('granularity', filters.granularity ?? 'month')
  if (filters.victimGender) params.set('victim_gender', filters.victimGender)
  if (filters.victimAgeMin !== undefined) params.set('victim_age_min', String(filters.victimAgeMin))
  if (filters.victimAgeMax !== undefined) params.set('victim_age_max', String(filters.victimAgeMax))

  return useQuery({
    queryKey: ['analytics-dashboard', filters],
    queryFn: () => apiFetch<DashboardPayload>(`/analytics/dashboard?${params.toString()}`),
    staleTime: 60 * 1000,
  })
}

export function useHotspotBreakdown(locationName: string | null) {
  return useQuery({
    queryKey: ['analytics-hotspot', locationName],
    queryFn: () => apiFetch<LocationBreakdown>(`/analytics/hotspot/${encodeURIComponent(locationName!)}`),
    enabled: locationName !== null,
    staleTime: 60 * 1000,
  })
}
