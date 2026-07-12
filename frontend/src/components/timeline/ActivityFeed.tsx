// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Live Activity Feed (stabilization pass)
//
// `state.feed` in useInvestigation.ts has accumulated every WSEvent as a
// chronological log since the very first version of this hook — started,
// each agent completing/skipping/failing, errors — but nothing ever
// rendered it. Collapsed by default (the pipeline steps above are the
// primary view); expand for the raw chronological trace, useful for
// understanding exactly what happened and in what order during a run,
// including agent failures once Phase 5's per-agent isolation added those.
// ─────────────────────────────────────────────────────────────────

import { useEffect, useRef, useState } from 'react';
import type { FeedEntry } from '../../lib/types';
import s from './ActivityFeed.module.css';

const STATUS_DOT: Record<FeedEntry['status'], string> = {
  started: s.dotStarted,
  done: s.dotDone,
  skipped: s.dotSkipped,
  failed: s.dotFailed,
  error: s.dotError,
};

export function ActivityFeed({ feed }: { feed: FeedEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [feed.length, expanded]);

  if (feed.length === 0) return null;

  return (
    <div className={s.root}>
      <button
        className={s.toggle}
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
        aria-controls="activity-feed-list"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 150ms' }}>
          <polyline points="9 18 15 12 9 6" />
        </svg>
        <span>Activity Feed</span>
        <span className={s.count}>{feed.length}</span>
      </button>

      {expanded && (
        <div id="activity-feed-list" className={s.list} ref={scrollRef}>
          {feed.map(entry => (
            <div key={entry.id} className={s.entry}>
              <span className={`${s.dot} ${STATUS_DOT[entry.status]}`} aria-hidden />
              <div className={s.entryBody}>
                <div className={s.entryHead}>
                  <span className={s.agent}>{entry.agent}</span>
                  <span className={s.time}>{entry.timestamp}</span>
                </div>
                <p className={s.message}>{entry.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
