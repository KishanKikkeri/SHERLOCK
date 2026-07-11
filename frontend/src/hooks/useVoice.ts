// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Voice interface (Phase 4)
// Wraps the browser's native SpeechRecognition (STT) and
// SpeechSynthesis (TTS) APIs. No server round-trip for voice itself —
// only the resulting text query goes over the wire, same as typing.
//
// Browser support note: SpeechRecognition is Chrome/Edge/Safari-16+
// only (no Firefox). We feature-detect and expose `supported` so the
// UI can degrade to text-only instead of silently failing.
//
// "Noise filtering" here means confidence-gating + a short debounce
// on interim results — the Web Speech API gives no lower-level audio
// denoising hook, so true acoustic noise suppression isn't available
// from JS. The VU meter is a real mic-level read (Web Audio API),
// used as a lightweight voice-activity indicator, not true VAD.
// ─────────────────────────────────────────────────────────────────

import { useCallback, useEffect, useRef, useState } from 'react';

const DEFAULT_WAKE_WORD = 'sherlock';
const MIN_CONFIDENCE = 0.35; // below this, treat interim result as noise

function getRecognitionCtor(): SpeechRecognitionStatic | null {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export interface VoiceState {
  supported: boolean;
  wakeListening: boolean;   // background "listening for wake word" loop is on
  dictating: boolean;       // actively capturing a command right now
  transcript: string;       // live interim text while dictating
  audioLevel: number;       // 0..1 mic level, for the VU meter
  speaking: boolean;        // TTS currently reading something aloud
  error: string | null;
}

export interface VoiceActions {
  toggleWakeListening: () => void;
  startPushToTalk: () => void;
  stopPushToTalk: () => void;
  speak: (text: string, onEnd?: () => void) => void;
  cancelSpeech: () => void;
}

export function useVoice(onCommand: (text: string) => void, wakeWord = DEFAULT_WAKE_WORD) {
  const Ctor = getRecognitionCtor();
  const [state, setState] = useState<VoiceState>({
    supported: !!Ctor,
    wakeListening: false,
    dictating: false,
    transcript: '',
    audioLevel: 0,
    speaking: false,
    error: null,
  });

  const recogRef       = useRef<SpeechRecognition | null>(null);
  const wantWakeRef    = useRef(false);   // should we auto-restart recognition on 'end'?
  const modeRef        = useRef<'wake' | 'ptt' | null>(null);
  const audioCtxRef    = useRef<AudioContext | null>(null);
  const streamRef      = useRef<MediaStream | null>(null);
  const rafRef         = useRef<number | null>(null);
  const lastMeterAtRef = useRef(0);
  const dictatingRef   = useRef(false);   // live mirror of state.dictating — onresult closures must not read stale state

  // ── VU meter (real mic level via Web Audio API) ────────────────
  const startMeter = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sumSq = 0;
        for (let i = 0; i < data.length; i++) { const v = (data[i] - 128) / 128; sumSq += v * v; }
        const rms = Math.sqrt(sumSq / data.length);
        const now = performance.now();
        if (now - lastMeterAtRef.current > 60) { // throttle re-renders
          lastMeterAtRef.current = now;
          setState((s) => ({ ...s, audioLevel: Math.min(1, rms * 4) }));
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // mic permission denied for the meter specifically — recognition may still work
    }
  }, []);

  const stopMeter = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    setState((s) => ({ ...s, audioLevel: 0 }));
  }, []);

  // ── Core recognition lifecycle ──────────────────────────────────
  const buildRecognition = useCallback((mode: 'wake' | 'ptt') => {
    if (!Ctor) return null;
    const r = new Ctor();
    r.continuous = mode === 'wake';
    r.interimResults = true;
    r.lang = 'en-US';

    r.onresult = (e: SpeechRecognitionEvent) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        const alt = res[0];
        if (alt.confidence !== undefined && alt.confidence > 0 && alt.confidence < MIN_CONFIDENCE) continue;
        const text = alt.transcript;

        if (mode === 'wake' && !dictatingRef.current) {
          const lower = text.toLowerCase();
          const idx = lower.indexOf(wakeWord);
          if (idx >= 0) {
            const remainder = text.slice(idx + wakeWord.length).trim();
            dictatingRef.current = true;
            setState((s) => ({ ...s, dictating: true, transcript: remainder }));
            if (res.isFinal && remainder) {
              onCommand(remainder);
              dictatingRef.current = false;
              setState((s) => ({ ...s, dictating: false, transcript: '' }));
            }
            continue;
          }
        } else {
          if (res.isFinal) {
            interim = '';
            dictatingRef.current = mode === 'ptt';
            setState((s) => ({ ...s, transcript: '', dictating: mode === 'ptt' }));
            if (text.trim()) onCommand(text.trim());
            if (mode === 'wake') dictatingRef.current = false; // back to waiting for the next wake word
          } else {
            interim = text;
          }
        }
      }
      if (interim) { dictatingRef.current = true; setState((s) => ({ ...s, transcript: interim, dictating: true })); }
    };

    r.onerror = (e: SpeechRecognitionErrorEvent) => {
      if (e.error === 'no-speech' || e.error === 'aborted') return;
      setState((s) => ({ ...s, error: e.error }));
    };

    r.onend = () => {
      if (mode === 'wake' && wantWakeRef.current) {
        try { r.start(); } catch { /* already starting — ignore */ }
      } else if (mode === 'ptt') {
        setState((s) => ({ ...s, dictating: false, transcript: '' }));
      }
    };

    return r;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Ctor, wakeWord, onCommand]);

  const toggleWakeListening = useCallback(() => {
    if (!Ctor) return;
    if (state.wakeListening) {
      wantWakeRef.current = false;
      dictatingRef.current = false;
      recogRef.current?.stop();
      recogRef.current = null;
      modeRef.current = null;
      stopMeter();
      setState((s) => ({ ...s, wakeListening: false, dictating: false, transcript: '' }));
    } else {
      wantWakeRef.current = true;
      modeRef.current = 'wake';
      const r = buildRecognition('wake');
      recogRef.current = r;
      r?.start();
      startMeter();
      setState((s) => ({ ...s, wakeListening: true, error: null }));
    }
  }, [Ctor, state.wakeListening, buildRecognition, startMeter, stopMeter]);

  const startPushToTalk = useCallback(() => {
    if (!Ctor) return;
    // Push-to-talk takes priority — pause wake listening while held.
    if (state.wakeListening) { wantWakeRef.current = false; recogRef.current?.stop(); }
    modeRef.current = 'ptt';
    dictatingRef.current = true;
    const r = buildRecognition('ptt');
    recogRef.current = r;
    try { r?.start(); } catch { /* ignore double-start */ }
    if (!streamRef.current) startMeter();
    setState((s) => ({ ...s, dictating: true, error: null }));
  }, [Ctor, state.wakeListening, buildRecognition, startMeter]);

  const stopPushToTalk = useCallback(() => {
    recogRef.current?.stop();
    if (state.wakeListening) {
      // resume background wake-word listening
      wantWakeRef.current = true;
      modeRef.current = 'wake';
      const r = buildRecognition('wake');
      recogRef.current = r;
      try { r?.start(); } catch { /* ignore */ }
    } else {
      stopMeter();
    }
  }, [state.wakeListening, buildRecognition, stopMeter]);

  // ── Text-to-speech ──────────────────────────────────────────────
  // Pauses wake-word listening for the duration of the utterance and resumes
  // it afterward — without this, an open mic would risk picking up Sherlock's
  // own voice as a new command (or re-triggering the wake word if it ever
  // appears in what it's reading back).
  const speak = useCallback((text: string, onEnd?: () => void) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) { onEnd?.(); return; }

    const wasWakeListening = wantWakeRef.current;
    if (wasWakeListening) {
      wantWakeRef.current = false;
      recogRef.current?.stop();
      recogRef.current = null;
    }

    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.02;
    utter.onstart = () => setState((s) => ({ ...s, speaking: true }));
    const resumeAndFinish = () => {
      setState((s) => ({ ...s, speaking: false }));
      if (wasWakeListening) {
        wantWakeRef.current = true;
        modeRef.current = 'wake';
        const r = buildRecognition('wake');
        recogRef.current = r;
        try { r?.start(); } catch { /* ignore */ }
      }
      onEnd?.();
    };
    utter.onend = resumeAndFinish;
    utter.onerror = resumeAndFinish;
    window.speechSynthesis.speak(utter);
  }, [buildRecognition]);

  const cancelSpeech = useCallback(() => {
    window.speechSynthesis?.cancel();
    setState((s) => ({ ...s, speaking: false }));
  }, []);

  useEffect(() => () => {
    wantWakeRef.current = false;
    recogRef.current?.stop();
    stopMeter();
    window.speechSynthesis?.cancel();
  }, [stopMeter]);

  const actions: VoiceActions = { toggleWakeListening, startPushToTalk, stopPushToTalk, speak, cancelSpeech };
  return { state, actions };
}
