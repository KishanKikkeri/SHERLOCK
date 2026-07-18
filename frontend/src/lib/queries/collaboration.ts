import { useQueries, useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type {
  ActivityFeedItem,
  DiscussionRecord,
  InvestigationSession,
  NotificationOut,
} from '@/lib/types'

export function useNotifications(officerId: number | null | undefined) {
  return useQuery({
    queryKey: ['notifications', officerId],
    queryFn: () => apiFetch<NotificationOut[]>(`/officers/${officerId}/notifications`),
    enabled: officerId !== null && officerId !== undefined,
    refetchInterval: 30 * 1000,
  })
}

/**
 * There is no global `/activity-feed` endpoint — only the per-session
 * `GET /sessions/{id}/activity-feed` (backend/api/collaboration.py).
 * The dashboard's "Activity feed" panel composes this client-side from
 * the most recently updated sessions the user can see. This is a
 * deliberate workaround, not an invented contract — see the F1
 * validation report's "known limitations" section. If a real
 * cross-session feed endpoint gets added later, swap this hook's body
 * for a single call and delete the composition logic below.
 */
export function useDashboardActivityFeed(sessions: InvestigationSession[] | undefined) {
  const topSessionIds = (sessions ?? [])
    .slice()
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 5)
    .map((s) => s.id)

  const results = useQueries({
    queries: topSessionIds.map((id) => ({
      queryKey: ['activity-feed', id],
      queryFn: () => apiFetch<ActivityFeedItem[]>(`/sessions/${id}/activity-feed`),
      staleTime: 30 * 1000,
    })),
  })

  const isLoading = results.some((r) => r.isLoading)
  const items = results
    .flatMap((r) => r.data ?? [])
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 15)

  return { items, isLoading }
}

/**
 * Same caveat as useDashboardActivityFeed: no global "recent discussions"
 * endpoint exists (only GET /sessions/{id}/discussions), so this composes
 * one client-side from the same top-5-recent-sessions set.
 */
export function useDashboardDiscussions(sessions: InvestigationSession[] | undefined) {
  const topSessionIds = (sessions ?? [])
    .slice()
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 5)
    .map((s) => s.id)

  const results = useQueries({
    queries: topSessionIds.map((id) => ({
      queryKey: ['discussions', id],
      queryFn: () => apiFetch<DiscussionRecord[]>(`/sessions/${id}/discussions`),
      staleTime: 30 * 1000,
    })),
  })

  const isLoading = results.some((r) => r.isLoading)
  const items = results
    .flatMap((r) => r.data ?? [])
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 8)

  return { items, isLoading }
}
