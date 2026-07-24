import { useMutation, useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type {
  OffenderNetworkProfile,
  OffenderProfile,
  OffenderProfileSummary,
  OffenderTimelineEvent,
} from '@/lib/types'

export function useOffenderProfile(personId: number | undefined) {
  return useQuery({
    queryKey: ['offender-profile', personId],
    queryFn: () => apiFetch<OffenderProfile>(`/persons/${personId}/profile`),
    enabled: personId !== undefined,
    staleTime: 60 * 1000,
  })
}

export function useHighRiskPersons(minRisk: number, limit = 20) {
  return useQuery({
    queryKey: ['offender-high-risk', minRisk, limit],
    queryFn: () =>
      apiFetch<{ min_risk: number; count: number; persons: OffenderProfileSummary[] }>(
        `/persons/high-risk?min_risk=${minRisk}&limit=${limit}`,
      ),
    staleTime: 30 * 1000,
  })
}

export function useProfileSearch() {
  return useMutation({
    mutationFn: (filters: {
      name_contains?: string
      min_risk?: number
      crime_type?: string
      district?: string
      limit?: number
    }) =>
      apiFetch<{ count: number; persons: OffenderProfileSummary[] }>('/persons/profile/search', {
        method: 'POST',
        body: filters,
      }),
  })
}

export function useOffenderTimeline(personId: number | undefined) {
  return useQuery({
    queryKey: ['offender-timeline', personId],
    queryFn: () =>
      apiFetch<{ person_id: number; name: string; event_count: number; events: OffenderTimelineEvent[] }>(
        `/persons/${personId}/timeline`,
      ),
    enabled: personId !== undefined,
  })
}

export function useOffenderNetwork(personId: number | undefined) {
  return useQuery({
    queryKey: ['offender-network', personId],
    queryFn: () =>
      apiFetch<{ person_id: number; name: string } & OffenderNetworkProfile>(`/persons/${personId}/network`),
    enabled: personId !== undefined,
  })
}
