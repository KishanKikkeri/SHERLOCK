import { Download, Eraser, FolderSearch, RotateCcw, Volume2, VolumeX } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { LanguageSelector } from '@/voice/LanguageSelector'
import { useSessions } from '@/lib/queries/sessions'
import { useClearConversation, useExportConversationPdf, useSummarizeConversation } from '@/lib/queries/conversation'
import { useConversationContext } from '@/conversation/ConversationProvider'

export function ConversationSidebar() {
  const { sessionId, setSessionId, language, setLanguage, muted, toggleMuted, resetConversation, addMessage } =
    useConversationContext()
  const { data: openSessions } = useSessions({ status: 'open' })
  const summarize = useSummarizeConversation()
  const clear = useClearConversation()
  const exportPdf = useExportConversationPdf()

  async function handleSummarize() {
    if (!sessionId) return
    const result = await summarize.mutateAsync(sessionId)
    addMessage({
      id: `summary_${Date.now()}`,
      role: 'assistant',
      text: result.summary || 'Nothing to summarize yet.',
      createdAt: new Date().toISOString(),
    })
  }

  async function handleClear() {
    if (!sessionId) return
    await clear.mutateAsync(sessionId)
    resetConversation()
  }

  async function handleExport() {
    if (!sessionId) return
    const { url } = await exportPdf.mutateAsync({ sessionId, language })
    window.open(url, '_blank')
  }

  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <CardHeader
        title="Conversation"
        subtitle={sessionId ? `Session #${sessionId}` : 'New conversation'}
      />
      <CardBody className="flex flex-1 flex-col gap-4 overflow-y-auto">
        <div>
          <p className="mb-1.5 text-xs font-medium text-muted">Language</p>
          <LanguageSelector value={language} onChange={setLanguage} />
        </div>

        <div>
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted">
            <FolderSearch className="h-3.5 w-3.5" /> Attach to session
          </p>
          <select
            value={sessionId ?? ''}
            onChange={(e) => setSessionId(e.target.value ? Number(e.target.value) : undefined)}
            className="h-9 w-full rounded-md border border-border bg-surface-raised px-2 text-sm text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            <option value="">New conversation</option>
            {openSessions?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.session_code} — {s.title}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Button variant="secondary" size="sm" onClick={handleSummarize} disabled={!sessionId || summarize.isPending}>
            <RotateCcw className="h-3.5 w-3.5" /> Summarize conversation
          </Button>
          <Button variant="secondary" size="sm" onClick={handleExport} disabled={!sessionId || exportPdf.isPending}>
            <Download className="h-3.5 w-3.5" /> Export as PDF
          </Button>
          <Button variant="ghost" size="sm" onClick={handleClear} disabled={!sessionId || clear.isPending}>
            <Eraser className="h-3.5 w-3.5" /> Clear conversation
          </Button>
          <Button variant="ghost" size="sm" onClick={toggleMuted}>
            {muted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
            {muted ? 'Unmute responses' : 'Mute responses'}
          </Button>
        </div>

        <p className="mt-auto text-[11px] leading-relaxed text-subtle">
          Every answer here is backed by validated evidence from SHERLOCK's investigation
          pipeline — the same Crime Records, Network, Financial, Pattern, and Prevention
          agents behind the Investigations screen, just reachable by asking directly.
        </p>
      </CardBody>
    </Card>
  )
}
