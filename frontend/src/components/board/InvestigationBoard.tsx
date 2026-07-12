// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Investigation Board (Phase 3: Digital War Room)
// Infinite pannable/zoomable canvas. Evidence cards, sticky notes,
// hypothesis cards, manual links, undo/redo, snapshots, auto-layout,
// presentation mode.
// ─────────────────────────────────────────────────────────────────

import { useCallback, useMemo, useRef, useState } from 'react';
import type { AgentFinding } from '../../lib/types';
import type { BoardCard } from '../../lib/board-types';
import { useBoard } from '../../hooks/useBoard';
import { useVoice } from '../../hooks/useVoice';
import { parseVoiceCommand } from '../../lib/voice-commands';
import { BoardToolbar } from './BoardToolbar';
import { EvidenceCardView } from './EvidenceCard';
import { LinkLayer } from './LinkLayer';
import { VoiceIndicator } from './VoiceIndicator';
import styles from './InvestigationBoard.module.css';

interface Props {
  findings: AgentFinding[];
  onExit: () => void;
}

interface ViewTransform { x: number; y: number; scale: number; }

export function InvestigationBoard({ findings, onExit }: Props) {
  const { data, snapshots, actions, canUndo, canRedo } = useBoard();
  const [view, setView] = useState<ViewTransform>({ x: 0, y: 0, scale: 1 });
  const [linkMode, setLinkMode] = useState(false);
  const [linkFrom, setLinkFrom] = useState<string | null>(null);
  const [selectedLink, setSelectedLink] = useState<string | null>(null);
  const [presenting, setPresenting] = useState(false);
  const [presentIdx, setPresentIdx] = useState(0);

  const canvasRef = useRef<HTMLDivElement>(null);
  const panState = useRef<{ startX: number; startY: number; ox: number; oy: number } | null>(null);

  // One-off reads only (never used to compute a state update) — lets
  // onCardPointerDown stay referentially stable across renders, which in
  // turn lets EvidenceCardView's React.memo actually skip re-rendering
  // untouched cards while one card is being dragged. Matters a lot once
  // the board has hundreds of cards on it.
  const dataRef = useRef(data);
  dataRef.current = data;

  const pinnedCards = useMemo(() => data.cards.filter(c => c.pinned), [data.cards]);

  // ── Canvas panning (background drag) ──────────────────────────
  const onCanvasPointerDown = useCallback((e: React.PointerEvent) => {
    if (e.target !== canvasRef.current) return; // only the empty background
    panState.current = { startX: e.clientX, startY: e.clientY, ox: view.x, oy: view.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    if (linkMode) { setLinkFrom(null); }
    setSelectedLink(null);
  }, [view, linkMode]);

  const onCanvasPointerMove = useCallback((e: React.PointerEvent) => {
    if (!panState.current) return;
    const dx = e.clientX - panState.current.startX;
    const dy = e.clientY - panState.current.startY;
    setView(v => ({ ...v, x: panState.current!.ox + dx, y: panState.current!.oy + dy }));
  }, []);

  const onCanvasPointerUp = useCallback(() => { panState.current = null; }, []);

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = -e.deltaY * 0.0015;
    setView(v => ({ ...v, scale: Math.min(2.5, Math.max(0.3, v.scale + delta)) }));
  }, []);

  // ── Card drag ──────────────────────────────────────────────────
  const dragCard = useRef<{ id: string; startX: number; startY: number; ox: number; oy: number } | null>(null);

  const onCardPointerDown = useCallback((id: string, e: React.PointerEvent) => {
    e.stopPropagation();
    if (linkMode) {
      if (!linkFrom) { setLinkFrom(id); }
      else { actions.addLink(linkFrom, id); setLinkFrom(null); }
      return;
    }
    const card = dataRef.current.cards.find(c => c.id === id);
    if (!card) return;
    dragCard.current = { id, startX: e.clientX, startY: e.clientY, ox: card.x, oy: card.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }, [linkMode, linkFrom, actions]);

  const onCardPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragCard.current) return;
    const dx = (e.clientX - dragCard.current.startX) / view.scale;
    const dy = (e.clientY - dragCard.current.startY) / view.scale;
    actions.moveCard(dragCard.current.id, dragCard.current.ox + dx, dragCard.current.oy + dy, false);
  }, [actions, view.scale]);

  const onCardPointerUp = useCallback((e: React.PointerEvent) => {
    if (!dragCard.current) return;
    const dx = (e.clientX - dragCard.current.startX) / view.scale;
    const dy = (e.clientY - dragCard.current.startY) / view.scale;
    actions.moveCard(dragCard.current.id, dragCard.current.ox + dx, dragCard.current.oy + dy, true);
    dragCard.current = null;
  }, [actions, view.scale]);

  const resetView = useCallback(() => setView({ x: 0, y: 0, scale: 1 }), []);

  // ── Presentation mode ─────────────────────────────────────────
  const startPresentation = useCallback(() => {
    if (!pinnedCards.length) return;
    setPresenting(true);
    setPresentIdx(0);
  }, [pinnedCards.length]);

  const focusOn = useCallback((card: BoardCard) => {
    setView({ x: -card.x * 1.1 + 480, y: -card.y * 1.1 + 260, scale: 1.1 });
  }, []);

  const nextPresent = useCallback(() => {
    const ni = Math.min(presentIdx + 1, pinnedCards.length - 1);
    setPresentIdx(ni);
    focusOn(pinnedCards[ni]);
  }, [presentIdx, pinnedCards, focusOn]);

  const prevPresent = useCallback(() => {
    const pi = Math.max(presentIdx - 1, 0);
    setPresentIdx(pi);
    focusOn(pinnedCards[pi]);
  }, [presentIdx, pinnedCards, focusOn]);

  // ── Voice-controlled board (Phase 4) ────────────────────────────
  const [voiceFeedback, setVoiceFeedback] = useState<string | null>(null);
  // `voice` (below) is constructed FROM handleVoiceCommand, so handleVoiceCommand
  // can't close over voice.actions.speak directly — a ref sidesteps the cycle
  // while still routing through the same wake-pause-aware speak() as the console.
  const speakRef = useRef<(text: string, onEnd?: () => void) => void>(() => {});

  const handleVoiceCommand = useCallback((raw: string) => {
    const cmd = parseVoiceCommand(raw);
    let feedback = '';
    switch (cmd.type) {
      case 'add_sticky':        actions.addStickyNote(); feedback = 'Added a sticky note'; break;
      case 'add_hypothesis':    actions.addCard({ kind: 'hypothesis', confidence: 0.5, x: 260, y: 200 }); feedback = 'Added a hypothesis card'; break;
      case 'toggle_link_mode':  setLinkMode(v => !v); setLinkFrom(null); feedback = 'Link mode toggled'; break;
      case 'undo':              actions.undo(); feedback = 'Undone'; break;
      case 'redo':              actions.redo(); feedback = 'Redone'; break;
      case 'auto_layout':       actions.autoLayout(); feedback = 'Auto-laying out the board'; break;
      case 'reset_view':        resetView(); feedback = 'View reset'; break;
      case 'zoom':              setView(v => ({ ...v, scale: Math.min(2.5, Math.max(0.3, v.scale + (cmd.direction === 'in' ? 0.25 : -0.25))) })); feedback = `Zoomed ${cmd.direction}`; break;
      case 'pan': {
        const step = 160;
        const delta = cmd.direction === 'left' ? { x: step, y: 0 } : cmd.direction === 'right' ? { x: -step, y: 0 } : cmd.direction === 'up' ? { x: 0, y: step } : { x: 0, y: -step };
        setView(v => ({ ...v, x: v.x + delta.x, y: v.y + delta.y }));
        feedback = `Panned ${cmd.direction}`;
        break;
      }
      case 'present':           startPresentation(); feedback = 'Starting presentation'; break;
      case 'exit_presentation': setPresenting(false); resetView(); feedback = 'Exited presentation'; break;
      case 'exit_board':        onExit(); return; // unmounting — nothing left to speak to
      case 'unrecognized':      feedback = `I didn't catch "${cmd.raw}" as a board command`; break;
    }
    setVoiceFeedback(feedback);
    speakRef.current(feedback); // spoken confirmation, not just a silent toast — this is what makes it feel like a conversation
    setTimeout(() => setVoiceFeedback(null), 2600);
  }, [actions, resetView, startPresentation, onExit]);

  const voice = useVoice(handleVoiceCommand);
  speakRef.current = voice.actions.speak;

  return (
    <div className={styles.root}>
      {!presenting && (
        <BoardToolbar
          findings={findings}
          linkMode={linkMode}
          onToggleLinkMode={() => { setLinkMode(v => !v); setLinkFrom(null); }}
          onAddSticky={actions.addStickyNote}
          onAddHypothesis={() => actions.addCard({ kind: 'hypothesis', confidence: 0.5, x: 260, y: 200 })}
          onAddFromFinding={actions.addFromFinding}
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
          onExit={onExit}
        />
      )}

      {presenting && (
        <div className={styles.presentBar}>
          <span className={styles.presentLabel}>
            Presentation · {presentIdx + 1} / {pinnedCards.length}
          </span>
          <div className={styles.presentControls}>
            <button onClick={prevPresent} disabled={presentIdx === 0} aria-label="Previous">‹</button>
            <button onClick={nextPresent} disabled={presentIdx === pinnedCards.length - 1} aria-label="Next">›</button>
            <button onClick={() => { setPresenting(false); resetView(); }} className={styles.presentExit}>Exit presentation</button>
          </div>
        </div>
      )}

      <div
        ref={canvasRef}
        className={styles.canvas}
        onPointerDown={onCanvasPointerDown}
        onPointerMove={(e) => { onCanvasPointerMove(e); onCardPointerMove(e); }}
        onPointerUp={(e) => { onCanvasPointerUp(); onCardPointerUp(e); }}
        onWheel={onWheel}
        style={{ cursor: linkMode ? 'crosshair' : panState.current ? 'grabbing' : 'grab' }}
      >
        <div
          className={styles.layer}
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}
        >
          <div className={styles.dotgrid} aria-hidden />

          <LinkLayer
            cards={data.cards}
            links={data.links}
            selectedLink={selectedLink}
            onSelectLink={setSelectedLink}
            onDeleteLink={actions.deleteLink}
          />

          {data.cards.map((card) => (
            <EvidenceCardView
              key={card.id}
              card={card}
              dimmed={presenting && !card.pinned}
              highlighted={linkMode && linkFrom === card.id}
              onPointerDown={onCardPointerDown}
              onEdit={actions.editCard}
              onDelete={actions.deleteCard}
            />
          ))}

          {data.cards.length === 0 && (
            <div className={styles.emptyHint} style={{ transform: `scale(${1 / view.scale})` }}>
              <p>Empty war room.</p>
              <p className={styles.emptyHintSub}>Add a sticky note or pull evidence from findings to begin.</p>
            </div>
          )}
        </div>
      </div>

      {linkMode && (
        <div className={styles.linkHint}>
          {linkFrom ? 'Click a second card to link it — or click empty canvas to cancel' : 'Link mode: click a card to start a connection'}
        </div>
      )}

      <VoiceIndicator voice={voice} feedback={voiceFeedback} />
    </div>
  );
}
