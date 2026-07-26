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

      // Optimistically add messages to query cache safely
      const messagesKey = ['v2', 'conversations', conversationId, 'messages']
      queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => {
        const existing = old ? [...old] : []
        if (!existing.some((m) => m.id === userMsg.id)) {
          existing.push(userMsg)
        }
        if (!existing.some((m) => m.id === assistantMsg.id)) {
          existing.push(assistantMsg)
        }
        return existing
      })

      store.clearTimeline()
      store.setStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller

      try {
        let finalReply = ''
        await streamConversationMessageV2(
          conversationId,
          trimmed,
          (event) => {
            store.applyStreamEvent(event)

            if (event.event_type === 'assistant_reply') {
              finalReply = event.message
              queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => {
                const list = old ? [...old] : []
                const pendingIdx = list.findIndex((m) => m.metadata?.pending)
                if (pendingIdx !== -1) {
                  list[pendingIdx] = {
                    ...list[pendingIdx],
                    content: finalReply,
                    metadata: { ...list[pendingIdx].metadata, pending: false },
                  }
                } else {
                  list.push({
                    id: Math.random() + 2,
                    conversation_id: conversationId!,
                    role: 'assistant',
                    content: finalReply,
                    tool_calls: null,
                    tool_name: null,
                    tool_result: null,
                    tool_call_id: null,
                    metadata: {},
                    created_at: new Date().toISOString(),
                  })
                }
                return list
              })
            }
          },
          controller.signal,
          language
        )
      } catch (err) {
        console.error('Streaming error:', err)
        const errMsg = (err as any)?.detail || 'Failed to stream response.'
        queryClient.setQueryData<MessageV2[]>(messagesKey, (old) => {
          const list = old ? [...old] : []
          const pendingIdx = list.findIndex((m) => m.metadata?.pending)
          if (pendingIdx !== -1) {
            list[pendingIdx] = {
              ...list[pendingIdx],
              content: errMsg,
              metadata: { ...list[pendingIdx].metadata, pending: false, error: true },
            }
          } else {
            list.push({
              id: Math.random() + 2,
              conversation_id: conversationId!,
              role: 'assistant',
              content: errMsg,
              tool_calls: null,
              tool_name: null,
              tool_result: null,
              tool_call_id: null,
              metadata: { error: true },
              created_at: new Date().toISOString(),
            })
          }
          return list
        })
      } finally {
        store.setStreaming(false)
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: messagesKey })
          queryClient.invalidateQueries({ queryKey: ['v2', 'conversations'] })
        }, 500)
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
