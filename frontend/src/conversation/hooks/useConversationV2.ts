import { useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useConversationV2Store } from '@/conversation/storeV2'
import {
  useCreateConversationV2,
  streamConversationMessageV2,
} from '@/lib/queries/conversation_v2'
import type { MessageV2 } from '@/lib/queries/conversation_v2'
import { useLanguage } from '@/providers/LanguageProvider'

export function useConversationV2() {
  const store = useConversationV2Store()
  const { language } = useLanguage()
  const queryClient = useQueryClient()
  const createConversation = useCreateConversationV2()
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || store.isStreaming) return

      let conversationId = store.activeConversationId

      // 1. Auto-create conversation if none is active
      if (conversationId === undefined) {
        try {
          const newConv = await createConversation.mutateAsync({
            investigation_id: store.activeInvestigationId || null,
            nickname: trimmed.slice(0, 30) || 'New Conversation',
            language,
          })
          conversationId = newConv.id
          store.setConversationId(conversationId)
        } catch (err) {
          console.error('Failed to auto-create conversation:', err)
          return
        }
      }

      const userMsg: MessageV2 = {
        id: Math.random(), // Temp unique ID
        conversation_id: conversationId,
        role: 'user',
        content: trimmed,
        tool_calls: null,
        tool_name: null,
        tool_result: null,
        tool_call_id: null,
        metadata: {},
        created_at: new Date().toISOString(),
      }

      const assistantMsg: MessageV2 = {
        id: Math.random() + 1,
        conversation_id: conversationId,
        role: 'assistant',
        content: '',
        tool_calls: null,
        tool_name: null,
        tool_result: null,
        tool_call_id: null,
        metadata: { pending: true },
        created_at: new Date().toISOString(),
      }

      // Optimistically add messages to query cache
      const messagesKey = ['v2', 'conversations', conversationId, 'messages']
      queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => [
        ...(old || []),
        userMsg,
        assistantMsg,
      ])

      store.clearTimeline()
      store.setStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller

      try {
        let finalReply = ''
        let streamErrored = false
        await streamConversationMessageV2(
          conversationId,
          trimmed,
          (event) => {
            store.applyStreamEvent(event)

            if (event.event_type === 'assistant_reply') {
              finalReply = event.message
              queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => {
                if (!old) return []
                return old.map((m) =>
                  m.metadata.pending
                    ? {
                        ...m,
                        content: finalReply,
                        metadata: { ...m.metadata, pending: false },
                      }
                    : m
                )
              })
            } else if (event.event_type === 'error') {
              // The backend's SSE generator sends this and then ends the
              // stream normally (HTTP 200) — no exception is thrown here,
              // so without this branch the error message only ever lived
              // in the timeline, which unmounts the instant isStreaming
              // goes false. That made real failures (LLM call erroring,
              // timing out, etc.) look identical to "no reply at all",
              // with the actual reason discarded before anyone could see
              // it. Write it onto the visible message instead, same as
              // the catch block below does for a hard JS/network failure.
              streamErrored = true
              const errMsg = event.message || 'The assistant hit an error before it could reply.'
              queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => {
                if (!old) return []
                return old.map((m) =>
                  m.metadata.pending
                    ? {
                        ...m,
                        content: errMsg,
                        metadata: { ...m.metadata, pending: false, error: true },
                      }
                    : m
                )
              })
            }
          },
          controller.signal
        )
        if (!finalReply && !streamErrored) {
          // Stream ended (200 OK) without ever sending assistant_reply or
          // error — leaving a permanently-empty pending bubble otherwise.
          queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => {
            if (!old) return []
            return old.map((m) =>
              m.metadata.pending
                ? {
                    ...m,
                    content: 'The assistant ended without sending a reply.',
                    metadata: { ...m.metadata, pending: false, error: true },
                  }
                : m
            )
          })
        }
      } catch (err) {
        console.error('Streaming error:', err)
        const errMsg = (err as any)?.detail || 'Failed to stream response.'
        queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => {
          if (!old) return []
          return old.map((m) =>
            m.metadata.pending
              ? {
                  ...m,
                  content: errMsg,
                  metadata: { ...m.metadata, pending: false, error: true },
                }
              : m
          )
        })
      } finally {
        store.setStreaming(false)
        queryClient.invalidateQueries({ queryKey: messagesKey })
        queryClient.invalidateQueries({ queryKey: ['v2', 'conversations'] })
      }
    },
    [
      store.activeConversationId,
      store.activeInvestigationId,
      store.isStreaming,
      language,
      createConversation,
      queryClient,
      store,
    ]
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    store.setStreaming(false)
  }, [store])

  return {
    ...store,
    sendMessage,
    cancel,
  }
}
