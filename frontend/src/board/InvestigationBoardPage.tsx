// Canvas pan/zoom/drag/presentation-mode logic ported from
// frontend/src/components/board/InvestigationBoard.tsx (Golden Rule 4).
// Voice control intentionally not ported — useVoice doesn't exist in
// frontend-v2 yet (ships in F4); see docs/stage-f/validation/F3-VALIDATION.md.
import { useCallback, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useBoard } from './useBoard'
import { BoardToolbar } from './BoardToolbar'
import { BoardCardView } from './BoardCard'
import { LinkLayer } from './LinkLayer'
import { AiSuggestionsPanel } from './AiSuggestionsPanel'
import { CardDetailPanel } from './CardDetailPanel'
import { SessionReviewPanel } from './SessionReviewPanel'
import { BoardVoiceControl } from './BoardVoiceControl'
import type { BoardVoiceCommand } from '@/voice/voice-commands'
import type { BoardCard, BoardCardKind } from './board-types'
import { useBoardIntelligence, useDecisionTimeline } from '@/lib/queries/board'
import { useSession } from '@/lib/queries/sessions'
import { Skeleton } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'

const ALL_KINDS: BoardCardKind[] = ['evidence', 'note', 'hypothesis', 'timeline']
const GRID = 20

interface ViewTransform {
  x: number
  y: number
  scale: number
}

export function InvestigationBoardPage() {
  const { id } = useParams<{ id: string }>()
  const sessionId = id ? Number(id) : undefined
  const navigate = useNavigate()

  const { data: session } = useSession(sessionId)
  const { data: intelligence, isLoading: intelligenceLoading } = useBoardIntelligence(sessionId)
  const { data: decisions } = useDecisionTimeline(sessionId)

  const { data, snapshots, actions, canUndo, canRedo } = useBoard()
  const [view, setView] = useState<ViewTransform>({ x: 0, y: 0, scale: 1 })
  const [linkMode, setLinkMode] = useState(false)
  const [linkFrom, setLinkFrom] = useState<string | null>(null)
  const [selectedLink, setSelectedLink] = useState<string | null>(null)
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null)
  const [multiSelected, setMultiSelected] = useState<Set<string>>(new Set())
  const [presenting, setPresenting] = useState(false)
  const [presentIdx, setPresentIdx] = useState(0)
  const [visibleKinds, setVisibleKinds] = useState<Set<BoardCardKind>>(new Set(ALL_KINDS))
  const [search, setSearch] = useState('')
  const [snapToGrid, setSnapToGrid] = useState(false)

  const canvasRef = useRef<HTMLDivElement>(null)
  const panState = useRef<{ startX: number; startY: number; ox: number; oy: number } | null>(null)

  const dataRef = useRef(data)
  dataRef.current = data

  const pinnedCards = useMemo(() => data.cards.filter((c) => c.pinned), [data.cards])
  const selectedCard = data.cards.find((c) => c.id === selectedCardId) ?? null

  const matchIds = useMemo(() => {
    if (!search.trim()) return null
    const q = search.trim().toLowerCase()
    return new Set(data.cards.filter((c) => c.title.toLowerCase().includes(q) || c.body.toLowerCase().includes(q)).map((c) => c.id))
  }, [search, data.cards])

  const isDimmed = useCallback(
    (card: BoardCard) => {
      if (presenting) return !card.pinned
      if (!visibleKinds.has(card.kind)) return true
      if (matchIds && !matchIds.has(card.id)) return true
      return false
    },
    [presenting, visibleKinds, matchIds],
  )

  // ── Canvas panning (background drag) ──────────────────────────
  const onCanvasPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.target !== canvasRef.current) return
      panState.current = { startX: e.clientX, startY: e.clientY, ox: view.x, oy: view.y }
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
      if (linkMode) setLinkFrom(null)
      setSelectedLink(null)
    },
    [view, linkMode],
  )

  const onCanvasPointerMove = useCallback((e: React.PointerEvent) => {
    if (!panState.current) return
    const dx = e.clientX - panState.current.startX
    const dy = e.clientY - panState.current.startY
    setView((v) => ({ ...v, x: panState.current!.ox + dx, y: panState.current!.oy + dy }))
  }, [])

  const onCanvasPointerUp = useCallback(() => {
    panState.current = null
  }, [])

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = -e.deltaY * 0.0015
    setView((v) => ({ ...v, scale: Math.min(2.5, Math.max(0.3, v.scale + delta)) }))
  }, [])

  // ── Card drag (solo: absolute position; grouped: incremental delta) ──
  const dragCard = useRef<{
    id: string
    groupId?: string
    startX: number
    startY: number
    ox: number
    oy: number
    lastClientX: number
    lastClientY: number
  } | null>(null)

  const onCardPointerDown = useCallback(
    (id: string, e: React.PointerEvent) => {
      e.stopPropagation()
      if (linkMode) {
        if (!linkFrom) setLinkFrom(id)
        else {
          actions.addLink(linkFrom, id)
          setLinkFrom(null)
        }
        return
      }
      if (!e.shiftKey) setSelectedCardId(id)
      const card = dataRef.current.cards.find((c) => c.id === id)
      if (!card) return
      dragCard.current = {
        id,
        groupId: card.groupId,
        startX: e.clientX,
        startY: e.clientY,
        ox: card.x,
        oy: card.y,
        lastClientX: e.clientX,
        lastClientY: e.clientY,
      }
      ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    },
    [linkMode, linkFrom, actions],
  )

  const onCardPointerMove = useCallback(
    (e: React.PointerEvent) => {
      const d = dragCard.current
      if (!d) return
      if (d.groupId) {
        const dx = (e.clientX - d.lastClientX) / view.scale
        const dy = (e.clientY - d.lastClientY) / view.scale
        actions.moveGroup(d.groupId, dx, dy, false)
        d.lastClientX = e.clientX
        d.lastClientY = e.clientY
      } else {
        const dx = (e.clientX - d.startX) / view.scale
        const dy = (e.clientY - d.startY) / view.scale
        actions.moveCard(d.id, d.ox + dx, d.oy + dy, false)
      }
    },
    [actions, view.scale],
  )

  const onCardPointerUp = useCallback(
    (e: React.PointerEvent) => {
      const d = dragCard.current
      if (!d) return
      if (d.groupId) {
        const dx = (e.clientX - d.lastClientX) / view.scale
        const dy = (e.clientY - d.lastClientY) / view.scale
        actions.moveGroup(d.groupId, dx, dy, true)
      } else {
        const dx = (e.clientX - d.startX) / view.scale
        const dy = (e.clientY - d.startY) / view.scale
        let x = d.ox + dx
        let y = d.oy + dy
        if (snapToGrid) {
          x = Math.round(x / GRID) * GRID
          y = Math.round(y / GRID) * GRID
        }
        actions.moveCard(d.id, x, y, true)
      }
      dragCard.current = null
    },
    [actions, view.scale, snapToGrid],
  )

  const resetView = useCallback(() => setView({ x: 0, y: 0, scale: 1 }), [])

  const handleVoiceCommand = useCallback(
    (cmd: BoardVoiceCommand) => {
      switch (cmd.type) {
        case 'add_sticky':
          actions.addStickyNote()
          break
        case 'add_hypothesis':
          actions.addCard({ kind: 'hypothesis', confidence: 0.5, x: 260, y: 200 })
          break
        case 'toggle_link_mode':
          setLinkMode((v) => !v)
          setLinkFrom(null)
          break
        case 'undo':
          actions.undo()
          break
        case 'redo':
          actions.redo()
          break
        case 'auto_layout':
          actions.autoLayout()
          break
        case 'reset_view':
          resetView()
          break
        case 'zoom':
          setView((v) => ({ ...v, scale: Math.min(2.5, Math.max(0.3, v.scale + (cmd.direction === 'in' ? 0.2 : -0.2))) }))
          break
        case 'pan': {
          const delta = 120
          setView((v) => ({
            ...v,
            x: v.x + (cmd.direction === 'left' ? delta : cmd.direction === 'right' ? -delta : 0),
            y: v.y + (cmd.direction === 'up' ? delta : cmd.direction === 'down' ? -delta : 0),
          }))
          break
        }
        case 'present':
          startPresentation()
          break
        case 'exit_presentation':
          setPresenting(false)
          resetView()
          break
        case 'exit_board':
          navigate(`/investigations/${sessionId}`)
          break
        case 'unrecognized':
          break
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [actions, resetView, navigate, sessionId],
  )

  const focusOn = useCallback((card: BoardCard) => {
    setView({ x: -card.x * 1.1 + 480, y: -card.y * 1.1 + 260, scale: 1.1 })
  }, [])

  const startPresentation = useCallback(() => {
    if (!pinnedCards.length) return
    setPresenting(true)
    setPresentIdx(0)
    focusOn(pinnedCards[0])
  }, [pinnedCards, focusOn])

  const nextPresent = useCallback(() => {
    const ni = Math.min(presentIdx + 1, pinnedCards.length - 1)
    setPresentIdx(ni)
    focusOn(pinnedCards[ni])
  }, [presentIdx, pinnedCards, focusOn])

  const prevPresent = useCallback(() => {
    const pi = Math.max(presentIdx - 1, 0)
    setPresentIdx(pi)
    focusOn(pinnedCards[pi])
  }, [presentIdx, pinnedCards, focusOn])

  function toggleKind(kind: BoardCardKind) {
    setVisibleKinds((prev) => {
      const next = new Set(prev)
      if (next.has(kind)) next.delete(kind)
      else next.add(kind)
      return next
    })
  }

  function toggleSelect(id: string) {
    setMultiSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (!sessionId) return null

  return (
    <div className="flex h-[calc(100vh-56px-48px)] flex-col gap-3">
      {!presenting && (
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-text">Investigation board</h1>
            <p className="text-xs text-muted">{session?.title ?? `Session #${sessionId}`}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate(`/investigations/${sessionId}`)}>
            <ArrowLeft className="h-3.5 w-3.5" /> Back to session
          </Button>
        </div>
      )}

      {!presenting && (
        <BoardToolbar
          linkMode={linkMode}
          onToggleLinkMode={() => {
            setLinkMode((v) => !v)
            setLinkFrom(null)
          }}
          onAddSticky={actions.addStickyNote}
          onAddHypothesis={() => actions.addCard({ kind: 'hypothesis', confidence: 0.5, x: 260, y: 200 })}
          onAddTimelineEvent={() =>
            actions.addCard({ kind: 'timeline', timestamp: new Date().toISOString(), x: 260, y: 200 })
          }
          onAutoLayout={actions.autoLayout}
          onUndo={actions.undo}
          onRedo={actions.redo}
          canUndo={canUndo}
          canRedo={canRedo}
          snapshots={snapshots}
          onSaveSnapshot={actions.saveSnapshot}
          onRestoreSnapshot={actions.restoreSnapshot}
          onDeleteSnapshot={actions.deleteSnapshot}
          onResetView={resetView}
          onPresent={startPresentation}
          canPresent={pinnedCards.length > 0}
          onExit={() => navigate(`/investigations/${sessionId}`)}
          visibleKinds={visibleKinds}
          onToggleKind={toggleKind}
          search={search}
          onSearchChange={setSearch}
          matchCount={matchIds?.size ?? 0}
          snapToGrid={snapToGrid}
          onToggleSnap={() => setSnapToGrid((v) => !v)}
          selectedCount={multiSelected.size}
          onGroup={() => {
            actions.groupCards(Array.from(multiSelected))
            setMultiSelected(new Set())
          }}
          onUngroup={() => {
            actions.ungroupCards(Array.from(multiSelected))
            setMultiSelected(new Set())
          }}
        />
      )}

      {presenting && (
        <div className="flex items-center justify-between rounded-lg border border-border bg-surface p-2.5">
          <span className="font-mono text-xs text-muted">
            Presentation · {presentIdx + 1} / {pinnedCards.length}
          </span>
          <div className="flex items-center gap-1.5">
            <Button variant="ghost" size="sm" onClick={prevPresent} disabled={presentIdx === 0}>
              ‹ Prev
            </Button>
            <Button variant="ghost" size="sm" onClick={nextPresent} disabled={presentIdx === pinnedCards.length - 1}>
              Next ›
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setPresenting(false)
                resetView()
              }}
            >
              Exit presentation
            </Button>
          </div>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-[1fr_300px] gap-3">
        <div
          ref={canvasRef}
          className="relative overflow-hidden rounded-lg border border-border bg-surface"
          onPointerDown={onCanvasPointerDown}
          onPointerMove={(e) => {
            onCanvasPointerMove(e)
            onCardPointerMove(e)
          }}
          onPointerUp={(e) => {
            onCanvasPointerUp()
            onCardPointerUp(e)
          }}
          onWheel={onWheel}
          style={{ cursor: linkMode ? 'crosshair' : panState.current ? 'grabbing' : 'grab' }}
        >
          <div
            className="absolute left-0 top-0"
            style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, transformOrigin: '0 0' }}
          >
            <LinkLayer
              cards={data.cards}
              links={data.links}
              selectedLink={selectedLink}
              onSelectLink={setSelectedLink}
              onDeleteLink={actions.deleteLink}
            />

            {data.cards.map((card) => (
              <BoardCardView
                key={card.id}
                card={card}
                dimmed={isDimmed(card)}
                highlighted={linkMode && linkFrom === card.id}
                selected={multiSelected.has(card.id) || selectedCardId === card.id}
                onPointerDown={onCardPointerDown}
                onEdit={actions.editCard}
                onDelete={(cid) => {
                  actions.deleteCard(cid)
                  if (selectedCardId === cid) setSelectedCardId(null)
                }}
                onToggleSelect={(cid) => toggleSelect(cid)}
              />
            ))}
          </div>

          {data.cards.length === 0 && (
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 text-center">
              <p className="text-sm text-text">Empty board.</p>
              <p className="text-xs text-muted">Add a sticky note, or pull a suggestion in from the right.</p>
            </div>
          )}

          {linkMode && (
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-text shadow-lg">
              {linkFrom ? 'Click a second card to link it — or click empty canvas to cancel' : 'Link mode: click a card to start a connection'}
            </div>
          )}

          {!presenting && <BoardVoiceControl onCommand={handleVoiceCommand} />}
        </div>

        <div className="flex flex-col gap-3 overflow-y-auto">
          {intelligenceLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <AiSuggestionsPanel
              intelligence={intelligence}
              decisions={decisions}
              isLoading={intelligenceLoading}
              onAddCard={actions.addCard}
            />
          )}
          <SessionReviewPanel sessionId={sessionId} />
          {selectedCard && (
            <CardDetailPanel
              sessionId={sessionId}
              card={selectedCard}
              onClose={() => setSelectedCardId(null)}
              onShared={(objectId) => actions.setSharedObjectId(selectedCard.id, objectId)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
