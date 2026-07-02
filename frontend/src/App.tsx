// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Root App
// Two modes: landing (idle) ↔ workspace (investigation active)
// Transition: landing fades out, workspace slides in.
// ─────────────────────────────────────────────────────────────────

import { useCallback, useEffect, useRef, useState } from 'react';
import { useInvestigation }   from './hooks/useInvestigation';
import { LandingScreen }      from './components/landing/LandingScreen';
import { WorkspaceLayout }    from './components/workspace/WorkspaceLayout';

type Mode = 'landing' | 'workspace';

export function App() {
  const [mode, setMode]         = useState<Mode>('landing');
  const [exiting, setExiting]   = useState(false);
  const exitTimer               = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [investigationState, investigationActions] = useInvestigation();

  // When investigation starts → switch to workspace
  const handleSubmit = useCallback((query: string) => {
    if (mode === 'landing') {
      // Brief exit animation before switching
      setExiting(true);
      exitTimer.current = setTimeout(() => {
        setExiting(false);
        setMode('workspace');
        investigationActions.start(query);
      }, 200);
    } else {
      investigationActions.start(query);
    }
  }, [mode, investigationActions]);

  // Reset → go back to landing
  const handleReset = useCallback(() => {
    investigationActions.reset();
    setMode('landing');
  }, [investigationActions]);

  useEffect(() => {
    return () => {
      if (exitTimer.current) clearTimeout(exitTimer.current);
    };
  }, []);

  // Page title reflects investigation state
  useEffect(() => {
    if (mode === 'workspace' && investigationState.query) {
      document.title = `SHERLOCK — ${investigationState.query.slice(0, 40)}`;
    } else {
      document.title = 'SHERLOCK — Crime Intelligence';
    }
  }, [mode, investigationState.query]);

  return (
    <main
      style={{
        width: '100%',
        height: '100%',
        opacity: exiting ? 0 : 1,
        transition: 'opacity 200ms ease',
      }}
    >
      {mode === 'landing' ? (
        <LandingScreen onSubmit={handleSubmit} />
      ) : (
        <WorkspaceLayout
          state={investigationState}
          actions={{ ...investigationActions, reset: handleReset }}
        />
      )}
    </main>
  );
}
