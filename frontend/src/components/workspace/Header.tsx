// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Workspace Header
// Logo · active query summary · subtle live metrics strip
// ─────────────────────────────────────────────────────────────────

import type { Metrics } from '../../lib/types';
import styles from './Header.module.css';

interface Props {
  query: string;
  metrics: Metrics | null;
  onReset: () => void;
  onOpenBoard: () => void;
}

function MetricPill({ value, label }: { value: number | undefined; label: string }) {
  return (
    <div className={styles.metric}>
      <span className={styles.metricVal}>{value?.toLocaleString() ?? '—'}</span>
      <span className={styles.metricLabel}>{label}</span>
    </div>
  );
}

export function Header({ query, metrics, onReset, onOpenBoard }: Props) {
  return (
    <header className={styles.root}>
      {/* Left: logo + query */}
      <div className={styles.left}>
        <button
          className={styles.logo}
          onClick={onReset}
          aria-label="Return to landing screen"
          title="New investigation"
        >
          <svg width="20" height="20" viewBox="0 0 28 28" fill="none" aria-hidden>
            <rect width="28" height="28" rx="6" fill="#38BDF8" fillOpacity="0.15" />
            <path d="M7 10h14M7 14h9M7 18h11" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="21" cy="18" r="4" stroke="#38BDF8" strokeWidth="1.5" />
            <path d="M24 21l2.5 2.5" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span className={styles.logoText}>SHERLOCK</span>
        </button>

        <span className={styles.sep} aria-hidden>/</span>

        <p className={styles.queryLabel} title={query}>
          {query.length > 80 ? query.slice(0, 80) + '…' : query}
        </p>
      </div>

      {/* Right: metrics + board nav */}
      <div className={styles.right}>
        <button className={styles.boardBtn} onClick={onOpenBoard} title="Open Investigation Board">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
            <rect x="3" y="3" width="8" height="8" rx="1.5" />
            <rect x="13" y="3" width="8" height="5" rx="1.5" />
            <rect x="13" y="10" width="8" height="11" rx="1.5" />
            <rect x="3" y="13" width="8" height="8" rx="1.5" />
          </svg>
          Board
        </button>

        {metrics && (
          <div className={styles.metrics} role="complementary" aria-label="Dataset metrics">
            <MetricPill value={metrics.persons} label="persons" />
            <div className={styles.metricDivider} aria-hidden />
            <MetricPill value={metrics.crimes} label="crimes" />
            <div className={styles.metricDivider} aria-hidden />
            <MetricPill value={metrics.relationships} label="graph edges" />
            <div className={styles.metricDivider} aria-hidden />
            <MetricPill value={metrics.repeat_offenders} label="repeat offenders" />

            {/* Live status indicator */}
            <div className={styles.statusWrap} aria-label="System operational">
              <span className={styles.statusDot} aria-hidden />
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
