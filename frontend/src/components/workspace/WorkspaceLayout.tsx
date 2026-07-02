// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Workspace Layout
// Investigation mode. Composes all panels into the full workspace.
// Handles: metrics fetch, graph fetch, PDF export.
// ─────────────────────────────────────────────────────────────────

import { useEffect, useState } from 'react';
import { downloadBlob, exportPDF, fetchMetrics, fetchSubgraph } from '../../lib/api';
import type { GraphData, Metrics } from '../../lib/types';
import type { InvestigationActions, InvestigationState } from '../../hooks/useInvestigation';
import { Header }                 from './Header';
import { InvestigationTimeline }  from '../timeline/InvestigationTimeline';
import { GraphPanel }             from '../graph/GraphPanel';
import { FindingsPanel }          from '../findings/FindingsPanel';
import { NLConsole }              from '../console/NLConsole';
import styles from './WorkspaceLayout.module.css';

interface Props {
  state: InvestigationState;
  actions: InvestigationActions;
}

export function WorkspaceLayout({ state, actions }: Props) {
  const [metrics,      setMetrics]      = useState<Metrics | null>(null);
  const [graphData,    setGraphData]    = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [exportingPDF, setExportingPDF] = useState(false);

  // Fetch metrics once on mount
  useEffect(() => {
    fetchMetrics().then(setMetrics).catch(() => {});
  }, []);

  // Fetch subgraph when a relevant person ID appears
  const personId = state.graphPersonId ?? state.graphHubPersonId;
  useEffect(() => {
    if (!personId) { setGraphData(null); return; }
    setGraphLoading(true);
    fetchSubgraph(personId, 1)
      .then(setGraphData)
      .catch(() => {})
      .finally(() => setGraphLoading(false));
  }, [personId]);

  // PDF export
  const handleExportPDF = async () => {
    if (!state.finalReport) return;
    setExportingPDF(true);
    try {
      const caseId = `INV-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${Math.floor(Math.random() * 9000 + 1000)}`;
      const blob = await exportPDF(state.finalReport, state.auditTrail, caseId);
      downloadBlob(blob, `SHERLOCK-${caseId}.pdf`);
    } catch (e) {
      alert(`PDF export failed: ${e}`);
    } finally {
      setExportingPDF(false);
    }
  };

  return (
    <div className={styles.root}>
      {/* Top: header */}
      <Header
        query={state.query}
        metrics={metrics}
        onReset={actions.reset}
      />

      {/* Middle: three-column workspace */}
      <div className={styles.workspace}>
        {/* Left: investigation timeline */}
        <InvestigationTimeline
          steps={state.steps}
          elapsedMs={state.elapsedMs}
        />

        {/* Center: intelligence graph */}
        <GraphPanel
          graphData={graphData}
          isLoading={graphLoading}
          personId={personId}
        />

        {/* Right: findings + actions */}
        <FindingsPanel
          findings={state.validatedFindings}
          isComplete={state.status === 'complete'}
          onExportPDF={handleExportPDF}
          exportingPDF={exportingPDF}
        />
      </div>

      {/* Bottom: natural language console */}
      <NLConsole
        onSubmit={actions.start}
        isRunning={state.status === 'running'}
        lastQuery={state.query}
      />
    </div>
  );
}
