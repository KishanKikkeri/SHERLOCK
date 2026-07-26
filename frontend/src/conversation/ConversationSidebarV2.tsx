import { useState } from 'react'
import {
  Plus,
  Pin,
  Archive,
  Trash2,
  Edit2,
  Copy,
  FolderLock,
  Globe,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useConversationV2Store } from '@/conversation/storeV2'
import {
  useConversationsV2,
  useCreateConversationV2,
  useUpdateConversationV2,
  useDeleteConversationV2,
  useDuplicateConversationV2,
} from '@/lib/queries/conversation_v2'
import { useLanguage } from '@/providers/LanguageProvider'

export function ConversationSidebarV2() {
  const store = useConversationV2Store()
  const { language, setLanguage } = useLanguage()

  const { data: conversations } = useConversationsV2(store.activeInvestigationId)
  const createMutation = useCreateConversationV2()
  const updateMutation = useUpdateConversationV2()
  const deleteMutation = useDeleteConversationV2()
  const duplicateMutation = useDuplicateConversationV2()

  const [renameId, setRenameId] = useState<number | null>(null)
  const [renameText, setRenameText] = useState('')

  async function handleNewChat() {
    const res = await createMutation.mutateAsync({
      investigation_id: store.activeInvestigationId || null,
      nickname: 'New Conversation',
      language,
    })
    store.setConversationId(res.id)
  }

  async function handleRename(id: number) {
    if (!renameText.trim()) return
    await updateMutation.mutateAsync({
      id,
      nickname: renameText,
    })
    setRenameId(null)
    setRenameText('')
  }

  async function handlePinToggle(id: number, currentPinned: boolean) {
    await updateMutation.mutateAsync({
      id,
      pinned: !currentPinned,
    })
  }

  async function handleArchiveToggle(id: number, currentArchived: string | null) {
    await updateMutation.mutateAsync({
      id,
      archive: !currentArchived,
    })
  }

  async function handleDelete(id: number) {
    await deleteMutation.mutateAsync(id)
    if (store.activeConversationId === id) {
      store.resetConversation()
    }
  }

  async function handleDuplicate(id: number) {
    const res = await duplicateMutation.mutateAsync(id)
    store.setConversationId(res.id)
  }

  const pinnedList = conversations?.filter((c) => c.pinned) || []
  const unpinnedList = conversations?.filter((c) => !c.pinned) || []

  return (
    <div className="flex h-full flex-col gap-4 border-r border-border bg-surface-raised/40 p-4">
      <div className="flex flex-col gap-2">
        <Button variant="primary" onClick={handleNewChat} className="w-full justify-start gap-2 shadow-sm">
          <Plus className="h-4 w-4" /> New Conversation
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto pr-1">
        {/* Pinned Section */}
        {pinnedList.length > 0 && (
          <div className="mb-4">
            <h3 className="mb-2 px-2 text-[10px] font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
              <Pin className="h-3 w-3" /> Pinned
            </h3>
            <ul className="flex flex-col gap-1">
              {pinnedList.map((c) => (
                <ConversationItem
                  key={c.id}
                  conversation={c}
                  isActive={store.activeConversationId === c.id}
                  onSelect={() => store.setConversationId(c.id)}
                  onRenameClick={() => {
                    setRenameId(c.id)
                    setRenameText(c.nickname)
                  }}
                  onPinToggle={() => handlePinToggle(c.id, c.pinned)}
                  onArchiveToggle={() => handleArchiveToggle(c.id, c.archived_at)}
                  onDelete={() => handleDelete(c.id)}
                  onDuplicate={() => handleDuplicate(c.id)}
                />
              ))}
            </ul>
          </div>
        )}

        {/* Regular Section */}
        <div>
          <h3 className="mb-2 px-2 text-[10px] font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
            <FolderLock className="h-3 w-3" /> Chats
          </h3>
          {conversations?.length === 0 ? (
            <p className="px-2 text-xs text-muted/80 italic">No conversations yet.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {unpinnedList.map((c) => (
                <ConversationItem
                  key={c.id}
                  conversation={c}
                  isActive={store.activeConversationId === c.id}
                  onSelect={() => store.setConversationId(c.id)}
                  onRenameClick={() => {
                    setRenameId(c.id)
                    setRenameText(c.nickname)
                  }}
                  onPinToggle={() => handlePinToggle(c.id, c.pinned)}
                  onArchiveToggle={() => handleArchiveToggle(c.id, c.archived_at)}
                  onDelete={() => handleDelete(c.id)}
                  onDuplicate={() => handleDuplicate(c.id)}
                />
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="border-t border-border pt-3">
        <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-muted">
          <Globe className="h-3.5 w-3.5 text-muted" /> Language
        </p>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value as 'en' | 'kn')}
          className="h-9 w-full rounded-md border border-border bg-surface px-2 text-sm text-text outline-none"
        >
          <option value="en">English (default)</option>
          <option value="kn">Kannada (ಕನ್ನಡ)</option>
          <option value="hi">Hindi (हिन्दी)</option>
        </select>
      </div>

      {/* Rename Dialog */}
      <Modal
        open={renameId !== null}
        onClose={() => setRenameId(null)}
        title="Rename Conversation"
        footer={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setRenameId(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => renameId !== null && handleRename(renameId)}>
              Save
            </Button>
          </div>
        }
      >
        <Input
          label="Conversation Nickname"
          value={renameText}
          onChange={(e) => setRenameText(e.target.value)}
          placeholder="Enter new name..."
        />
      </Modal>
    </div>
  )
}

function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onRenameClick,
  onPinToggle,
  onArchiveToggle,
  onDelete,
  onDuplicate,
}: {
  conversation: any
  isActive: boolean
  onSelect: () => void
  onRenameClick: () => void
  onPinToggle: () => void
  onArchiveToggle: () => void
  onDelete: () => void
  onDuplicate: () => void
}) {
  return (
    <li
      className={`group flex items-center justify-between gap-1.5 rounded-md px-2 py-1.5 transition-colors cursor-pointer text-sm ${
        isActive
          ? 'bg-surface-raised font-medium border border-border/80 shadow-sm'
          : 'hover:bg-surface-raised/40 text-muted hover:text-text'
      }`}
      onClick={onSelect}
    >
      <span className="truncate flex-1 pr-1">{conversation.nickname}</span>
      <div className="hidden group-hover:flex items-center gap-1 shrink-0">
        <button
          onClick={(e) => {
            e.stopPropagation()
            onPinToggle()
          }}
          className="rounded p-0.5 hover:bg-surface hover:text-primary"
          title={conversation.pinned ? 'Unpin' : 'Pin'}
        >
          <Pin className={`h-3 w-3 ${conversation.pinned ? 'fill-current text-primary' : ''}`} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRenameClick()
          }}
          className="rounded p-0.5 hover:bg-surface hover:text-primary"
          title="Rename"
        >
          <Edit2 className="h-3 w-3" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDuplicate()
          }}
          className="rounded p-0.5 hover:bg-surface hover:text-primary"
          title="Duplicate"
        >
          <Copy className="h-3 w-3" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onArchiveToggle()
          }}
          className="rounded p-0.5 hover:bg-surface hover:text-primary"
          title={conversation.archived_at ? 'Unarchive' : 'Archive'}
        >
          <Archive className={`h-3 w-3 ${conversation.archived_at ? 'text-primary' : ''}`} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          className="rounded p-0.5 hover:bg-surface hover:text-critical"
          title="Delete"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
    </li>
  )
}
