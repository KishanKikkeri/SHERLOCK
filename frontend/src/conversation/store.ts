import { create } from 'zustand'
import type { ConversationCitation, ConversationStreamEvent } from '@/lib/types'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  pending?: boolean
  error?: string
  citations?: ConversationCitation[]
  suggestedQuestions?: string[]
  intent?: string
  createdAt: string
}

export interface TimelineStep {
  agent: string
  status: 'started' | 'completed' | 'skipped' | 'failed'
  message: string
}

// Priority 28: the backend attaches a parallel `data.localized_message`
// (see `_make_localizing_sender` in backend/api/investigation_stream.py)
// whenever the investigation is running in a non-English language,
// alongside the canonical English `message` it never renames or
// removes (Golden Rule 1). Nothing previously read that field — every
// consumer rendered `message`, so the live reasoning panel showed
// English regardless of the active language. This prefers the
// localized text whenever the backend sent one; it's only ever
// present when the language for this investigation was already
// non-English, so no extra language check is needed here.
export function displayMessage(event: ConversationStreamEvent): string {
  const localized = (event.data as { localized_message?: unknown } | null)?.localized_message
  return typeof localized === 'string' && localized ? localized : (event.message ?? '')
}

// Priority 26: language is deliberately NOT part of this store. It used
// to have its own independent `language`/`setLanguage` here, bound to
// ConversationSidebar's language selector — a second, disconnected copy
// of "what language is active" alongside LanguageProvider's app-wide
// one (and a third inside useVoice's STT/TTS locale, which defaulted to
// English because nothing passed it a language at all). All three now
// read from the one global `useLanguage()` context instead — see
// useConversation.ts, ConversationSidebar.tsx, and ConversationProvider.tsx.
interface ConversationState {
  sessionId: number | undefined
  messages: ChatMessage[]
  timeline: TimelineStep[]
  isStreaming: boolean
  showTimeline: boolean   // Stage F3: only show timeline for investigation intents
  muted: boolean

  setSessionId: (id: number | undefined) => void
  addMessage: (message: ChatMessage) => void
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void
  applyStreamEvent: (event: ConversationStreamEvent) => void
  clearTimeline: () => void
  setStreaming: (streaming: boolean) => void
  setShowTimeline: (show: boolean) => void
  toggleMuted: () => void
  resetConversation: () => void
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  sessionId: undefined,
  messages: [],
  timeline: [],
  isStreaming: false,
  showTimeline: false,
  muted: false,

  setSessionId: (id) => set({ sessionId: id }),

  addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),

  updateMessage: (id, patch) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),

  // Folds one /conversation/stream (or /ws/investigate) event into the
  // live agent-execution timeline. Mirrors what the existing
  // investigation activity feed does (see useInvestigation.ts) so the
  // Conversation screen's timeline reads identically to the WS-driven one.
  applyStreamEvent: (event) => {
    const agent = event.agent ?? 'System'
    const message = displayMessage(event)
    if (event.event_type === 'agent_completed') {
      set((s) => ({ timeline: [...s.timeline, { agent, status: 'completed', message }] }))
    } else if (event.event_type === 'agent_skipped') {
      set((s) => ({ timeline: [...s.timeline, { agent, status: 'skipped', message }] }))
    } else if (event.event_type === 'agent_failed') {
      set((s) => ({ timeline: [...s.timeline, { agent, status: 'failed', message }] }))
    } else if (event.event_type === 'investigation_started' || event.event_type === 'agent_started') {
      // An investigation was triggered — show the timeline
      set((s) => ({ showTimeline: true, timeline: [...s.timeline, { agent, status: 'started', message }] }))
    } else if (event.event_type === 'thinking') {
      // "Let me look into that..." — show timeline is coming
      set((s) => ({ showTimeline: true, timeline: [...s.timeline, { agent, status: 'started', message }] }))
    }
    // conversation_reply / report_ready / clarification_needed / topic_reset
    // / error are handled by the caller (useConversation) directly against
    // `messages`, not folded into the timeline.
    void get
  },

  clearTimeline: () => set({ timeline: [], showTimeline: false }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  setShowTimeline: (show) => set({ showTimeline: show }),
  toggleMuted: () => set((s) => ({ muted: !s.muted })),

  resetConversation: () => set({ sessionId: undefined, messages: [], timeline: [], isStreaming: false, showTimeline: false }),
}))
