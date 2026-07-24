import { useEffect, useRef } from 'react'
import { MessageSquare } from 'lucide-react'
import { Card, EmptyState } from '@/components/ui/Card'
import { AgentExecutionTimeline } from '@/conversation/AgentExecutionTimeline'
import { ChatComposer } from '@/conversation/ChatComposer'
import { ConversationMessage } from '@/conversation/ConversationMessage'
import { ConversationProvider, useConversationContext } from '@/conversation/ConversationProvider'
import { ConversationSidebar } from '@/conversation/ConversationSidebar'
import { SuggestedQuestions } from '@/conversation/SuggestedQuestions'

const STARTER_QUESTIONS = [
  'Show recent burglary cases in Mysuru',
  'Which accounts show suspicious transaction patterns?',
  'Who are the top repeat offenders this year?',
]

function ConversationBody() {
  const { messages, timeline, isStreaming, sendMessage } = useConversationContext()
  const scrollRef = useRef<HTMLDivElement>(null)
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant' && !m.pending)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, timeline])

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr] gap-4">
      <ConversationSidebar />

      <Card className="flex flex-col overflow-hidden">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <EmptyState
              icon={<MessageSquare className="h-6 w-6" />}
              title="Ask SHERLOCK anything"
              description='Type or speak — "Show repeat offenders in Mysuru", "Trace this account", "Summarize this conversation".'
              action={<SuggestedQuestions questions={STARTER_QUESTIONS} onSelect={sendMessage} />}
            />
          ) : (
            <div className="flex flex-col gap-5">
              {messages.map((m) => (
                <ConversationMessage key={m.id} message={m} />
              ))}
              {isStreaming && <AgentExecutionTimeline steps={timeline} />}
            </div>
          )}
        </div>

        {lastAssistant?.suggestedQuestions && lastAssistant.suggestedQuestions.length > 0 && (
          <div className="border-t border-border px-4 py-2.5">
            <SuggestedQuestions
              questions={lastAssistant.suggestedQuestions}
              onSelect={sendMessage}
              disabled={isStreaming}
            />
          </div>
        )}

        <ChatComposer />
      </Card>
    </div>
  )
}

export function ConversationPage() {
  return (
    <ConversationProvider>
      <div className="flex h-[calc(100vh-56px-48px)] flex-col gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">Conversation</h1>
          <p className="text-xs text-muted">
            The primary way to work with SHERLOCK — every screen (Investigations, Network,
            Analytics) is also reachable by just asking.
          </p>
        </div>
        <ConversationBody />
      </div>
    </ConversationProvider>
  )
}
