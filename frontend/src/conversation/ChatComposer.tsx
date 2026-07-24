import { useState, type FormEvent } from 'react'
import { Send, Square } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { VoiceButton } from '@/conversation/VoiceButton'
import { useConversationContext } from '@/conversation/ConversationProvider'

export function ChatComposer() {
  const { sendMessage, cancel, isStreaming } = useConversationContext()
  const [value, setValue] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!value.trim() || isStreaming) return
    void sendMessage(value)
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border bg-surface p-3">
      <VoiceButton />
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder='Ask SHERLOCK — "Show repeat offenders in Mysuru", "Expand his network", "Summarize this conversation"…'
        className="h-10 flex-1 rounded-md border border-border bg-surface-raised px-3 text-sm text-text outline-none placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-ring"
        disabled={isStreaming}
        aria-label="Message SHERLOCK"
      />
      {isStreaming ? (
        <Button type="button" variant="destructive" size="icon" onClick={cancel} title="Stop">
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button type="submit" variant="primary" size="icon" disabled={!value.trim()} title="Send">
          <Send className="h-4 w-4" />
        </Button>
      )}
    </form>
  )
}
