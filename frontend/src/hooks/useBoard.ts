// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Investigation Board state (Phase 3)
// Cards + links with undo/redo history, localStorage snapshots,
// and force-directed auto-layout (lazy-loaded d3).
// ─────────────────────────────────────────────────────────────────

import { useCallback, useRef, useState } from 'react';
import type { AgentFinding } from '../lib/types';
import {
  type BoardCard, type BoardData, type BoardLink, type BoardSnapshot,
  EVIDENCE_COLORS, STICKY_COLORS, newCardId, newLinkId,
} from '../lib/board-types';

const SNAPSHOT_KEY = 'sherlock-board-snapshots';
const MAX_HISTORY = 50;

function emptyData(): BoardData {
  return { cards: [], links: [] };
}

function loadSnapshots(): BoardSnapshot[] {
  try {
    const raw = localStorage.getItem(SNAPSHOT_KEY);
    return raw ? (JSON.parse(raw) as BoardSnapshot[]) : [];
  } catch {
    return [];
  }
}

function saveSnapshots(snaps: BoardSnapshot[]) {
  try { localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(snaps)); } catch { /* storage unavailable — ignore */ }
}

export interface BoardActions {
  addCard: (partial: Partial<BoardCard> & { kind: BoardCard['kind'] }) => void;
  addStickyNote: () => void;
  addFromFinding: (finding: AgentFinding, index: number) => void;
  moveCard: (id: string, x: number, y: number, commit: boolean) => void;
  editCard: (id: string, patch: Partial<BoardCard>) => void;
  deleteCard: (id: string) => void;
  addLink: (from: string, to: string, label?: string) => void;
  deleteLink: (id: string) => void;
  undo: () => void;
  redo: () => void;
  autoLayout: () => void;
  saveSnapshot: (label: string) => void;
  restoreSnapshot: (id: string) => void;
  deleteSnapshot: (id: string) => void;
}

export function useBoard() {
  const [data, setData]           = useState<BoardData>(emptyData());
  const [snapshots, setSnapshots] = useState<BoardSnapshot[]>(() => loadSnapshots());
  const past   = useRef<BoardData[]>([]);
  const future = useRef<BoardData[]>([]);
  const dragOrigin = useRef<BoardData | null>(null);

  const commit = useCallback((next: BoardData, recordHistory = true) => {
    if (recordHistory) {
      past.current = [...past.current.slice(-(MAX_HISTORY - 1)), data];
      future.current = [];
    }
    setData(next);
  }, [data]);

  const addCard = useCallback((partial: Partial<BoardCard> & { kind: BoardCard['kind'] }) => {
    const card: BoardCard = {
      id: newCardId(), x: 120, y: 120, w: 200, h: 120,
      title: partial.kind === 'note' ? 'New note' : partial.kind === 'hypothesis' ? 'New hypothesis' : 'New evidence',
      body: '', color: STICKY_COLORS[0],
      ...partial,
    };
    commit({ ...data, cards: [...data.cards, card] });
  }, [data, commit]);

  const addStickyNote = useCallback(() => {
    const color = STICKY_COLORS[data.cards.filter(c => c.kind === 'note').length % STICKY_COLORS.length];
    addCard({ kind: 'note', color, x: 200 + Math.random() * 120, y: 160 + Math.random() * 120 });
  }, [addCard, data.cards]);

  const addFromFinding = useCallback((finding: AgentFinding, index: number) => {
    const entityType = (finding.metadata?.entity_type as string) as BoardCard['entityType'] | undefined;
    addCard({
      kind: 'evidence',
      title: finding.finding_type.replace(/_/g, ' '),
      body: finding.summary,
      color: EVIDENCE_COLORS[entityType ?? 'Person'] ?? '#38BDF8',
      entityType,
      confidence: finding.confidence,
      sourceFindingIndex: index,
      x: 160 + Math.random() * 300,
      y: 140 + Math.random() * 240,
      w: 220, h: 140,
    });
  }, [addCard]);

  // Drag: don't spam history — snapshot origin on first move, commit once on release.
  const moveCard = useCallback((id: string, x: number, y: number, commitFinal: boolean) => {
    if (!dragOrigin.current) dragOrigin.current = data;
    const next = { ...data, cards: data.cards.map(c => c.id === id ? { ...c, x, y } : c) };
    if (commitFinal) {
      past.current = [...past.current.slice(-(MAX_HISTORY - 1)), dragOrigin.current];
      future.current = [];
      dragOrigin.current = null;
      setData(next);
    } else {
      setData(next); // live move, no history entry yet
    }
  }, [data]);

  const editCard = useCallback((id: string, patch: Partial<BoardCard>) => {
    commit({ ...data, cards: data.cards.map(c => c.id === id ? { ...c, ...patch } : c) });
  }, [data, commit]);

  const deleteCard = useCallback((id: string) => {
    commit({
      cards: data.cards.filter(c => c.id !== id),
      links: data.links.filter(l => l.from !== id && l.to !== id),
    });
  }, [data, commit]);

  const addLink = useCallback((from: string, to: string, label?: string) => {
    if (from === to) return;
    if (data.links.some(l => (l.from === from && l.to === to) || (l.from === to && l.to === from))) return;
    commit({ ...data, links: [...data.links, { id: newLinkId(), from, to, label }] });
  }, [data, commit]);

  const deleteLink = useCallback((id: string) => {
    commit({ ...data, links: data.links.filter(l => l.id !== id) });
  }, [data, commit]);

  const undo = useCallback(() => {
    if (!past.current.length) return;
    const prev = past.current[past.current.length - 1];
    past.current = past.current.slice(0, -1);
    future.current = [data, ...future.current];
    setData(prev);
  }, [data]);

  const redo = useCallback(() => {
    if (!future.current.length) return;
    const next = future.current[0];
    future.current = future.current.slice(1);
    past.current = [...past.current, data];
    setData(next);
  }, [data]);

  const autoLayout = useCallback(() => {
    if (!data.cards.length) return;
    import('d3').then((d3) => {
      type N = BoardCard & d3.SimulationNodeDatum;
      const nodes: N[] = data.cards.map(c => ({ ...c, x: c.x, y: c.y }));
      const links = data.links
        .map(l => ({ source: nodes.find(n => n.id === l.from)!, target: nodes.find(n => n.id === l.to)! }))
        .filter(l => l.source && l.target);

      const sim = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).distance(220).strength(0.5))
        .force('charge', d3.forceManyBody().strength(-500))
        .force('center', d3.forceCenter(500, 350))
        .force('collision', d3.forceCollide(140))
        .stop();

      for (let i = 0; i < 300; i++) sim.tick();

      past.current = [...past.current.slice(-(MAX_HISTORY - 1)), data];
      future.current = [];
      setData({
        ...data,
        cards: data.cards.map((c, i) => ({ ...c, x: Math.round(nodes[i].x ?? c.x), y: Math.round(nodes[i].y ?? c.y) })),
      });
    });
  }, [data]);

  const saveSnapshot = useCallback((label: string) => {
    const snap: BoardSnapshot = { id: `snap_${Date.now()}`, label, timestamp: new Date().toISOString(), data };
    const next = [snap, ...snapshots].slice(0, 20);
    setSnapshots(next);
    saveSnapshots(next);
  }, [data, snapshots]);

  const restoreSnapshot = useCallback((id: string) => {
    const snap = snapshots.find(s => s.id === id);
    if (!snap) return;
    commit(snap.data);
  }, [snapshots, commit]);

  const deleteSnapshot = useCallback((id: string) => {
    const next = snapshots.filter(s => s.id !== id);
    setSnapshots(next);
    saveSnapshots(next);
  }, [snapshots]);

  const actions: BoardActions = {
    addCard, addStickyNote, addFromFinding, moveCard, editCard, deleteCard,
    addLink, deleteLink, undo, redo, autoLayout,
    saveSnapshot, restoreSnapshot, deleteSnapshot,
  };

  return {
    data, snapshots, actions,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
  };
}
