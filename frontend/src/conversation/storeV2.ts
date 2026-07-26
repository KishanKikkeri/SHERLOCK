import { create } from 'zustand'

export interface TimelineStep {
  agent: string
  status: 'started' | 'completed' | 'skipped' | 'failed'
  message: string
}

interface ConversationV2State {
  activeInvestigationId: number | undefined
  activeConversationId: number | undefined
  isStreaming: boolean
  showTimeline: boolean
  timeline: TimelineStep[]
  muted: boolean

  setInvestigationId: (id: number | undefined) => void
  setConversationId: (id: number | undefined) => void
  setStreaming: (streaming: boolean) => void
  setShowTimeline: (show: boolean) => void
  clearTimeline: () => void
  applyStreamEvent: (event: { event_type: string; message: string; agent: string; data?: any }) => void
  toggleMuted: () => void
  resetConversation: () => void
}

export const useConversationV2Store = create<ConversationV2State>((set) => ({
  activeInvestigationId: undefined,
  activeConversationId: undefined,
  isStreaming: false,
  showTimeline: false,
  timeline: [],
  muted: false,

  setInvestigationId: (id) => set({ activeInvestigationId: id }),
  setConversationId: (id) => set({ activeConversationId: id }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  setShowTimeline: (show) => set({ showTimeline: show }),
  clearTimeline: () => set({ timeline: [], showTimeline: false }),

  applyStreamEvent: (event) => {
    const agent = event.agent ?? 'System'
    const message = event.message ?? ''
    const type = event.event_type

    if (type === 'tool_started' || type === 'investigation_started' || type === 'agent_started') {
      set((s) => ({
        showTimeline: true,
        timeline: [...s.timeline, { agent, status: 'started', message }],
      }))
    } else if (type === 'tool_completed' || type === 'agent_completed') {
      set((s) => ({
        timeline: [...s.timeline, { agent, status: 'completed', message }],
      }))
    } else if (type === 'agent_skipped') {
      set((s) => ({
        timeline: [...s.timeline, { agent, status: 'skipped', message }],
      }))
    } else if (type === 'agent_failed' || type === 'error') {
      set((s) => ({
        timeline: [...s.timeline, { agent, status: 'failed', message }],
      }))
    } else if (type === 'thinking') {
      set((s) => ({
        showTimeline: true,
        timeline: [...s.timeline, { agent, status: 'started', message }],
      }))
    }
  },

  toggleMuted: () => set((s) => ({ muted: !s.muted })),
  resetConversation: () =>
    set({
      activeConversationId: undefined,
      timeline: [],
      isStreaming: false,
      showTimeline: false,
    }),
}))
