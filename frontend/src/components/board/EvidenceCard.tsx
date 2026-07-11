// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Board card
// One component renders all three kinds: evidence / note / hypothesis.
// Drag via pointer events forwarded from the board; inline edit on
// double-click; colour-coded by entity type (evidence) or free pick
// (note/hypothesis).
// ─────────────────────────────────────────────────────────────────

import { useState } from 'react';
import type { BoardCard } from '../../lib/board-types';
import { STICKY_COLORS } from '../../lib/board-types';
import styles from './EvidenceCard.module.css';

interface Props {
  card: BoardCard;
  dimmed: boolean;
  highlighted: boolean;
  onPointerDown: (e: React.PointerEvent) => void;
  onEdit: (patch: Partial<BoardCard>) => void;
  onDelete: () => void;
  onTogglePin: () => void;
}

export function EvidenceCardView({ card, dimmed, highlighted, onPointerDown, onEdit, onDelete, onTogglePin }: Props) {
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
      onPointerDown={onPointerDown}
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
            onClick={(e) => { e.stopPropagation(); onTogglePin(); }}
            title={card.pinned ? 'Remove from presentation' : 'Pin for presentation'}
            aria-pressed={card.pinned}
          >
            📌
          </button>
          <button className={styles.iconBtn} onClick={(e) => { e.stopPropagation(); onDelete(); }} title="Delete">
            ✕
          </button>
        </div>
      </div>

      {editing ? (
        <div className={styles.editForm} onPointerDown={(e) => e.stopPropagation()}>
          <input
            className={styles.editTitle}
            value={card.title}
            onChange={(e) => onEdit({ title: e.target.value })}
            autoFocus
          />
          <textarea
            className={styles.editBody}
            value={card.body}
            onChange={(e) => onEdit({ body: e.target.value })}
          />
          {card.kind === 'hypothesis' && (
            <input
              type="range" min={0} max={1} step={0.05}
              value={card.confidence ?? 0.5}
              onChange={(e) => onEdit({ confidence: parseFloat(e.target.value) })}
            />
          )}
          {card.kind === 'note' && (
            <div className={styles.swatches}>
              {STICKY_COLORS.map((c) => (
                <button key={c} className={styles.swatch} style={{ background: c }} onClick={() => onEdit({ color: c })} aria-label={`Colour ${c}`} />
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
