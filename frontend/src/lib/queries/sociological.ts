import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { SociologicalDashboard, SociologicalReport } from '@/lib/types'

/**
 * Unlike frontend/src/lib/queries/analytics.ts's useAnalyticsQuery (which
 * has to go through POST /voice/command because there's no dedicated
 * endpoint for those topics), the Sociological Insights dashboard has a
 * real, dedicated, non-conversational endpoint — GET /analytics/sociological
 * — because a chart-based dashboard needs structured numeric data, not a
 * narrative. See backend/api/sociological.py.
 */
export function useSociologicalDashboard() {
  return useQuery({
    queryKey: ['sociological-dashboard'],
    queryFn: () => apiFetch<SociologicalDashboard>('/analytics/sociological'),
    staleTime: 60 * 1000,
  })
}

export function useSociologicalReport(enabled: boolean) {
  return useQuery({
    queryKey: ['sociological-report'],
    queryFn: () => apiFetch<SociologicalReport>('/analytics/sociological/report'),
    enabled,
    staleTime: 60 * 1000,
  })
}
