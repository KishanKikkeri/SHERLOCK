// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Voice control widget (Phase 4)
// Floating control for the board: push-to-talk button, wake-word
// toggle, live VU meter, transcript preview, command feedback toast.
// ─────────────────────────────────────────────────────────────────

import type { useVoice } from '../../hooks/useVoice';
import styles from './VoiceIndicator.module.css';

interface Props {
  voice: ReturnType<typeof useVoice>;
  feedback: string | null;
}

export function VoiceIndicator({ voice, feedback }: Props) {
  const { state, actions } = voice;

  if (!state.supported) {
    return (
      <div className={styles.root}>
        <div className={styles.unsupported}>
          Voice control isn't supported in this browser — try Chrome, Edge, or Safari 16+.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      {feedback && <div className={styles.toast}>{feedback}</div>}

      {(state.dictating || state.wakeListening) && (
        <div className={styles.meterRow}>
          <div className={styles.meterTrack}>
            <div className={styles.meterFill} style={{ width: `${Math.round(state.audioLevel * 100)}%` }} />
          </div>
          {state.transcript && <span className={styles.transcript}>"{state.transcript}"</span>}
        </div>
      )}

      <div className={styles.controls}>
        <button
          className={`${styles.wakeBtn} ${state.wakeListening ? styles.active : ''}`}
          onClick={actions.toggleWakeListening}
          title={state.wakeListening ? 'Stop listening for "Sherlock"' : 'Listen for wake word "Sherlock"'}
        >
          {state.wakeListening ? '👂 Listening for "Sherlock"' : 'Wake word off'}
        </button>

        <button
          className={`${styles.pttBtn} ${state.dictating ? styles.active : ''}`}
          onPointerDown={actions.startPushToTalk}
          onPointerUp={actions.stopPushToTalk}
          onPointerLeave={() => { if (state.dictating) actions.stopPushToTalk(); }}
          title="Hold to talk"
          aria-pressed={state.dictating}
        >
          🎙 Hold to talk
        </button>
      </div>

      {state.error && <div className={styles.error}>Voice error: {state.error}</div>}
    </div>
  );
}
