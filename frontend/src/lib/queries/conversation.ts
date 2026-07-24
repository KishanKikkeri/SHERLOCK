import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_BASE_URL, apiFetch } from '@/lib/api-client'
import { useAuthStore } from '@/store/auth-store'
import type {
  ConversationHistoryMessage,
  ConversationMessageResult,
  ConversationStreamEvent,
  ConversationSummaryResult,
} from '@/lib/types'

export function useConversationHistory(sessionId: number | undefined) {
  return useQuery({
    queryKey: ['conversation', sessionId, 'history'],
    queryFn: () =>
      apiFetch<{ session_id: number; messages: ConversationHistoryMessage[] }>(
        `/conversation/${sessionId}/history`,
      ),
    enabled: sessionId !== undefined,
  })
}

export function useSendConversationMessage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { sessionId?: number; message: string; language?: string; enableDiscussion?: boolean }) =>
      apiFetch<ConversationMessageResult>('/conversation/message', {
        method: 'POST',
        body: {
          session_id: body.sessionId,
          message: body.message,
          language: body.language,
          enable_discussion: body.enableDiscussion ?? false,
        },
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['conversation', data.session_id, 'history'] })
    },
  })
}

export function useSummarizeConversation() {
  return useMutation({
    mutationFn: (sessionId: number) =>
      apiFetch<ConversationSummaryResult>(`/conversation/${sessionId}/summarize`, { method: 'POST' }),
  })
}

export function useClearConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: number) =>
      apiFetch<{ session_id: number; archived_turns: number }>(`/conversation/${sessionId}/history`, {
        method: 'DELETE',
      }),
    onSuccess: (_data, sessionId) => {
      queryClient.invalidateQueries({ queryKey: ['conversation', sessionId, 'history'] })
    },
  })
}

// Returns an object URL the caller must revoke when done (same pattern as useSpeak).
export function useExportConversationPdf() {
  return useMutation({
    mutationFn: async ({ sessionId, language = 'en' }: { sessionId: number; language?: string }) => {
      const accessToken = useAuthStore.getState().accessToken
      const res = await fetch(`${API_BASE_URL}/conversation/${sessionId}/export/pdf?language=${language}`, {
        method: 'POST',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw { status: res.status, detail: detail.detail ?? res.statusText }
      }
      const blob = await res.blob()
      return { url: URL.createObjectURL(blob), warnings: res.headers.get('X-PDF-Warnings') }
    },
  })
}

/**
 * SSE-driven streaming turn — the `/conversation/stream` counterpart to
 * `/ws/investigate`, for callers that would rather not manage a raw
 * WebSocket. `fetch` + `ReadableStream` reading rather than `EventSource`
 * because EventSource can't send a POST body / custom Authorization
 * header, both of which this endpoint needs.
 */
export async function streamConversationMessage(
  body: { sessionId?: number; message: string; language?: string; enableDiscussion?: boolean },
  onEvent: (event: ConversationStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const accessToken = useAuthStore.getState().accessToken
  const res = await fetch(`${API_BASE_URL}/conversation/stream`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify({
      session_id: body.sessionId,
      message: body.message,
      language: body.language,
      enable_discussion: body.enableDiscussion ?? false,
    }),
  })
  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw { status: res.status, detail: detail.detail ?? res.statusText }
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const jsonText = trimmed.slice('data:'.length).trim()
      if (!jsonText) continue
      try {
        onEvent(JSON.parse(jsonText) as ConversationStreamEvent)
      } catch {
        // Malformed chunk (rare, mid-stream boundary) — skip rather than
        // crash the whole stream over one unparseable event.
      }
    }
  }
}
