// Ported from frontend/src/components/board/BoardToolbar.tsx (Golden
// Rule 4), extended with filtering, search, snap-to-grid, and
// grouping controls — none of which existed in the original.
import { useState } from 'react'
import {
  ArrowLeft,
  Undo2,
  Redo2,
  LayoutGrid,
  Maximize,
  Camera,
  Play,
  Search,
  Magnet,
  Group,
  Ungroup,
} from 'lucide-react'
import type { BoardCardKind, BoardSnapshot } from './board-types'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'

const KIND_LABELS: Record<BoardCardKind, string> = {
  evidence: 'Evidence',
  note: 'Notes',
  hypothesis: 'Hypotheses',
  timeline: 'Timeline',
}

interface Props {
  linkMode: boolean
  onToggleLinkMode: () => void
  onAddSticky: () => void
  onAddHypothesis: () => void
  onAddTimelineEvent: () => void
  onAutoLayout: () => void
  onUndo: () => void
  onRedo: () => void
  canUndo: boolean
  canRedo: boolean
  snapshots: BoardSnapshot[]
  onSaveSnapshot: (label: string) => void
  onRestoreSnapshot: (id: string) => void
  onDeleteSnapshot: (id: string) => void
  onResetView: () => void
  onPresent: () => void
  canPresent: boolean
  onExit: () => void
  visibleKinds: Set<BoardCardKind>
  onToggleKind: (kind: BoardCardKind) => void
  search: string
  onSearchChange: (v: string) => void
  matchCount: number
  snapToGrid: boolean
  onToggleSnap: () => void
  selectedCount: number
  onGroup: () => void
  onUngroup: () => void
}

export function BoardToolbar({
  linkMode,
  onToggleLinkMode,
  onAddSticky,
  onAddHypothesis,
  onAddTimelineEvent,
  onAutoLayout,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  snapshots,
  onSaveSnapshot,
  onRestoreSnapshot,
  onDeleteSnapshot,
  onResetView,
  onPresent,
  canPresent,
  onExit,
  visibleKinds,
  onToggleKind,
  search,
  onSearchChange,
  matchCount,
  snapToGrid,
  onToggleSnap,
  selectedCount,
  onGroup,
  onUngroup,
}: Props) {
  const [showSnapshots, setShowSnapshots] = useState(false)

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onExit}>
          <ArrowLeft className="h-3.5 w-3.5" /> Investigation
        </Button>
        <span className="h-5 w-px bg-border" />

        <Button variant="secondary" size="sm" onClick={onAddSticky}>
          + Sticky
        </Button>
        <Button variant="secondary" size="sm" onClick={onAddHypothesis}>
          + Hypothesis
        </Button>
        <Button variant="secondary" size="sm" onClick={onAddTimelineEvent}>
          + Timeline event
        </Button>
        <Button variant={linkMode ? 'primary' : 'secondary'} size="sm" onClick={onToggleLinkMode}>
          {linkMode ? 'Linking…' : 'Link cards'}
        </Button>

        <span className="h-5 w-px bg-border" />

        <Button variant="ghost" size="icon" onClick={onUndo} disabled={!canUndo} title="Undo">
          <Undo2 className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={onRedo} disabled={!canRedo} title="Redo">
          <Redo2 className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onAutoLayout} title="Auto-layout">
          <LayoutGrid className="h-3.5 w-3.5" /> Auto-layout
        </Button>
        <Button variant="ghost" size="icon" onClick={onResetView} title="Reset view">
          <Maximize className="h-4 w-4" />
        </Button>
        <Button
          variant={snapToGrid ? 'primary' : 'ghost'}
          size="icon"
          onClick={onToggleSnap}
          title="Snap to grid"
          aria-pressed={snapToGrid}
        >
          <Magnet className="h-4 w-4" />
        </Button>

        {selectedCount >= 2 && (
          <Button variant="secondary" size="sm" onClick={onGroup}>
            <Group className="h-3.5 w-3.5" /> Group {selectedCount}
          </Button>
        )}
        {selectedCount >= 1 && (
          <Button variant="ghost" size="sm" onClick={onUngroup}>
            <Ungroup className="h-3.5 w-3.5" /> Ungroup
          </Button>
        )}

        <div className="ml-auto flex items-center gap-2">
          <div className="relative w-48">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
            <input
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search cards…"
              className="h-8 w-full rounded-md border border-border bg-surface pl-8 pr-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
            />
          </div>
          {search && <span className="text-xs text-muted">{matchCount} match(es)</span>}

          <div className="relative">
            <Button variant="ghost" size="sm" onClick={() => setShowSnapshots((v) => !v)}>
              <Camera className="h-3.5 w-3.5" /> Snapshots
            </Button>
            {showSnapshots && (
              <div className="absolute right-0 top-full z-10 mt-1 w-56 rounded-md border border-border bg-surface p-1 shadow-lg">
                <button
                  type="button"
                  className="w-full cursor-pointer rounded px-2 py-1.5 text-left text-xs text-text hover:bg-surface-raised"
                  onClick={() => onSaveSnapshot(`Snapshot ${snapshots.length + 1}`)}
                >
                  + Save current board
                </button>
                {snapshots.length === 0 && <p className="px-2 py-1.5 text-xs text-muted">No snapshots saved</p>}
                {snapshots.map((s) => (
                  <div key={s.id} className="flex items-center gap-1">
                    <button
                      type="button"
                      className="flex-1 cursor-pointer rounded px-2 py-1.5 text-left text-xs hover:bg-surface-raised"
                      onClick={() => {
                        onRestoreSnapshot(s.id)
                        setShowSnapshots(false)
                      }}
                    >
                      <span className="block text-text">{s.label}</span>
                      <span className="block text-[10px] text-muted">
                        {new Date(s.timestamp).toLocaleString()}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="cursor-pointer px-1 text-xs text-muted hover:text-critical"
                      onClick={() => onDeleteSnapshot(s.id)}
                      title="Delete snapshot"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Button variant="secondary" size="sm" onClick={onPresent} disabled={!canPresent}>
            <Play className="h-3.5 w-3.5" /> Present
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 border-t border-border pt-2">
        <span className="text-xs text-muted">Show:</span>
        {(Object.keys(KIND_LABELS) as BoardCardKind[]).map((kind) => (
          <button
            key={kind}
            type="button"
            onClick={() => onToggleKind(kind)}
            aria-pressed={visibleKinds.has(kind)}
            className={cn(
              'cursor-pointer rounded-full border px-2 py-0.5 text-xs transition-colors duration-150',
              visibleKinds.has(kind)
                ? 'border-border bg-surface-raised text-text'
                : 'border-border/50 text-muted opacity-50',
            )}
          >
            {KIND_LABELS[kind]}
          </button>
        ))}
      </div>
    </div>
  )
}
