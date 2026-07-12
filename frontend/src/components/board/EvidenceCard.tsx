// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Board card
// One component renders all three kinds: evidence / note / hypothesis.
// Drag via pointer events forwarded from the board; inline edit on
// double-click; colour-coded by entity type (evidence) or free pick
// (note/hypothesis).
//
// Wrapped in React.memo: `onPointerDown`/`onEdit`/`onDelete` are stable
// callbacks from useBoard (see its stability note), and `card` is only a
// new object reference for whichever single card actually changed — so
// memo lets every OTHER card skip re-rendering while one is being dragged
// or edited. Without this, every card re-renders on every drag frame,
// which is fine for a handful of cards but visibly janky with hundreds.
// ─────────────────────────────────────────────────────────────────

import { memo, useState } from 'react';
import type { BoardCard } from '../../lib/board-types';
import { STICKY_COLORS } from '../../lib/board-types';
import styles from './EvidenceCard.module.css';

interface Props {
  card: BoardCard;
  dimmed: boolean;
  highlighted: boolean;
  onPointerDown: (id: string, e: React.PointerEvent) => void;
  onEdit: (id: string, patch: Partial<BoardCard>) => void;
  onDelete: (id: string) => void;
}

function EvidenceCardViewInner({ card, dimmed, highlighted, onPointerDown, onEdit, onDelete }: Props) {
  const [editing, setEditing] = useState(false);

  const kindClass = card.kind === 'note' ? styles.note : card.kind === 'hypothesis' ? styles.hypothesis : styles.evidence;

  return (
    <div
      className={`${styles.card} ${kindClass} ${dimmed ? styles.dimmed : ''} ${highlighted ? styles.highlighted : ''}`}
      style={{
        left: card.x, top: card.y, width: card.w, height: card.h,
        borderLeftColor: card.kind !== 'note' ? card.color : undefined,
        background: card.kind === 'note' ? card.color : undefined,
      }}
      onPointerDown={(e) => onPointerDown(card.id, e)}
      onDoubleClick={() => setEditing(true)}
    >
      <div className={styles.head}>
        {card.kind === 'evidence' && card.entityType && (
          <span className={styles.typeTag}>{card.entityType}</span>
        )}
        {card.kind === 'hypothesis' && (
          <span className={styles.confBadge}>{Math.round((card.confidence ?? 0) * 100)}%</span>
        )}
        <div className={styles.headActions}>
          <button
            className={`${styles.iconBtn} ${card.pinned ? styles.pinned : ''}`}
            onClick={(e) => { e.stopPropagation(); onEdit(card.id, { pinned: !card.pinned }); }}
            title={card.pinned ? 'Remove from presentation' : 'Pin for presentation'}
            aria-pressed={card.pinned}
          >
            📌
          </button>
          <button className={styles.iconBtn} onClick={(e) => { e.stopPropagation(); onDelete(card.id); }} title="Delete">
            ✕
          </button>
        </div>
      </div>

      {editing ? (
        <div className={styles.editForm} onPointerDown={(e) => e.stopPropagation()}>
          <input
            className={styles.editTitle}
            value={card.title}
            onChange={(e) => onEdit(card.id, { title: e.target.value })}
            autoFocus
          />
          <textarea
            className={styles.editBody}
            value={card.body}
            onChange={(e) => onEdit(card.id, { body: e.target.value })}
          />
          {card.kind === 'hypothesis' && (
            <input
              type="range" min={0} max={1} step={0.05}
              value={card.confidence ?? 0.5}
              onChange={(e) => onEdit(card.id, { confidence: parseFloat(e.target.value) })}
            />
          )}
          {card.kind === 'note' && (
            <div className={styles.swatches}>
              {STICKY_COLORS.map((c) => (
                <button key={c} className={styles.swatch} style={{ background: c }} onClick={() => onEdit(card.id, { color: c })} aria-label={`Colour ${c}`} />
              ))}
            </div>
          )}
          <button className={styles.doneBtn} onClick={() => setEditing(false)}>Done</button>
        </div>
      ) : (
        <>
          <p className={styles.title}>{card.title}</p>
          {card.body && <p className={styles.body}>{card.body}</p>}
        </>
      )}
    </div>
  );
}

export const EvidenceCardView = memo(EvidenceCardViewInner);
