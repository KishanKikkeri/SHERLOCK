// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Workspace Layout
// Investigation mode. Composes all panels into the full workspace.
// Handles: metrics fetch, graph fetch, PDF export, and the voice
// conversation loop (owns the one useVoice instance for this screen
// so console input and spoken replies share the same mic/TTS state).
// ─────────────────────────────────────────────────────────────────

import { useCallback, useEffect, useRef, useState } from 'react';
import { downloadBlob, exportPDF, fetchMetrics, fetchSubgraph } from '../../lib/api';
import type { GraphData, Metrics } from '../../lib/types';
import type { InvestigationActions, InvestigationState } from '../../hooks/useInvestigation';
import { useVoice } from '../../hooks/useVoice';
import { Header }                 from './Header';
import { InvestigationTimeline }  from '../timeline/InvestigationTimeline';
import { GraphPanel }             from '../graph/GraphPanel';
import { FindingsPanel }          from '../findings/FindingsPanel';
import { NLConsole }              from '../console/NLConsole';
import styles from './WorkspaceLayout.module.css';

interface Props {
  state: InvestigationState;
  actions: InvestigationActions;
  onOpenBoard: () => void;
}

export function WorkspaceLayout({ state, actions, onOpenBoard }: Props) {
  const [metrics,      setMetrics]      = useState<Metrics | null>(null);
  const [graphData,    setGraphData]    = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [exportingPDF, setExportingPDF] = useState(false);

  // Was the query that's currently running (or just finished) submitted by voice?
  // Only voice-initiated queries get read back automatically — typed queries keep
  // the manual button, since a person typing at their desk didn't ask to be talked at.
  const viaVoiceRef = useRef(false);
  const spokenForRunRef = useRef(false);

  const handleSubmit = useCallback((query: string, viaVoice?: boolean) => {
    viaVoiceRef.current = !!viaVoice;
    spokenForRunRef.current = false;
    actions.start(query);
  }, [actions]);

  const onVoiceQuery = useCallback((text: string) => {
    if (state.status !== 'running') handleSubmit(text, true);
  }, [state.status, handleSubmit]);

  // One voice instance for the whole workspace — console input (wake word /
  // push-to-talk) and the spoken reply below both go through it, so `speak()`
  // can safely pause wake-word listening while it talks (see useVoice.ts) and
  // FindingsPanel's manual "read aloud" button shares the same speaking state.
  const voice = useVoice(onVoiceQuery);

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

  // The conversational loop: once a voice-initiated investigation finishes (or
  // fails), speak the result once — without this, "talking to it" would still
  // end in silence and you'd have to go read the screen, which defeats the point.
  useEffect(() => {
    if (!viaVoiceRef.current || spokenForRunRef.current) return;

    if (state.status === 'complete' && state.finalReport?.narrative) {
      spokenForRunRef.current = true;
      voice.actions.speak(state.finalReport.narrative);
    } else if (state.status === 'error') {
      spokenForRunRef.current = true;
      voice.actions.speak("Something went wrong with that investigation — check the activity feed for details.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status, state.finalReport]);

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

  const handleReset = () => {
    viaVoiceRef.current = false;
    spokenForRunRef.current = false;
    voice.actions.cancelSpeech();
    actions.reset();
  };

  return (
    <div className={styles.root}>
      {/* Top: header */}
      <Header
        query={state.query}
        metrics={metrics}
        onReset={handleReset}
        onOpenBoard={onOpenBoard}
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
          narrative={state.finalReport?.narrative ?? null}
          voice={voice}
        />
      </div>

      {/* Bottom: natural language console */}
      <NLConsole
        onSubmit={handleSubmit}
        isRunning={state.status === 'running'}
        lastQuery={state.query}
        voice={voice}
      />
    </div>
  );
}
