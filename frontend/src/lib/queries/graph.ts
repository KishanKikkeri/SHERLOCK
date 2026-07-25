import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { GraphNodeType, GraphResponse, GraphSearchResponse } from '@/lib/types'

export function useGraph(personId: number | undefined, hops: number) {
  return useQuery({
    queryKey: ['graph', personId, hops],
    queryFn: () => apiFetch<GraphResponse>(`/graph/${personId}?hops=${hops}`),
    enabled: personId !== undefined,
    staleTime: 60 * 1000,
  })
}

/** Priority 21 — center-and-expand on any node type, not just Person. */
export function useEntityGraph(
  nodeType: GraphNodeType | undefined,
  entityId: number | undefined,
  hops: number,
) {
  return useQuery({
    queryKey: ['graph', 'node', nodeType, entityId, hops],
    queryFn: () => apiFetch<GraphResponse>(`/graph/node/${nodeType}/${entityId}?hops=${hops}`),
    enabled: nodeType !== undefined && entityId !== undefined,
    staleTime: 60 * 1000,
  })
}

/** Priority 18-20 — unified identifier search: name, alias, vehicle
 * number, phone, bank account, weapon serial, FIR/crime number,
 * org/gang name, address, location, district, state, or crime type.
 * `caseId` boosts ranking for entities already connected to that case
 * (Priority 23). Caller is responsible for debouncing `query`. */
export function useGraphSearch(query: string, caseId?: number) {
  const trimmed = query.trim()
  return useQuery({
    queryKey: ['graph-search', trimmed, caseId],
    queryFn: () =>
      apiFetch<GraphSearchResponse>(
        `/graph/search?q=${encodeURIComponent(trimmed)}${caseId ? `&case_id=${caseId}` : ''}`,
      ),
    enabled: trimmed.length > 0,
    staleTime: 30 * 1000,
  })
}
