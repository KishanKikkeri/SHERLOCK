import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { useVoice } from '@/voice/useVoice'
import { useConversationV2 } from '@/conversation/hooks/useConversationV2'
import { useLanguage } from '@/providers/LanguageProvider'

type ConversationV2ContextValue = ReturnType<typeof useConversationV2> & {
  voice: ReturnType<typeof useVoice>
}

const ConversationV2Context = createContext<ConversationV2ContextValue | null>(null)

export function ConversationV2Provider({ children }: { children: ReactNode }) {
  const conversation = useConversationV2()
  const { language } = useLanguage()

  const handleVoiceCommand = useCallback(
    (text: string) => {
      void conversation.sendMessage(text)
    },
    [conversation.sendMessage]
  )

  const voice = useVoice(handleVoiceCommand, language)

  const value = useMemo(() => ({ ...conversation, voice }), [conversation, voice])

  return (
    <ConversationV2Context.Provider value={value}>
      {children}
    </ConversationV2Context.Provider>
  )
}

export function useConversationV2Context() {
  const ctx = useContext(ConversationV2Context)
  if (!ctx) throw new Error('useConversationV2Context must be used within a ConversationV2Provider')
  return ctx
}
