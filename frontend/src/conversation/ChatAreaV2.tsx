import { useState, useRef, useEffect } from 'react'
import { Terminal, ChevronDown, ChevronUp, Bot, User, HelpCircle, FileText } from 'lucide-react'
import { useConversationV2Context } from '@/conversation/ConversationProviderV2'
import { useConversationMessagesV2 } from '@/lib/queries/conversation_v2'
import type { MessageV2 } from '@/lib/queries/conversation_v2'
import { AgentExecutionTimelineV2 } from '@/conversation/AgentExecutionTimelineV2'

export function ChatAreaV2() {
  const { activeConversationId, timeline, isStreaming, sendMessage } = useConversationV2Context()
  const { data: messages, isLoading } = useConversationMessagesV2(activeConversationId)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, timeline])

  if (activeConversationId === undefined) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8 text-center text-muted">
        <Bot className="h-12 w-12 text-primary/40 mb-3" />
        <h3 className="text-base font-semibold text-text">Welcome to SHERLOCK Chat</h3>
        <p className="text-xs max-w-sm mt-1">
          Select or create an Investigation Workspace above, then start a conversation to query data and trace suspects.
        </p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex-1 p-4 flex flex-col gap-3 animate-pulse">
        <div className="h-10 w-2/3 bg-border rounded-md self-start" />
        <div className="h-14 w-1/2 bg-border rounded-md self-end" />
        <div className="h-20 w-3/4 bg-border rounded-md self-start" />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
      {messages?.map((msg) => (
        <MessageBubble key={msg.id} message={msg} onSend={sendMessage} />
      ))}

      {isStreaming && (
        <div className="flex flex-col gap-3">
          <AgentExecutionTimelineV2 steps={timeline} />
          <div className="flex items-center gap-2 text-xs text-muted italic">
            <Bot className="h-4 w-4 animate-spin text-primary" />
            SHERLOCK is analyzing...
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}

function MessageBubble({ message, onSend }: { message: MessageV2; onSend: (text: string) => void }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 max-w-[85%] ${isUser ? 'self-end flex-row-reverse' : 'self-start'}`}>
      <div
        className={`flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full border text-xs font-semibold ${
          isUser
            ? 'bg-primary border-primary text-primary-foreground'
            : 'bg-surface-raised border-border text-text'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4 text-primary" />}
      </div>

      <div className="flex flex-col gap-1.5 min-w-0">
        <div
          className={`rounded-lg px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
            isUser
              ? 'bg-primary text-primary-foreground'
              : message.metadata?.error
              ? 'bg-critical/10 border border-critical/20 text-critical'
              : 'bg-surface border border-border text-text'
          }`}
        >
          {message.content && <p className="whitespace-pre-wrap">{message.content}</p>}

          {/* Render tool invocation call in the assistant bubble */}
          {message.tool_calls && message.tool_calls.map((tc, idx) => (
            <div key={idx} className="mt-2 text-xs border-t border-border/40 pt-2 flex flex-col gap-1">
              <span className="font-mono text-muted flex items-center gap-1">
                <Terminal className="h-3 w-3" /> Tool Call: {tc.name}
              </span>
              <pre className="rounded bg-surface-sunken p-1.5 font-mono text-[10px] overflow-x-auto text-muted">
                {JSON.stringify(tc.arguments, null, 2)}
              </pre>
            </div>
          ))}

          {/* Render tool results if role is tool */}
          {message.role === 'tool' && (
            <div className="border border-border/80 rounded bg-surface-sunken p-2.5 flex flex-col gap-2">
              <span className="font-mono text-xs text-muted flex items-center gap-1.5">
                <Terminal className="h-3.5 w-3.5 text-primary" />
                Tool Output: {message.tool_name}
              </span>
              <ToolResultCollapse data={message.tool_result} />
            </div>
          )}
        </div>

        {/* Citations & Suggested Questions */}
        {!isUser && (
          <div className="flex flex-col gap-1.5 px-1">
            {message.metadata?.citations && message.metadata.citations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                <span className="font-semibold flex items-center gap-1">
                  <FileText className="h-3 w-3" /> Citations:
                </span>
                {message.metadata.citations.map((cite: any, i: number) => (
                  <span key={i} className="underline decoration-dotted cursor-help" title={cite.text}>
                    [{i + 1}] {cite.source}
                  </span>
                ))}
              </div>
            )}

            {message.metadata?.suggested_questions && message.metadata.suggested_questions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-1">
                {message.metadata.suggested_questions.map((q: string, i: number) => (
                  <button
                    key={i}
                    onClick={() => onSend(q)}
                    className="inline-flex items-center gap-1 text-[11px] font-medium rounded-full bg-surface-raised border border-border px-2.5 py-1 text-muted hover:text-primary hover:border-primary transition-all duration-150"
                  >
                    <HelpCircle className="h-3 w-3 text-primary/70" />
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ToolResultCollapse({ data }: { data: any }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex flex-col gap-1.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[11px] font-semibold text-accent hover:text-accent-hover transition-colors self-start"
      >
        {open ? (
          <>
            Hide Response Details <ChevronUp className="h-3 w-3" />
          </>
        ) : (
          <>
            Show Response Details <ChevronDown className="h-3 w-3" />
          </>
        )}
      </button>

      {open && (
        <pre className="rounded bg-surface p-2 font-mono text-[10px] max-h-48 overflow-y-auto border border-border shadow-inner text-muted-foreground whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}
