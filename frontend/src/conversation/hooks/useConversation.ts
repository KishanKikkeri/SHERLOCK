import { useCallback, useRef } from 'react'
import { streamConversationMessage } from '@/lib/queries/conversation'
import { useConversationStore, type ChatMessage } from '@/conversation/store'
import type { ConversationStreamEvent } from '@/lib/types'

function newMessageId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

/**
 * The Conversation screen's one interaction point: send a message (typed
 * or transcribed from voice — VoiceButton/ChatComposer both call this
 * same function, so text and voice are two inputs into one conversation,
 * not two separate features). Streams via `/conversation/stream` (SSE)
 * so the AgentExecutionTimeline fills in live, exactly like the
 * WebSocket-driven investigation feed elsewhere in the app.
 */
export function useConversation() {
  const store = useConversationStore()
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || store.isStreaming) return

      const userMessage: ChatMessage = {
        id: newMessageId(),
        role: 'user',
        text: trimmed,
        createdAt: new Date().toISOString(),
      }
      const assistantId = newMessageId()
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        text: '',
        pending: true,
        createdAt: new Date().toISOString(),
      }
      store.addMessage(userMessage)
      store.addMessage(assistantMessage)
      store.clearTimeline()
      store.setStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller

      try {
        await streamConversationMessage(
          { sessionId: store.sessionId, message: trimmed, language: store.language },
          (event: ConversationStreamEvent) => {
            store.applyStreamEvent(event)

            if (event.event_type === 'report_ready') {
              const data = (event.data ?? {}) as Record<string, unknown>
              const conversationResult = data.conversation_result as
                | { reply: string; citations: unknown[]; suggested_questions: string[]; intent: string; session_id: number }
                | undefined
              const finalReport = data.final_report as { narrative?: string } | null | undefined

              if (conversationResult) {
                // Meta-command (summarize/export/clear) — manager.py
                // flattens these into a single report_ready carrying the
                // full ConversationManager result under conversation_result.
                store.setSessionId(conversationResult.session_id)
                store.updateMessage(assistantId, {
                  pending: false,
                  text: conversationResult.reply,
                  intent: conversationResult.intent,
                })
              } else {
                if (typeof data.session_id === 'number') store.setSessionId(data.session_id)
                store.updateMessage(assistantId, {
                  pending: false,
                  text: (finalReport?.narrative as string) || event.message || '',
                  citations: (data.citations as ChatMessage['citations']) ?? undefined,
                  suggestedQuestions: (data.suggested_questions as string[]) ?? undefined,
                })
              }
            } else if (event.event_type === 'clarification_needed') {
              store.updateMessage(assistantId, {
                pending: false,
                text: event.message || 'Could you clarify who/what you mean?',
              })
            } else if (event.event_type === 'error') {
              store.updateMessage(assistantId, {
                pending: false,
                error: event.message || 'Something went wrong.',
                text: event.message || 'Something went wrong.',
              })
            }
          },
          controller.signal,
        )
      } catch (err) {
        const detail = (err as { detail?: string })?.detail ?? 'Connection to SHERLOCK failed.'
        store.updateMessage(assistantId, { pending: false, error: detail, text: detail })
      } finally {
        store.setStreaming(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [store.sessionId, store.language, store.isStreaming],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    store.setStreaming(false)
  }, [store])

  return { ...store, sendMessage, cancel }
}
