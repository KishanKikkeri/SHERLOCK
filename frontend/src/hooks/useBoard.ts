// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Investigation Board state (Phase 3, stabilized)
// Cards + links with undo/redo history, localStorage snapshots,
// and force-directed auto-layout (lazy-loaded d3).
//
// STABILITY NOTE (stress-test fix): every action below is built with
// `useCallback(..., [])` or depends only on other stable callbacks —
// none of them depend on `data`/`snapshots` directly. They read the
// latest values either through React's functional setState form or
// through `dataRef` (a plain ref mirrored to `data` each render, used
// only for one-off reads inside a callback body, never for the state
// update itself). This matters a lot in practice: with unstable action
// identities, EvidenceCardView's React.memo can't do anything — every
// card would re-render on every pointer-move of a drag, which is
// exactly the kind of thing that only becomes visible ("janky
// dragging") once a board has hundreds of cards on it.
// ─────────────────────────────────────────────────────────────────

import { useCallback, useMemo, useRef, useState } from 'react';
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

function saveSnapshotsToStorage(snaps: BoardSnapshot[]) {
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

  // Mirror of the latest `data`, for one-off reads inside stable callbacks
  // (e.g. "how many sticky notes exist right now, to rotate the colour").
  // Never used to compute the actual next state — that always goes through
  // React's functional setData form so it can't race a stale closure.
  const dataRef = useRef(data);
  dataRef.current = data;

  // Stable: commits a state update, optionally recording history. Accepts
  // either a value or an updater function (mirrors React's own setState).
  const commit = useCallback((updater: BoardData | ((prev: BoardData) => BoardData), recordHistory = true) => {
    setData(prev => {
      const next = typeof updater === 'function' ? (updater as (p: BoardData) => BoardData)(prev) : updater;
      if (recordHistory) {
        past.current = [...past.current.slice(-(MAX_HISTORY - 1)), prev];
        future.current = [];
      }
      return next;
    });
  }, []);

  const addCard = useCallback((partial: Partial<BoardCard> & { kind: BoardCard['kind'] }) => {
    const card: BoardCard = {
      id: newCardId(), x: 120, y: 120, w: 200, h: 120,
      title: partial.kind === 'note' ? 'New note' : partial.kind === 'hypothesis' ? 'New hypothesis' : 'New evidence',
      body: '', color: STICKY_COLORS[0],
      ...partial,
    };
    commit(prev => ({ ...prev, cards: [...prev.cards, card] }));
  }, [commit]);

  const addStickyNote = useCallback(() => {
    const color = STICKY_COLORS[dataRef.current.cards.filter(c => c.kind === 'note').length % STICKY_COLORS.length];
    addCard({ kind: 'note', color, x: 200 + Math.random() * 120, y: 160 + Math.random() * 120 });
  }, [addCard]);

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
    if (!dragOrigin.current) dragOrigin.current = dataRef.current;
    if (commitFinal) {
      const origin = dragOrigin.current;
      dragOrigin.current = null;
      setData(prev => {
        past.current = [...past.current.slice(-(MAX_HISTORY - 1)), origin ?? prev];
        future.current = [];
        return { ...prev, cards: prev.cards.map(c => c.id === id ? { ...c, x, y } : c) };
      });
    } else {
      setData(prev => ({ ...prev, cards: prev.cards.map(c => c.id === id ? { ...c, x, y } : c) })); // live move, no history entry yet
    }
  }, []);

  const editCard = useCallback((id: string, patch: Partial<BoardCard>) => {
    commit(prev => ({ ...prev, cards: prev.cards.map(c => c.id === id ? { ...c, ...patch } : c) }));
  }, [commit]);

  const deleteCard = useCallback((id: string) => {
    commit(prev => ({
      cards: prev.cards.filter(c => c.id !== id),
      links: prev.links.filter(l => l.from !== id && l.to !== id),
    }));
  }, [commit]);

  const addLink = useCallback((from: string, to: string, label?: string) => {
    if (from === to) return;
    commit(prev => {
      if (prev.links.some(l => (l.from === from && l.to === to) || (l.from === to && l.to === from))) return prev;
      return { ...prev, links: [...prev.links, { id: newLinkId(), from, to, label }] };
    });
  }, [commit]);

  const deleteLink = useCallback((id: string) => {
    commit(prev => ({ ...prev, links: prev.links.filter(l => l.id !== id) }));
  }, [commit]);

  const undo = useCallback(() => {
    if (!past.current.length) return;
    const prevSnapshot = past.current[past.current.length - 1];
    past.current = past.current.slice(0, -1);
    setData(current => {
      future.current = [current, ...future.current];
      return prevSnapshot;
    });
  }, []);

  const redo = useCallback(() => {
    if (!future.current.length) return;
    const nextSnapshot = future.current[0];
    future.current = future.current.slice(1);
    setData(current => {
      past.current = [...past.current, current];
      return nextSnapshot;
    });
  }, []);

  const autoLayout = useCallback(() => {
    const startedFrom = dataRef.current;
    if (!startedFrom.cards.length) return;
    import('d3').then((d3) => {
      // Re-read latest data instead of relying on the closure — the dynamic
      // import is async, so the board could have changed while it resolved.
      const current = dataRef.current;
      type N = BoardCard & d3.SimulationNodeDatum;
      const nodes: N[] = current.cards.map(c => ({ ...c, x: c.x, y: c.y }));
      const links = current.links
        .map(l => ({ source: nodes.find(n => n.id === l.from)!, target: nodes.find(n => n.id === l.to)! }))
        .filter(l => l.source && l.target);

      const sim = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).distance(220).strength(0.5))
        .force('charge', d3.forceManyBody().strength(-500))
        .force('center', d3.forceCenter(500, 350))
        .force('collision', d3.forceCollide(140))
        .stop();

      for (let i = 0; i < 300; i++) sim.tick();

      setData(prev => {
        past.current = [...past.current.slice(-(MAX_HISTORY - 1)), prev];
        future.current = [];
        return {
          ...prev,
          cards: prev.cards.map((c, i) => ({ ...c, x: Math.round(nodes[i]?.x ?? c.x), y: Math.round(nodes[i]?.y ?? c.y) })),
        };
      });
    });
  }, []);

  const saveSnapshot = useCallback((label: string) => {
    const snap: BoardSnapshot = { id: `snap_${Date.now()}`, label, timestamp: new Date().toISOString(), data: dataRef.current };
    setSnapshots(prev => {
      const next = [snap, ...prev].slice(0, 20);
      saveSnapshotsToStorage(next);
      return next;
    });
  }, []);

  const restoreSnapshot = useCallback((id: string) => {
    const snap = snapshots.find(s => s.id === id);
    if (!snap) return;
    commit(snap.data);
  }, [snapshots, commit]);

  const deleteSnapshot = useCallback((id: string) => {
    setSnapshots(prev => {
      const next = prev.filter(s => s.id !== id);
      saveSnapshotsToStorage(next);
      return next;
    });
  }, []);

  const actions: BoardActions = useMemo(() => ({
    addCard, addStickyNote, addFromFinding, moveCard, editCard, deleteCard,
    addLink, deleteLink, undo, redo, autoLayout,
    saveSnapshot, restoreSnapshot, deleteSnapshot,
  }), [
    addCard, addStickyNote, addFromFinding, moveCard, editCard, deleteCard,
    addLink, deleteLink, undo, redo, autoLayout,
    saveSnapshot, restoreSnapshot, deleteSnapshot,
  ]);

  return {
    data, snapshots, actions,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
  };
}
