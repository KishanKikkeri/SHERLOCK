import { useState } from 'react'
import { ClipboardCheck, Check, X as XIcon } from 'lucide-react'
import { useDecideReview, useRequestReview, useReviews } from '@/lib/queries/board'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { useAuth } from '@/auth/AuthProvider'
import { hasPermission } from '@/lib/permissions'
import { formatRelativeTime } from '@/lib/format'
import type { ReviewStatus } from '@/lib/types'

// Reviews are session-scoped ("Draft -> In Review -> Approved/Rejected"
// on the session's work-so-far), not attached to individual board
// cards — POST /sessions/{id}/reviews takes no card/object reference at
// all. See docs/stage-f/02-API-CONTRACTS.md. So this lives once per
// board, not inside CardDetailPanel.
const STATUS_TONE: Record<ReviewStatus, 'neutral' | 'warning' | 'positive' | 'critical'> = {
  draft: 'neutral',
  in_review: 'warning',
  approved: 'positive',
  rejected: 'critical',
}

export function SessionReviewPanel({ sessionId }: { sessionId: number }) {
  const { user } = useAuth()
  const canRequest = hasPermission(user?.roles ?? [], 'participate_case')
  const canDecide = hasPermission(user?.roles ?? [], 'decide_review')
  const { data: reviews, isLoading } = useReviews(sessionId)
  const requestReview = useRequestReview(sessionId)
  const decideReview = useDecideReview(sessionId)
  const [notes, setNotes] = useState('')

  const pending = reviews?.find((r) => r.status === 'in_review')

  return (
    <Card>
      <CardHeader title="Review" />
      <CardBody className="flex flex-col gap-3">
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            {pending ? (
              <div className="rounded-md border border-warning/30 bg-warning/10 p-2.5">
                <div className="flex items-center justify-between">
                  <Badge tone="warning">In review</Badge>
                  <span className="text-[11px] text-muted">{formatRelativeTime(pending.created_at)}</span>
                </div>
                {pending.notes && <p className="mt-1.5 text-xs text-text">{pending.notes}</p>}
                {canDecide && (
                  <div className="mt-2 flex gap-1.5">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => decideReview.mutate({ reviewId: pending.id, approve: true, actor_officer_id: user?.officer_id ?? undefined })}
                      isLoading={decideReview.isPending}
                    >
                      <Check className="h-3.5 w-3.5" /> Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => decideReview.mutate({ reviewId: pending.id, approve: false, actor_officer_id: user?.officer_id ?? undefined })}
                      isLoading={decideReview.isPending}
                    >
                      <XIcon className="h-3.5 w-3.5" /> Reject
                    </Button>
                  </div>
                )}
              </div>
            ) : canRequest ? (
              <div className="flex flex-col gap-1.5">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="What should the reviewer look at?"
                  rows={2}
                  className="resize-none rounded-md border border-border bg-surface px-2 py-1.5 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
                />
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    requestReview.mutate(
                      { notes: notes.trim() || undefined, requested_by_officer_id: user?.officer_id ?? undefined },
                      { onSuccess: () => setNotes('') },
                    )
                  }
                  isLoading={requestReview.isPending}
                >
                  <ClipboardCheck className="h-3.5 w-3.5" /> Request review
                </Button>
              </div>
            ) : (
              <EmptyState
                icon={<ClipboardCheck className="h-6 w-6" />}
                title="No review in progress"
                description="Nothing pending for this session right now."
              />
            )}

            {reviews && reviews.length > 0 && (
              <div className="flex flex-col gap-1 border-t border-border pt-2">
                <p className="text-[11px] font-medium text-muted">History</p>
                {reviews.slice(0, 5).map((r) => (
                  <div key={r.id} className="flex items-center justify-between text-[11px]">
                    <Badge tone={STATUS_TONE[r.status]} className="capitalize">
                      {r.status.replace('_', ' ')}
                    </Badge>
                    <span className="text-muted">{formatRelativeTime(r.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  )
}
