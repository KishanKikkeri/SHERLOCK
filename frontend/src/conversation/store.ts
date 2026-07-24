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

interface ConversationState {
  sessionId: number | undefined
  messages: ChatMessage[]
  timeline: TimelineStep[]
  isStreaming: boolean
  language: string
  muted: boolean

  setSessionId: (id: number | undefined) => void
  addMessage: (message: ChatMessage) => void
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void
  applyStreamEvent: (event: ConversationStreamEvent) => void
  clearTimeline: () => void
  setStreaming: (streaming: boolean) => void
  setLanguage: (language: string) => void
  toggleMuted: () => void
  resetConversation: () => void
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  sessionId: undefined,
  messages: [],
  timeline: [],
  isStreaming: false,
  language: 'en',
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
    if (event.event_type === 'agent_completed') {
      set((s) => ({ timeline: [...s.timeline, { agent, status: 'completed', message: event.message ?? '' }] }))
    } else if (event.event_type === 'agent_skipped') {
      set((s) => ({ timeline: [...s.timeline, { agent, status: 'skipped', message: event.message ?? '' }] }))
    } else if (event.event_type === 'agent_failed') {
      set((s) => ({ timeline: [...s.timeline, { agent, status: 'failed', message: event.message ?? '' }] }))
    } else if (event.event_type === 'investigation_started' || event.event_type === 'agent_started') {
      set((s) => ({ timeline: [...s.timeline, { agent, status: 'started', message: event.message ?? '' }] }))
    }
    // report_ready / clarification_needed / topic_reset / error are all
    // handled by the caller (useConversation) directly against `messages`,
    // not folded into the timeline — they're conversational outcomes, not
    // per-agent execution steps.
    void get
  },

  clearTimeline: () => set({ timeline: [] }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  setLanguage: (language) => set({ language }),
  toggleMuted: () => set((s) => ({ muted: !s.muted })),

  resetConversation: () => set({ sessionId: undefined, messages: [], timeline: [], isStreaming: false }),
}))
