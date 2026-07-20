// Ported from frontend/src/components/board/LinkLayer.tsx (Golden Rule 4).
import type { BoardCard, BoardLink } from './board-types'

interface Props {
  cards: BoardCard[]
  links: BoardLink[]
  selectedLink: string | null
  onSelectLink: (id: string | null) => void
  onDeleteLink: (id: string) => void
}

export function LinkLayer({ cards, links, selectedLink, onSelectLink, onDeleteLink }: Props) {
  const byId = new Map(cards.map((c) => [c.id, c]))

  return (
    <svg
      className="pointer-events-none absolute left-0 top-0 h-[6000px] w-[6000px] overflow-visible"
      aria-hidden={links.length === 0}
    >
      {links.map((link) => {
        const from = byId.get(link.from)
        const to = byId.get(link.to)
        if (!from || !to) return null
        const x1 = from.x + from.w / 2
        const y1 = from.y + from.h / 2
        const x2 = to.x + to.w / 2
        const y2 = to.y + to.h / 2
        const midX = (x1 + x2) / 2
        const midY = (y1 + y2) / 2
        const selected = selectedLink === link.id

        return (
          <g key={link.id} className="pointer-events-auto">
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="transparent"
              strokeWidth={16}
              style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
              onClick={(e) => {
                e.stopPropagation()
                onSelectLink(selected ? null : link.id)
              }}
            />
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={link.color ?? 'var(--accent)'}
              strokeWidth={selected ? 2.5 : 1.5}
              strokeOpacity={selected ? 0.9 : 0.45}
              style={{ pointerEvents: 'none' }}
            />
            {link.label && (
              <text
                x={midX}
                y={midY - 6}
                textAnchor="middle"
                fontSize="10"
                fill="var(--text-muted)"
                style={{ pointerEvents: 'none' }}
              >
                {link.label}
              </text>
            )}
            {selected && (
              <foreignObject x={midX - 45} y={midY - 12} width={90} height={24}>
                <button
                  type="button"
                  className="cursor-pointer rounded border border-critical/40 bg-surface px-1.5 py-0.5 text-[10px] text-critical"
                  onClick={(e) => {
                    e.stopPropagation()
                    onDeleteLink(link.id)
                    onSelectLink(null)
                  }}
                >
                  Remove link
                </button>
              </foreignObject>
            )}
          </g>
        )
      })}
    </svg>
  )
}
