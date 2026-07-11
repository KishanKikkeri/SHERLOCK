// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Board link layer
// Renders SVG lines between card centers. Lives inside the same
// pan/zoom-transformed container as the cards so coordinates line up.
// ─────────────────────────────────────────────────────────────────

import type { BoardCard, BoardLink } from '../../lib/board-types';
import styles from './InvestigationBoard.module.css';

interface Props {
  cards: BoardCard[];
  links: BoardLink[];
  selectedLink: string | null;
  onSelectLink: (id: string | null) => void;
  onDeleteLink: (id: string) => void;
}

export function LinkLayer({ cards, links, selectedLink, onSelectLink, onDeleteLink }: Props) {
  const byId = new Map(cards.map(c => [c.id, c]));

  return (
    <svg className={styles.linkSvg} aria-hidden={links.length === 0}>
      {links.map((link) => {
        const from = byId.get(link.from);
        const to = byId.get(link.to);
        if (!from || !to) return null;
        const x1 = from.x + from.w / 2, y1 = from.y + from.h / 2;
        const x2 = to.x + to.w / 2, y2 = to.y + to.h / 2;
        const midX = (x1 + x2) / 2, midY = (y1 + y2) / 2;
        const selected = selectedLink === link.id;

        return (
          <g key={link.id}>
            {/* Wide invisible hit-area for easy selection */}
            <line
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="transparent" strokeWidth={16}
              style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
              onClick={(e) => { e.stopPropagation(); onSelectLink(selected ? null : link.id); }}
            />
            <line
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={link.color ?? (selected ? '#F9FAFB' : '#38BDF8')}
              strokeWidth={selected ? 2.5 : 1.5}
              strokeOpacity={selected ? 0.9 : 0.45}
              style={{ pointerEvents: 'none' }}
            />
            {link.label && (
              <text x={midX} y={midY - 6} textAnchor="middle" fontSize="10" fill="#94A3B8" style={{ pointerEvents: 'none' }}>
                {link.label}
              </text>
            )}
            {selected && (
              <foreignObject x={midX - 40} y={midY - 12} width={80} height={24}>
                <button
                  className={styles.linkDeleteBtn}
                  onClick={(e) => { e.stopPropagation(); onDeleteLink(link.id); onSelectLink(null); }}
                >
                  Remove link
                </button>
              </foreignObject>
            )}
          </g>
        );
      })}
    </svg>
  );
}
