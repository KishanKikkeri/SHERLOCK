import { useCallback } from 'react'
import { Mic, Ear } from 'lucide-react'
import { useVoice } from '@/voice/useVoice'
import { parseVoiceCommand, type BoardVoiceCommand } from '@/voice/voice-commands'
import { Button } from '@/components/ui/Button'
import { useLanguage } from '@/providers/LanguageProvider'

/**
 * Floating board-command voice control. Deliberately push-to-talk /
 * wake-word only — no language selector, no server-audio fallback,
 * no conversation history. Full voice UX lives at /voice; this is
 * just the board-UI vocabulary (voice/voice-commands.ts) wired to a
 * board that can already receive these actions. Kept intentionally
 * small — see docs/stage-f/validation/F4-VALIDATION.md. Follows the
 * global UI language for recognition, same as the main Voice page.
 */
export function BoardVoiceControl({ onCommand }: { onCommand: (cmd: BoardVoiceCommand) => void }) {
  const { language, t } = useLanguage()
  const handleTranscript = useCallback(
    (text: string) => {
      onCommand(parseVoiceCommand(text))
    },
    [onCommand],
  )

  const voice = useVoice(handleTranscript, language)

  if (!voice.state.supported) return null

  return (
    <div className="absolute bottom-3 right-3 z-10 flex items-center gap-1.5 rounded-full border border-border bg-surface p-1.5 shadow-lg">
      {voice.state.transcript && (
        <span className="max-w-[200px] truncate px-2 text-xs text-muted">"{voice.state.transcript}"</span>
      )}
      <Button
        variant={voice.state.wakeListening ? 'primary' : 'ghost'}
        size="icon"
        onClick={voice.actions.toggleWakeListening}
        aria-pressed={voice.state.wakeListening}
        title={voice.state.wakeListening ? t('board_voice.stop_listening', 'Stop listening for "Sherlock"') : t('board_voice.listen_for_wake_word', 'Listen for wake word')}
      >
        <Ear className="h-4 w-4" />
      </Button>
      <Button
        variant={voice.state.dictating ? 'primary' : 'ghost'}
        size="icon"
        onPointerDown={voice.actions.startPushToTalk}
        onPointerUp={voice.actions.stopPushToTalk}
        onPointerLeave={() => voice.state.dictating && voice.actions.stopPushToTalk()}
        title={t('board_voice.hold_to_speak', 'Hold to speak a board command')}
        aria-pressed={voice.state.dictating}
      >
        <Mic className="h-4 w-4" />
      </Button>
    </div>
  )
}
