import { Card } from '@/components/ui/Card'
import { ConversationV2Provider } from '@/conversation/ConversationProviderV2'
import { ConversationSidebarV2 } from '@/conversation/ConversationSidebarV2'
import { InvestigationSelector } from '@/conversation/InvestigationSelector'
import { ChatAreaV2 } from '@/conversation/ChatAreaV2'
import { ChatComposerV2 } from '@/conversation/ChatComposerV2'

export function ConversationPageV2() {
  return (
    <ConversationV2Provider>
      <div className="flex h-[calc(100vh-56px-48px)] flex-col gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">Conversation</h1>
          <p className="text-xs text-muted">
            The primary workspace to interact with SHERLOCK. Access specialized tools, inspect evidence, and collaborate in real-time.
          </p>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr] gap-4">
          <ConversationSidebarV2 />

          <div className="flex flex-col gap-3 min-h-0">
            <InvestigationSelector />

            <Card className="flex flex-1 flex-col overflow-hidden">
              <ChatAreaV2 />
              <ChatComposerV2 />
            </Card>
          </div>
        </div>
      </div>
    </ConversationV2Provider>
  )
}
export default ConversationPageV2
