// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Investigation Board domain types (Phase 3)
// ─────────────────────────────────────────────────────────────────

import type { NodeType } from './types';

export type BoardCardKind = 'evidence' | 'note' | 'hypothesis';

export interface BoardCard {
  id: string;
  kind: BoardCardKind;
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  body: string;
  color: string;                 // hex — drives left border / sticky background
  entityType?: NodeType;         // evidence cards only — drives type colour + icon
  confidence?: number;           // hypothesis cards only — 0..1
  pinned?: boolean;              // included in presentation-mode sequence
  sourceFindingIndex?: number;   // back-reference to the AgentFinding it was pulled from
}

export interface BoardLink {
  id: string;
  from: string;                  // card id
  to: string;                    // card id
  label?: string;
  color?: string;
}

export interface BoardData {
  cards: BoardCard[];
  links: BoardLink[];
}

export interface BoardSnapshot {
  id: string;
  label: string;
  timestamp: string;
  data: BoardData;
}

export const STICKY_COLORS = ['#F59E0B', '#38BDF8', '#10B981', '#EC4899', '#8B5CF6', '#EF4444'];

export const EVIDENCE_COLORS: Record<NodeType | string, string> = {
  Person: '#38BDF8', Crime: '#EF4444', FIR: '#EC4899', Location: '#10B981',
  BankAccount: '#F59E0B', Phone: '#8B5CF6', Vehicle: '#6B7280', Transaction: '#F97316',
};

export function newCardId(): string {
  return `card_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function newLinkId(): string {
  return `link_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}
