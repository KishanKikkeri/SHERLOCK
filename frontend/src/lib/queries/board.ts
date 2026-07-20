import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type {
  BoardIntelligence,
  BoardObject,
  BoardObjectType,
  Comment,
  CommentTargetType,
  DecisionTimelineEntry,
  ReviewRequestRecord,
} from '@/lib/types'

export function useBoardIntelligence(sessionId: number | undefined) {
  return useQuery({
    queryKey: ['board-intelligence', sessionId],
    queryFn: () => apiFetch<BoardIntelligence>(`/sessions/${sessionId}/board`),
    enabled: sessionId !== undefined,
    staleTime: 30 * 1000,
  })
}

export function useDecisionTimeline(sessionId: number | undefined) {
  return useQuery({
    queryKey: ['timeline', 'decisions', sessionId],
    queryFn: () => apiFetch<DecisionTimelineEntry[]>(`/sessions/${sessionId}/timeline/decisions`),
    enabled: sessionId !== undefined,
    staleTime: 30 * 1000,
  })
}

export function useBoardObjects(sessionId: number | undefined) {
  return useQuery({
    queryKey: ['board-objects', sessionId],
    queryFn: () => apiFetch<BoardObject[]>(`/sessions/${sessionId}/board-objects`),
    enabled: sessionId !== undefined,
    staleTime: 15 * 1000,
  })
}

export function useCreateBoardObject(sessionId: number | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      object_type: BoardObjectType
      content: string
      payload?: Record<string, unknown>
      created_by_officer_id?: number
    }) => apiFetch<BoardObject>(`/sessions/${sessionId}/board-objects`, { method: 'POST', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['board-objects', sessionId] }),
  })
}

export function useUpdateBoardObject(sessionId: number | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number
      content?: string
      payload?: Record<string, unknown>
      actor_officer_id?: number
    }) => apiFetch<BoardObject>(`/board-objects/${id}`, { method: 'PATCH', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['board-objects', sessionId] }),
  })
}

export function useComments(sessionId: number | undefined, targetType?: CommentTargetType, targetRef?: string) {
  const query = new URLSearchParams()
  if (targetType) query.set('target_type', targetType)
  if (targetRef) query.set('target_ref', targetRef)
  const qs = query.toString()

  return useQuery({
    queryKey: ['comments', sessionId, targetType, targetRef],
    queryFn: () => apiFetch<Comment[]>(`/sessions/${sessionId}/comments${qs ? `?${qs}` : ''}`),
    enabled: sessionId !== undefined && targetRef !== undefined,
    staleTime: 15 * 1000,
  })
}

export function useAddComment(sessionId: number | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      target_type: CommentTargetType
      target_ref: string
      body: string
      author_officer_id?: number
    }) => apiFetch<Comment>(`/sessions/${sessionId}/comments`, { method: 'POST', body }),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({
        queryKey: ['comments', sessionId, variables.target_type, variables.target_ref],
      }),
  })
}

export function useReviews(sessionId: number | undefined) {
  return useQuery({
    queryKey: ['reviews', sessionId],
    queryFn: () => apiFetch<ReviewRequestRecord[]>(`/sessions/${sessionId}/reviews`),
    enabled: sessionId !== undefined,
    staleTime: 15 * 1000,
  })
}

export function useRequestReview(sessionId: number | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { requested_by_officer_id?: number; reviewer_officer_id?: number; notes?: string }) =>
      apiFetch<ReviewRequestRecord>(`/sessions/${sessionId}/reviews`, { method: 'POST', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reviews', sessionId] }),
  })
}

export function useDecideReview(sessionId: number | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      reviewId,
      ...body
    }: {
      reviewId: number
      approve: boolean
      actor_officer_id?: number
      decision_notes?: string
    }) => apiFetch<ReviewRequestRecord>(`/reviews/${reviewId}/decide`, { method: 'POST', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reviews', sessionId] }),
  })
}
