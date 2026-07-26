import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_BASE_URL, apiFetch } from '@/lib/api-client'
import { useAuthStore } from '@/store/auth-store'

// ---------------------------------------------------------------------------
// Types for V2 API
// ---------------------------------------------------------------------------

export interface InvestigationV2 {
  id: number
  title: string
  description: string | null
  status: 'active' | 'closed' | 'archived'
  created_by_officer_id: number | null
  created_at: string
  updated_at: string
  archived_at: string | null
  selected_firs: number[]
  selected_persons: number[]
  selected_accounts: number[]
  selected_locations: number[]
  selected_orgs: number[]
  metadata: Record<string, any>
}

export interface ConversationV2 {
  id: number
  investigation_id: number | null
  nickname: string
  language: string
  pinned: boolean
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface MessageV2 {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls: Array<{ name: string; arguments: any; call_id: string }> | null
  tool_name: string | null
  tool_result: any | null
  tool_call_id: string | null
  metadata: Record<string, any>
  created_at: string
}

// ---------------------------------------------------------------------------
// Investigations V2 Hooks
// ---------------------------------------------------------------------------

export function useInvestigationsV2(status?: string) {
  return useQuery({
    queryKey: ['v2', 'investigations', status ?? 'all'],
    queryFn: () =>
      apiFetch<InvestigationV2[]>(
        `/v2/investigations${status ? `?status=${status}` : ''}`
      ),
    staleTime: 10 * 1000,
  })
}

export function useInvestigationV2(id: number | undefined) {
  return useQuery({
    queryKey: ['v2', 'investigations', id],
    queryFn: () => apiFetch<InvestigationV2>(`/v2/investigations/${id}`),
    enabled: id !== undefined,
  })
}

export function useCreateInvestigationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      title: string
      description?: string
      selected_firs?: number[]
      selected_persons?: number[]
      selected_accounts?: number[]
      selected_locations?: number[]
      selected_orgs?: number[]
    }) =>
      apiFetch<InvestigationV2>('/v2/investigations', {
        method: 'POST',
        body,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations'] })
    },
  })
}

export function useUpdateInvestigationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number
      title?: string
      description?: string
      status?: 'active' | 'closed' | 'archived'
    }) =>
      apiFetch<InvestigationV2>(`/v2/investigations/${id}`, {
        method: 'PATCH',
        body,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations', data.id] })
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations'] })
    },
  })
}

export function useDeleteInvestigationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ id: number; status: string }>(`/v2/investigations/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations'] })
    },
  })
}

export function useDuplicateInvestigationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<InvestigationV2>(`/v2/investigations/${id}/duplicate`, {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations'] })
    },
  })
}

export function useMergeInvestigationsV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, otherId }: { id: number; otherId: number }) =>
      apiFetch<InvestigationV2>(`/v2/investigations/${id}/merge/${otherId}`, {
        method: 'POST',
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations', data.id] })
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations'] })
    },
  })
}

export function useAddEntitiesV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      kind,
      ids,
    }: {
      id: number
      kind: 'fir' | 'person' | 'account' | 'location' | 'org'
      ids: number[]
    }) =>
      apiFetch<InvestigationV2>(`/v2/investigations/${id}/entities`, {
        method: 'POST',
        body: { kind, ids },
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations', data.id] })
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations'] })
    },
  })
}

export function useRemoveEntitiesV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      kind,
      ids,
    }: {
      id: number
      kind: 'fir' | 'person' | 'account' | 'location' | 'org'
      ids: number[]
    }) =>
      apiFetch<InvestigationV2>(`/v2/investigations/${id}/entities`, {
        method: 'DELETE',
        body: { kind, ids },
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations', data.id] })
      queryClient.invalidateQueries({ queryKey: ['v2', 'investigations'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Conversations V2 Hooks
// ---------------------------------------------------------------------------

export function useConversationsV2(investigationId?: number, includeArchived?: boolean) {
  const query = new URLSearchParams()
  if (investigationId !== undefined) {
    query.set('investigation_id', String(investigationId))
  }
  if (includeArchived) {
    query.set('include_archived', 'true')
  }
  const qs = query.toString()

  return useQuery({
    queryKey: ['v2', 'conversations', investigationId ?? 'all', includeArchived ?? false],
    queryFn: () =>
      apiFetch<ConversationV2[]>(`/v2/conversations${qs ? `?${qs}` : ''}`),
    staleTime: 10 * 1000,
  })
}

export function useConversationV2(id: number | undefined) {
  return useQuery({
    queryKey: ['v2', 'conversations', id],
    queryFn: () => apiFetch<ConversationV2>(`/v2/conversations/${id}`),
    enabled: id !== undefined,
  })
}

export function useCreateConversationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      investigation_id?: number | null
      nickname?: string
      language?: string
    }) =>
      apiFetch<ConversationV2>('/v2/conversations', {
        method: 'POST',
        body,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'conversations'] })
    },
  })
}

export function useUpdateConversationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number
      nickname?: string
      language?: string
      pinned?: boolean
      archive?: boolean
    }) =>
      apiFetch<ConversationV2>(`/v2/conversations/${id}`, {
        method: 'PATCH',
        body,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'conversations', data.id] })
      queryClient.invalidateQueries({ queryKey: ['v2', 'conversations'] })
    },
  })
}

export function useDeleteConversationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ id: number; status: string }>(`/v2/conversations/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'conversations'] })
    },
  })
}

export function useConversationMessagesV2(id: number | undefined) {
  return useQuery({
    queryKey: ['v2', 'conversations', id, 'messages'],
    queryFn: () => apiFetch<MessageV2[]>(`/v2/conversations/${id}/messages`),
    enabled: id !== undefined,
  })
}

export function useSendConversationMessageV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, message }: { id: number; message: string }) =>
      apiFetch<{
        reply: string
        conversation_id: number
        tool_calls: any[]
        citations: any[]
        recent_messages: MessageV2[]
      }>(`/v2/conversations/${id}/messages`, {
        method: 'POST',
        body: { message },
      }),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'conversations', id, 'messages'] })
    },
  })
}

export function useDuplicateConversationV2() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<ConversationV2>(`/v2/conversations/${id}/duplicate`, {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v2', 'conversations'] })
    },
  })
}

export function useExportConversationPdfV2() {
  return useMutation({
    mutationFn: async (id: number) => {
      const accessToken = useAuthStore.getState().accessToken
      const res = await fetch(`${API_BASE_URL}/v2/conversations/${id}/export/pdf`, {
        method: 'POST',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw { status: res.status, detail: detail.detail ?? res.statusText }
      }
      const blob = await res.blob()
      return { url: URL.createObjectURL(blob) }
    },
  })
}

// Streaming handler
export async function streamConversationMessageV2(
  id: number,
  message: string,
  onEvent: (event: { event_type: string; message: string; agent: string; data: any }) => void,
  signal?: AbortSignal
): Promise<void> {
  const accessToken = useAuthStore.getState().accessToken
  const res = await fetch(`${API_BASE_URL}/v2/conversations/${id}/stream`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify({ message }),
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
        onEvent(JSON.parse(jsonText))
      } catch {
        // Skip malformed chunk
      }
    }
  }
}
