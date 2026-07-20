import type { VoiceIntent } from '@/lib/types'

export type VoicePath = 'browser' | 'server'

export interface VoiceConversationTurn {
  id: string
  query: string
  language: string
  path: VoicePath
  timestamp: string
  intent?: VoiceIntent
  spokenResponse?: string
  data?: Record<string, unknown>
  pending?: boolean
  error?: string
}

export function newTurnId(): string {
  return `turn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}
