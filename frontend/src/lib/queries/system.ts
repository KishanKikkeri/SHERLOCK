import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { HealthResponse, MetricsResponse } from '@/lib/types'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<HealthResponse>('/health', { skipAuth: true, skipRefresh: true }),
    refetchInterval: 30 * 1000,
    retry: 1,
  })
}

export function useMetrics(enabled: boolean) {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: () => apiFetch<MetricsResponse>('/metrics'),
    enabled,
    staleTime: 60 * 1000,
  })
}
