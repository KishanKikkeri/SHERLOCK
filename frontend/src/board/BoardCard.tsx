// Ported from frontend/src/components/board/EvidenceCard.tsx (Golden
// Rule 4). One component renders all four kinds. Wrapped in React.memo
// for the same reason as the original: onPointerDown/onEdit/onDelete
// are stable callbacks from useBoard, so untouched cards skip
// re-rendering while one is being dragged — matters once a board has
// hundreds of cards.
import { memo, useState } from 'react'
import { Pin, X, Users, MessageSquare } from 'lucide-react'
import type { BoardCard } from './board-types'
import { STICKY_COLORS } from './board-types'
import { ENTITY_META, entityLabel } from '@/graph/entity-meta'
import { cn } from '@/lib/cn'
import { confidenceTone } from '@/lib/status-tone'
import { Badge } from '@/components/ui/Badge'
import { useLanguage } from '@/providers/LanguageProvider'

interface Props {
  card: BoardCard
  dimmed: boolean
  highlighted: boolean
  selected: boolean
  commentCount?: number
  onPointerDown: (id: string, e: React.PointerEvent) => void
  onEdit: (id: string, patch: Partial<BoardCard>) => void
  onDelete: (id: string) => void
  onToggleSelect: (id: string, e: React.MouseEvent) => void
  onSelect: (id: string) => void
}

function BoardCardViewInner({
  card,
  dimmed,
  highlighted,
  selected,
  commentCount,
  onPointerDown,
  onEdit,
  onDelete,
  onToggleSelect,
  onSelect,
}: Props) {
  const [editing, setEditing] = useState(false)
  const { t } = useLanguage()
  const entityMeta = card.entityType ? ENTITY_META[card.entityType] : null
  const kindLabel = t(`board_toolbar.kind_${card.kind}`, card.kind)

  const borderColor = card.kind === 'note' ? undefined : entityMeta ? `var(--${entityMeta.colorVar})` : card.color

  return (
    <div
      className={cn(
        'absolute flex select-none flex-col gap-1 overflow-hidden rounded-md border p-2.5 shadow-sm transition-shadow duration-150',
        card.kind === 'note' ? 'border-transparent text-slate-900' : 'border-l-4 border-y border-r border-border bg-surface text-text',
        dimmed && 'opacity-25',
        highlighted && 'ring-2 ring-accent',
        selected && 'ring-2 ring-ring',
        card.groupColor && 'outline outline-dashed outline-1',
        'outline-none focus-visible:ring-2 focus-visible:ring-ring',
      )}
      style={{
        left: card.x,
        top: card.y,
        width: card.w,
        height: card.h,
        borderLeftColor: card.kind !== 'note' ? borderColor : undefined,
        background: card.kind === 'note' ? card.color : undefined,
        outlineColor: card.groupColor,
        cursor: 'grab',
      }}
      // can't be a native <button>: this card nests an <input>/<textarea>
      // and other <button>s in edit mode, and HTML forbids interactive
      // content inside a real <button>. role="button" on a div is the
      // only valid option here, not a shortcut.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="button"
      tabIndex={0}
      aria-label={`${kindLabel} card: ${card.title}`}
      onPointerDown={(e) => onPointerDown(card.id, e)}
      onClick={(e) => {
        if (e.shiftKey) onToggleSelect(card.id, e)
      }}
      onDoubleClick={() => setEditing(true)}
      onKeyDown={(e) => {
        // Keyboard parity with the primary (non-shift) click action —
        // dragging a card is inherently pointer-based and out of scope
        // for keyboard, same tradeoff as the graph's nodes, but every
        // card should at least be reachable and selectable without a mouse.
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(card.id)
        } else if (e.key === 'Delete' || e.key === 'Backspace') {
          e.preventDefault()
          onDelete(card.id)
        }
      }}
    >
      <div className="flex items-center gap-1">
        {card.kind === 'evidence' && card.entityType && (
          <Badge tone="neutral" className="text-[10px]">
            {entityLabel(card.entityType, t)}
          </Badge>
        )}
        {card.kind === 'hypothesis' && card.confidence !== undefined && (
          <Badge tone={confidenceTone(card.confidence).tone} className="text-[10px]">
            {Math.round(card.confidence * 100)}%
          </Badge>
        )}
        {card.kind === 'timeline' && card.timestamp && (
          <span className="font-mono text-[10px] text-muted">
            {new Date(card.timestamp).toLocaleDateString()}
          </span>
        )}
        {card.sharedObjectId !== undefined && (
          <span title={t('board_card.shared_with_team', 'Shared with team')} className="text-muted">
            <Users className="h-3 w-3" />
          </span>
        )}
        {!!commentCount && (
          <span className="flex items-center gap-0.5 text-[10px] text-muted" title={`${commentCount} ${t('board_card.comments', 'comment(s)')}`}>
            <MessageSquare className="h-3 w-3" />
            {commentCount}
          </span>
        )}
        <div className="ml-auto flex items-center gap-0.5">
          <button
            type="button"
            className={cn('cursor-pointer rounded p-0.5 hover:bg-black/10', card.pinned && 'text-accent')}
            onClick={(e) => {
              e.stopPropagation()
              onEdit(card.id, { pinned: !card.pinned })
            }}
            title={card.pinned ? t('board_card.remove_from_presentation', 'Remove from presentation') : t('board_card.pin_for_presentation', 'Pin for presentation')}
            aria-pressed={card.pinned}
          >
            <Pin className="h-3 w-3" />
          </button>
          <button
            type="button"
            className="cursor-pointer rounded p-0.5 hover:bg-black/10"
            onClick={(e) => {
              e.stopPropagation()
              onDelete(card.id)
            }}
            title={t('board_card.delete', 'Delete')}
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </div>

      {editing ? (
        <div className="flex flex-1 flex-col gap-1.5" onPointerDown={(e) => e.stopPropagation()}>
          <input
            className="rounded border border-border bg-surface/80 px-1.5 py-1 text-xs font-medium text-inherit outline-none"
            value={card.title}
            onChange={(e) => onEdit(card.id, { title: e.target.value })}
            autoFocus
          />
          <textarea
            className="flex-1 resize-none rounded border border-border bg-surface/80 px-1.5 py-1 text-xs text-inherit outline-none"
            value={card.body}
            onChange={(e) => onEdit(card.id, { body: e.target.value })}
          />
          {card.kind === 'hypothesis' && (
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={card.confidence ?? 0.5}
              onChange={(e) => onEdit(card.id, { confidence: parseFloat(e.target.value) })}
            />
          )}
          {card.kind === 'note' && (
            <div className="flex gap-1">
              {STICKY_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className="h-4 w-4 cursor-pointer rounded-full border border-black/10"
                  style={{ background: c }}
                  onClick={() => onEdit(card.id, { color: c })}
                  aria-label={`${t('board_card.colour', 'Colour')} ${c}`}
                />
              ))}
            </div>
          )}
          <button
            type="button"
            className="cursor-pointer self-end rounded bg-black/10 px-2 py-0.5 text-[10px] font-medium"
            onClick={() => setEditing(false)}
          >
            {t('board_card.done', 'Done')}
          </button>
        </div>
      ) : (
        <>
          <p className="truncate text-xs font-semibold">{card.title}</p>
          {card.body && <p className="line-clamp-3 text-[11px] opacity-90">{card.body}</p>}
        </>
      )}
    </div>
  )
}

export const BoardCardView = memo(BoardCardViewInner)
