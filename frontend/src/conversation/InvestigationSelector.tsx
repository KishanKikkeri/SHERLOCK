import { useState } from 'react'
import { FolderSearch, Plus, X, FolderPlus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { useConversationV2Store } from '@/conversation/storeV2'
import {
  useInvestigationsV2,
  useInvestigationV2,
  useCreateInvestigationV2,
  useAddEntitiesV2,
  useRemoveEntitiesV2,
} from '@/lib/queries/conversation_v2'

export function InvestigationSelector() {
  const store = useConversationV2Store()
  const { data: investigations } = useInvestigationsV2('active')
  const { data: activeInv } = useInvestigationV2(store.activeInvestigationId)

  const createMutation = useCreateInvestigationV2()
  const addMutation = useAddEntitiesV2()
  const removeMutation = useRemoveEntitiesV2()

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDesc, setNewDesc] = useState('')

  const [addEntityOpen, setAddEntityOpen] = useState(false)
  const [entityKind, setEntityKind] = useState<'fir' | 'person' | 'account' | 'location' | 'org'>('fir')
  const [entityIdsText, setEntityIdsText] = useState('')

  async function handleCreate() {
    if (!newTitle.trim()) return
    const res = await createMutation.mutateAsync({
      title: newTitle,
      description: newDesc,
    })
    store.setInvestigationId(res.id)
    setIsModalOpen(false)
    setNewTitle('')
    setNewDesc('')
  }

  async function handleAddEntities() {
    if (!store.activeInvestigationId || !entityIdsText.trim()) return
    const ids = entityIdsText
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n))

    if (ids.length > 0) {
      await addMutation.mutateAsync({
        id: store.activeInvestigationId,
        kind: entityKind,
        ids,
      })
    }
    setAddEntityOpen(false)
    setEntityIdsText('')
  }

  async function handleRemoveEntity(
    kind: 'fir' | 'person' | 'account' | 'location' | 'org',
    id: number
  ) {
    if (!store.activeInvestigationId) return
    await removeMutation.mutateAsync({
      id: store.activeInvestigationId,
      kind,
      ids: [id],
    })
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface-raised p-3 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-1 items-center gap-2">
          <FolderSearch className="h-4 w-4 text-primary" />
          <select
            value={store.activeInvestigationId ?? ''}
            onChange={(e) => {
              const val = e.target.value
              store.setInvestigationId(val ? Number(val) : undefined)
              // Reset conversation if switching workspace
              store.resetConversation()
            }}
            className="h-9 flex-1 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            <option value="">No Active Workspace (All Cases)</option>
            {investigations?.map((inv) => (
              <option key={inv.id} value={inv.id}>
                {inv.title}
              </option>
            ))}
          </select>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setIsModalOpen(true)}
          title="Create Workspace"
          className="shrink-0"
        >
          <FolderPlus className="h-4 w-4 mr-1" /> New Workspace
        </Button>
      </div>

      {activeInv && (
        <div className="mt-2 flex flex-col gap-2">
          {activeInv.description && (
            <p className="text-xs text-muted leading-relaxed italic">{activeInv.description}</p>
          )}

          {/* Render selected entities categorized */}
          <div className="flex flex-wrap gap-2 text-xs">
            {activeInv.selected_firs.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 border border-border/80 bg-surface rounded-md p-1.5">
                <span className="font-semibold text-muted mr-1">FIRs:</span>
                {activeInv.selected_firs.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 rounded bg-surface-raised px-1.5 py-0.5 border border-border text-[11px] font-medium"
                  >
                    #{id}
                    <button
                      onClick={() => handleRemoveEntity('fir', id)}
                      className="text-muted hover:text-critical"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {activeInv.selected_persons.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 border border-border/80 bg-surface rounded-md p-1.5">
                <span className="font-semibold text-muted mr-1">Suspects:</span>
                {activeInv.selected_persons.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 rounded bg-surface-raised px-1.5 py-0.5 border border-border text-[11px] font-medium"
                  >
                    Person {id}
                    <button
                      onClick={() => handleRemoveEntity('person', id)}
                      className="text-muted hover:text-critical"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
            </div>
            )}

            {activeInv.selected_accounts.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 border border-border/80 bg-surface rounded-md p-1.5">
                <span className="font-semibold text-muted mr-1">Accounts:</span>
                {activeInv.selected_accounts.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 rounded bg-surface-raised px-1.5 py-0.5 border border-border text-[11px] font-medium"
                  >
                    Acct {id}
                    <button
                      onClick={() => handleRemoveEntity('account', id)}
                      className="text-muted hover:text-critical"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <Button
              variant="secondary"
              className="h-7 text-[11px] px-2"
              onClick={() => setAddEntityOpen(true)}
            >
              <Plus className="h-3 w-3 mr-1" /> Add Entities
            </Button>
          </div>
        </div>
      )}

      {/* Workspace Creation Modal */}
      <Modal
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Investigation Workspace"
        description="Create an isolated workspace workspace for organizing suspects, cases, and phone records."
        footer={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate} disabled={!newTitle.trim()}>
              Create
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <Input
            label="Workspace Title"
            placeholder="e.g. Mysuru Cyber Fraud Ring"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
          />
          <Input
            label="Workspace Notes / Description"
            placeholder="Detailed description of the case scope..."
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
          />
        </div>
      </Modal>

      {/* Add Entity Modal */}
      <Modal
        open={addEntityOpen}
        onClose={() => setAddEntityOpen(false)}
        title="Add Entities to Workspace"
        description="Select the kind of entity and input comma-separated database IDs to scope this workspace."
        footer={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setAddEntityOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleAddEntities} disabled={!entityIdsText.trim()}>
              Add Selected
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-text">Entity Kind</label>
            <select
              value={entityKind}
              onChange={(e) => setEntityKind(e.target.value as any)}
              className="h-10 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none"
            >
              <option value="fir">FIR (Case Record)</option>
              <option value="person">Person / Suspect</option>
              <option value="account">Bank Account</option>
              <option value="location">Location</option>
              <option value="org">Organization</option>
            </select>
          </div>
          <Input
            label="Entity IDs (comma-separated)"
            placeholder="e.g. 101, 104, 112"
            value={entityIdsText}
            onChange={(e) => setEntityIdsText(e.target.value)}
          />
        </div>
      </Modal>
    </div>
  )
}
