import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { AuditLogEntry, RetentionPolicy } from '@/lib/types'

export function useAuditLog(filters: { action?: string; success?: boolean } = {}) {
  const query = new URLSearchParams()
  if (filters.action) query.set('action', filters.action)
  if (filters.success !== undefined) query.set('success', String(filters.success))
  const qs = query.toString()

  return useQuery({
    queryKey: ['audit', filters],
    queryFn: () => apiFetch<AuditLogEntry[]>(`/audit${qs ? `?${qs}` : ''}`),
  })
}

export function useRetentionPolicy() {
  return useQuery({
    queryKey: ['governance', 'retention-policy'],
    queryFn: () => apiFetch<RetentionPolicy>('/governance/retention-policy'),
  })
}

export function useRunRetentionSweep() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/governance/retention/run', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['governance'] }),
  })
}
