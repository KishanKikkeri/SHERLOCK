import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { ForecastDashboard } from '@/lib/types'

/** GET /forecast/dashboard — see backend/api/forecast.py. Deterministic,
 * no LLM call anywhere in the pipeline behind this endpoint. */
export function useForecastDashboard() {
  return useQuery({
    queryKey: ['forecast-dashboard'],
    queryFn: () => apiFetch<ForecastDashboard>('/forecast/dashboard'),
    staleTime: 60 * 1000,
  })
}
