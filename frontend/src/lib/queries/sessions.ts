import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { InvestigationSession, SessionStatus } from '@/lib/types'

export function useSessions(params: { status?: SessionStatus; ownerOfficerId?: number } = {}) {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  if (params.ownerOfficerId !== undefined) {
    query.set('owner_officer_id', String(params.ownerOfficerId))
  }
  const qs = query.toString()

  return useQuery({
    queryKey: ['sessions', params],
    queryFn: () => apiFetch<InvestigationSession[]>(`/sessions${qs ? `?${qs}` : ''}`),
    staleTime: 30 * 1000,
  })
}

export function useSession(id: number | undefined) {
  return useQuery({
    queryKey: ['sessions', id],
    queryFn: () => apiFetch<InvestigationSession>(`/sessions/${id}`),
    enabled: id !== undefined,
  })
}
