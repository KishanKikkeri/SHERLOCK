import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { useVoice } from '@/voice/useVoice'
import { useConversation } from '@/conversation/hooks/useConversation'
import { useLanguage } from '@/providers/LanguageProvider'

type ConversationContextValue = ReturnType<typeof useConversation> & {
  voice: ReturnType<typeof useVoice>
}

const ConversationContext = createContext<ConversationContextValue | null>(null)

/**
 * The CIS proposal's "Conversation is the primary interface, voice is
 * just one way to talk to it" idea, made concrete: this provider creates
 * exactly one `useConversation` (message/session state) and one
 * `useVoice` (wake word / push-to-talk / TTS — same hook VoicePage
 * already used) per Conversation screen, and wires the microphone's
 * recognized text into the same `sendMessage` the text composer calls.
 * Nothing downstream needs to know whether a given turn came from
 * typing or speaking.
 */
export function ConversationProvider({ children }: { children: ReactNode }) {
  const conversation = useConversation()
  const { language } = useLanguage()

  const handleVoiceCommand = useCallback(
    (text: string) => {
      void conversation.sendMessage(text)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [conversation.sendMessage],
  )

  // Priority 32: previously called as `useVoice(handleVoiceCommand)` with
  // no second argument, so it silently defaulted to `'en'` regardless of
  // the active UI language — speech recognition and synthesis stayed in
  // English even in Kannada mode. `useVoice` already tracks this via a
  // ref internally (see its own "Phase 6: voice defaults follow the UI
  // language" comment) — it just never actually received the value.
  const voice = useVoice(handleVoiceCommand, language)

  const value = useMemo(() => ({ ...conversation, voice }), [conversation, voice])

  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>
}

export function useConversationContext() {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversationContext must be used within a ConversationProvider')
  return ctx
}
