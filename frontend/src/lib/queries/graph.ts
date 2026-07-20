import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { GraphResponse } from '@/lib/types'

export function useGraph(personId: number | undefined, hops: number) {
  return useQuery({
    queryKey: ['graph', personId, hops],
    queryFn: () => apiFetch<GraphResponse>(`/graph/${personId}?hops=${hops}`),
    enabled: personId !== undefined,
    staleTime: 60 * 1000,
  })
}
