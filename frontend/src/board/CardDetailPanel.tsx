import { useState, type FormEvent } from 'react'
import { Users, Send, X } from 'lucide-react'
import type { BoardCard } from './board-types'
import { useAddComment, useComments, useCreateBoardObject } from '@/lib/queries/board'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useAuth } from '@/auth/AuthProvider'
import { hasPermission } from '@/lib/permissions'
import { formatRelativeTime } from '@/lib/format'
import type { BoardObjectType } from '@/lib/types'

const KIND_TO_OBJECT_TYPE: Record<BoardCard['kind'], BoardObjectType> = {
  note: 'note',
  hypothesis: 'hypothesis',
  evidence: 'note', // no dedicated backend object_type for evidence — stored as a note, content says what it is
  timeline: 'note',
}

export function CardDetailPanel({
  sessionId,
  card,
  onClose,
  onShared,
}: {
  sessionId: number
  card: BoardCard
  onClose: () => void
  onShared: (objectId: number) => void
}) {
  const { user } = useAuth()
  const canParticipate = hasPermission(user?.roles ?? [], 'participate_case')
  const createBoardObject = useCreateBoardObject(sessionId)
  const targetRef = card.sharedObjectId !== undefined ? String(card.sharedObjectId) : undefined
  const { data: comments, isLoading: commentsLoading } = useComments(sessionId, 'board_object', targetRef)
  const addComment = useAddComment(sessionId)
  const [commentBody, setCommentBody] = useState('')

  async function handleShare() {
    const obj = await createBoardObject.mutateAsync({
      object_type: KIND_TO_OBJECT_TYPE[card.kind],
      content: `${card.title}\n\n${card.body}`,
      payload: { kind: card.kind, entityType: card.entityType, confidence: card.confidence },
      created_by_officer_id: user?.officer_id ?? undefined,
    })
    onShared(obj.id)
  }

  function handleAddComment(e: FormEvent) {
    e.preventDefault()
    if (!commentBody.trim() || !targetRef) return
    addComment.mutate(
      {
        target_type: 'board_object',
        target_ref: targetRef,
        body: commentBody.trim(),
        author_officer_id: user?.officer_id ?? undefined,
      },
      { onSuccess: () => setCommentBody('') },
    )
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-text">{card.title}</p>
        <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {card.sharedObjectId === undefined ? (
        <div className="flex flex-col gap-2 rounded-md border border-dashed border-border p-3 text-center">
          <p className="text-xs text-muted">
            This card is only visible to you. Share it so collaborators can see and comment on it.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleShare}
            isLoading={createBoardObject.isPending}
            disabled={!canParticipate}
          >
            <Users className="h-3.5 w-3.5" /> Share with team
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Badge tone="info" className="w-fit">
            Shared · board object #{card.sharedObjectId}
          </Badge>

          <div className="flex flex-col gap-2">
            {commentsLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : comments && comments.length > 0 ? (
              <ul className="flex max-h-48 flex-col gap-2 overflow-y-auto">
                {comments.map((c) => (
                  <li key={c.id} className="rounded-md bg-surface-raised p-2 text-xs">
                    <p className="text-text">{c.body}</p>
                    <p className="mt-1 text-[10px] text-muted">
                      Officer #{c.author_officer_id ?? '—'} · {formatRelativeTime(c.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted">No comments yet.</p>
            )}

            {canParticipate && (
              <form onSubmit={handleAddComment} className="flex items-end gap-1.5">
                <textarea
                  value={commentBody}
                  onChange={(e) => setCommentBody(e.target.value)}
                  placeholder="@name, or @supervisor/@lead/@reviewer/@investigator to notify someone"
                  rows={2}
                  className="flex-1 resize-none rounded-md border border-border bg-surface px-2 py-1.5 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
                />
                <Button type="submit" size="icon" variant="secondary" isLoading={addComment.isPending}>
                  <Send className="h-3.5 w-3.5" />
                </Button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
