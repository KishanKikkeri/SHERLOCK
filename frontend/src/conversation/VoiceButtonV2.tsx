import { Ear, Mic } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useConversationV2Context } from '@/conversation/ConversationProviderV2'

export function VoiceButtonV2() {
  const { voice } = useConversationV2Context()

  if (!voice.state.supported) return null

  return (
    <div className="flex items-center gap-1.5">
      <Button
        type="button"
        variant={voice.state.wakeListening ? 'primary' : 'ghost'}
        size="icon"
        onClick={voice.actions.toggleWakeListening}
        title={voice.state.wakeListening ? 'Listening for "Sherlock"' : 'Wake word off'}
        aria-pressed={voice.state.wakeListening}
      >
        <Ear className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant={voice.state.dictating ? 'primary' : 'ghost'}
        size="icon"
        onPointerDown={voice.actions.startPushToTalk}
        onPointerUp={voice.actions.stopPushToTalk}
        onPointerLeave={() => voice.state.dictating && voice.actions.stopPushToTalk()}
        title="Hold to talk"
        aria-pressed={voice.state.dictating}
      >
        <Mic className="h-4 w-4" />
      </Button>
    </div>
  )
}
