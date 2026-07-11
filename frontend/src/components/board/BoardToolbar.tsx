// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Board toolbar
// ─────────────────────────────────────────────────────────────────

import { useState } from 'react';
import type { AgentFinding } from '../../lib/types';
import type { BoardSnapshot } from '../../lib/board-types';
import styles from './BoardToolbar.module.css';

interface Props {
  findings: AgentFinding[];
  linkMode: boolean;
  onToggleLinkMode: () => void;
  onAddSticky: () => void;
  onAddHypothesis: () => void;
  onAddFromFinding: (finding: AgentFinding, index: number) => void;
  onAutoLayout: () => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  snapshots: BoardSnapshot[];
  onSaveSnapshot: (label: string) => void;
  onRestoreSnapshot: (id: string) => void;
  onDeleteSnapshot: (id: string) => void;
  onResetView: () => void;
  onPresent: () => void;
  canPresent: boolean;
  onExit: () => void;
}

export function BoardToolbar({
  findings, linkMode, onToggleLinkMode, onAddSticky, onAddHypothesis, onAddFromFinding,
  onAutoLayout, onUndo, onRedo, canUndo, canRedo,
  snapshots, onSaveSnapshot, onRestoreSnapshot, onDeleteSnapshot,
  onResetView, onPresent, canPresent, onExit,
}: Props) {
  const [showFindings, setShowFindings] = useState(false);
  const [showSnapshots, setShowSnapshots] = useState(false);

  return (
    <div className={styles.root}>
      <div className={styles.group}>
        <button className={styles.backBtn} onClick={onExit} title="Back to workspace">‹ Workspace</button>
        <span className={styles.title}>Investigation Board</span>
      </div>

      <div className={styles.group}>
        <button className={styles.btn} onClick={onAddSticky}>+ Sticky note</button>
        <button className={styles.btn} onClick={onAddHypothesis}>+ Hypothesis</button>

        <div className={styles.dropdownWrap}>
          <button className={styles.btn} onClick={() => setShowFindings(v => !v)} disabled={!findings.length}>
            + From findings
          </button>
          {showFindings && (
            <div className={styles.dropdown}>
              {findings.length === 0 && <div className={styles.dropdownEmpty}>No findings yet</div>}
              {findings.map((f, i) => (
                <button key={i} className={styles.dropdownItem} onClick={() => { onAddFromFinding(f, i); setShowFindings(false); }}>
                  <span className={styles.dropdownType}>{f.finding_type.replace(/_/g, ' ')}</span>
                  <span className={styles.dropdownSummary}>{f.summary.slice(0, 60)}{f.summary.length > 60 ? '…' : ''}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <button className={`${styles.btn} ${linkMode ? styles.btnActive : ''}`} onClick={onToggleLinkMode}>
          {linkMode ? 'Linking…' : 'Link cards'}
        </button>
      </div>

      <div className={styles.group}>
        <button className={styles.iconOnly} onClick={onUndo} disabled={!canUndo} title="Undo">↶</button>
        <button className={styles.iconOnly} onClick={onRedo} disabled={!canRedo} title="Redo">↷</button>
        <button className={styles.btn} onClick={onAutoLayout}>Auto-layout</button>
        <button className={styles.btn} onClick={onResetView}>Reset view</button>
      </div>

      <div className={styles.group}>
        <div className={styles.dropdownWrap}>
          <button className={styles.btn} onClick={() => setShowSnapshots(v => !v)}>Snapshots</button>
          {showSnapshots && (
            <div className={styles.dropdown}>
              <button
                className={styles.dropdownItem}
                onClick={() => { onSaveSnapshot(`Snapshot ${snapshots.length + 1}`); }}
              >
                <span className={styles.dropdownType}>+ Save current board</span>
              </button>
              {snapshots.length === 0 && <div className={styles.dropdownEmpty}>No snapshots saved</div>}
              {snapshots.map((s) => (
                <div key={s.id} className={styles.snapshotRow}>
                  <button className={styles.dropdownItem} onClick={() => { onRestoreSnapshot(s.id); setShowSnapshots(false); }}>
                    <span className={styles.dropdownType}>{s.label}</span>
                    <span className={styles.dropdownSummary}>{new Date(s.timestamp).toLocaleString()}</span>
                  </button>
                  <button className={styles.snapshotDelete} onClick={() => onDeleteSnapshot(s.id)} title="Delete snapshot">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
        <button className={styles.btn} onClick={onPresent} disabled={!canPresent} title={canPresent ? 'Present pinned cards' : 'Pin cards to enable presentation'}>
          Present
        </button>
      </div>
    </div>
  );
}
