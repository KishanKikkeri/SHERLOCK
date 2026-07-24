import { AlertTriangle, Bot, User } from 'lucide-react'
import { cn } from '@/lib/cn'
import { EvidenceCard } from '@/conversation/EvidenceCard'
import type { ChatMessage } from '@/conversation/store'

export function ConversationMessage({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-accent/15 text-accent' : 'bg-surface-raised text-muted',
        )}
        aria-hidden
      >
        {isUser ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
      </div>

      <div className={cn('flex max-w-[75%] flex-col gap-2', isUser && 'items-end')}>
        <div
          className={cn(
            'rounded-lg px-3.5 py-2.5 text-sm leading-relaxed',
            isUser ? 'bg-accent text-accent-foreground' : 'bg-surface-raised text-text',
            message.error && 'border border-critical/40 bg-critical/10 text-critical',
          )}
        >
          {message.pending ? (
            <span className="inline-flex items-center gap-1.5 text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current [animation-delay:300ms]" />
            </span>
          ) : (
            <>
              {message.error && (
                <div className="mb-1 flex items-center gap-1.5 text-xs font-medium">
                  <AlertTriangle className="h-3.5 w-3.5" /> Something went wrong
                </div>
              )}
              <p className="whitespace-pre-wrap">{message.text}</p>
            </>
          )}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="flex w-full flex-col gap-1.5">
            {message.citations.map((c, i) => (
              <EvidenceCard key={i} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
