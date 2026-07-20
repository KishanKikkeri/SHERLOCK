// Ported from frontend/src/lib/board-types.ts (Golden Rule 4 — don't
// duplicate proven logic) and extended: 'timeline' kind (brief asks for
// "Timeline events"), groupId/groupColor (Grouping), and sharedObjectId
// (links a local card to a persisted BoardObject once shared).
import type { GraphNodeType } from '@/lib/types'

export type BoardCardKind = 'evidence' | 'note' | 'hypothesis' | 'timeline'

export interface BoardCard {
  id: string
  kind: BoardCardKind
  x: number
  y: number
  w: number
  h: number
  title: string
  body: string
  color: string // hex — left border (evidence/hypothesis/timeline) or sticky background (note)
  entityType?: GraphNodeType // evidence cards — drives color + icon via graph/entity-meta
  confidence?: number // hypothesis cards — 0..1
  timestamp?: string // timeline cards
  pinned?: boolean // included in presentation-mode sequence
  groupId?: string
  groupColor?: string
  /** Set once "Share to team" persists this card as a BoardObject.
   * Comments/reviews attach to that id, not the local card id, since
   * they need a stable server-side target. */
  sharedObjectId?: number
}

export interface BoardLink {
  id: string
  from: string // card id
  to: string // card id
  label?: string
  color?: string
}

export interface BoardData {
  cards: BoardCard[]
  links: BoardLink[]
}

export interface BoardSnapshot {
  id: string
  label: string
  timestamp: string
  data: BoardData
}

export const STICKY_COLORS = ['#F59E0B', '#38BDF8', '#10B981', '#EC4899', '#8B5CF6', '#EF4444']
export const GROUP_COLORS = ['#38BDF8', '#A78BFA', '#34D399', '#FB923C', '#F472B6', '#FACC15']

export function newCardId(): string {
  return `card_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function newLinkId(): string {
  return `link_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function newGroupId(): string {
  return `group_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}
