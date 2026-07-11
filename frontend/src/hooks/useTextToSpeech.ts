// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Text-to-speech only (Phase 4)
// Separate from useVoice on purpose: read-aloud features shouldn't
// request microphone permission at all.
// ─────────────────────────────────────────────────────────────────

import { useCallback, useState } from 'react';

export function useTextToSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== 'undefined' && !!window.speechSynthesis;

  const speak = useCallback((text: string) => {
    if (!supported) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.02;
    utter.onstart = () => setSpeaking(true);
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utter);
  }, [supported]);

  const cancel = useCallback(() => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  return { supported, speaking, speak, cancel };
}
