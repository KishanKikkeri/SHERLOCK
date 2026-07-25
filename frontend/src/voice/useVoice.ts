// Ported from frontend/src/hooks/useVoice.ts (Golden Rule 4) — wake
// word, push-to-talk, and TTS via the browser's native SpeechRecognition
// / SpeechSynthesis APIs. No server round-trip for voice itself; only
// the resulting text goes over the wire (POST /voice/command).
//
// Priority 14-16 rewrite (Conversation, Voice & Graph Search Refactor):
// the previous version treated each SpeechRecognition session as the
// whole utterance, matched exactly one wake-word string, and had no
// interruption support. This version adds:
//   - flexible wake phrases (Priority 15) with normalized matching
//   - session chaining across the browser recognizer's own silence/
//     duration cutoffs, so a 30-60s utterance survives them instead of
//     being cut off (Priority 14 — real VAD isn't available from a
//     plain SpeechRecognition object, so this is the practical
//     equivalent: don't let an internal recognizer restart look like
//     the user finished talking)
//   - an active-conversation grace window so a follow-up doesn't need
//     the wake word repeated (Priority 15)
//   - barge-in: new speech while the assistant is talking cancels TTS
//     immediately (Priority 16)
//   - speakStream(), which reads out completed sentences as they
//     arrive rather than waiting for the full response (Priority 16)
//
// Extension over the original: exposes getAnalyser() so a canvas
// waveform can read live frequency-domain data itself, on its own
// rAF loop, without adding React state that would re-render at 60fps —
// same discipline as the graph module's tick handler (see
// graph/GraphView.tsx). The original only exposed a throttled scalar
// (audioLevel) for a simple bar meter; the brief asks for a waveform
// *and* a VU meter as distinct elements, so both are now supported
// from the same underlying AnalyserNode.
import { useCallback, useEffect, useRef, useState } from 'react'

// Priority 15 — "Hey Sherlock" / "Sherlock" / "Okay Sherlock" /
// "Hello Sherlock" / "Detective Sherlock" / "Assistant" should all work.
// Matched as whole-word sequences after stripping punctuation, so
// "sherlock," / "Sherlock!" / "hey, sherlock" all still hit.
const DEFAULT_WAKE_PHRASES = [
  'hey sherlock',
  'okay sherlock',
  'ok sherlock',
  'hello sherlock',
  'detective sherlock',
  'sherlock',
  'assistant',
]

const MIN_CONFIDENCE = 0.35 // below this, treat interim result as noise

// Priority 14 — a plain SpeechRecognition session ends on its own
// after a browser-specific silence/duration limit even in `continuous`
// mode; that's the "recognition stops too early" / "long utterances
// are cut off" complaint. There's no real silence-vs-cutoff signal
// exposed by the Web Speech API, so this is the practical proxy: if
// the recognizer ended less than RESTART_GRACE_MS after its last
// result, the user was very likely still mid-utterance (a real pause
// long enough to mean "I'm done" would show up as a longer gap), so
// silently start a fresh session and keep appending to the same
// transcript instead of treating it as finished.
const RESTART_GRACE_MS = 1800
// Priority 15 — "If user is already in active conversation: DO NOT
// require wake word again. Only require wake word after: timeout /
// manual stop / conversation closed." This is that timeout.
const CONVERSATION_ACTIVE_MS = 45_000

function getRecognitionCtor(): SpeechRecognitionStatic | null {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

function normalizePhrase(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** True if any wake phrase appears as a whole-word sequence in `text`. */
function findWakePhrase(text: string, phrases: string[]): { phrase: string; endIndex: number } | null {
  const norm = normalizePhrase(text)
  let best: { phrase: string; endIndex: number } | null = null
  for (const phrase of phrases) {
    const p = normalizePhrase(phrase)
    const idx = norm.indexOf(p)
    if (idx < 0) continue
    // Require a word boundary on both sides so "sherlock" doesn't
    // match inside an unrelated longer word.
    const before = idx === 0 || norm[idx - 1] === ' '
    const afterIdx = idx + p.length
    const after = afterIdx >= norm.length || norm[afterIdx] === ' '
    if (!before || !after) continue
    // Prefer the longest/most-specific phrase that matches (so "hey
    // sherlock" wins over bare "sherlock" when both are present).
    if (!best || p.length > normalizePhrase(best.phrase).length) {
      best = { phrase, endIndex: afterIdx }
    }
  }
  return best
}

/** Split completed sentences off the front of `text`; returns
 * [completeSentences, remainder]. A "sentence" ends at . ! or ? followed
 * by whitespace/end — good enough for spoken narration, not meant to be
 * a real sentence boundary detector. */
function splitCompleteSentences(text: string): [string[], string] {
  const matches = text.match(/[^.!?]+[.!?]+(?:\s+|$)/g)
  if (!matches) return [[], text]
  const consumed = matches.join('')
  const remainder = text.slice(consumed.length)
  return [matches.map((m) => m.trim()).filter(Boolean), remainder]
}

export interface VoiceState {
  supported: boolean
  wakeListening: boolean // background "listening for wake word" loop is on
  conversationActive: boolean // wake word already heard recently — no need to repeat it
  dictating: boolean // actively capturing a command right now
  transcript: string // live interim text while dictating (accumulated across chained sessions)
  audioLevel: number // 0..1 mic level, for the VU meter
  speaking: boolean // TTS currently reading something aloud
  error: string | null
}

export interface VoiceActions {
  toggleWakeListening: () => void
  startPushToTalk: () => void
  stopPushToTalk: () => void
  speak: (text: string, onEnd?: () => void) => void
  /** Priority 16 — speak a response as it streams in rather than
   * waiting for the whole thing. Call repeatedly with the growing text
   * (e.g. on every store update while isStreaming); pass done=true once
   * generation has finished so the trailing partial sentence gets
   * spoken too. Safe to call every render — it only acts on new text. */
  speakStream: (text: string, done: boolean) => void
  /** Reset speakStream's internal "already spoken up to here" cursor —
   * call when starting a new assistant turn. */
  resetSpeakStream: () => void
  cancelSpeech: () => void
  getAnalyser: () => AnalyserNode | null
}

export function useVoice(
  onCommand: (text: string) => void,
  language: 'en' | 'kn' = 'en',
  wakePhrases: string[] = DEFAULT_WAKE_PHRASES,
) {
  const Ctor = getRecognitionCtor()
  const [state, setState] = useState<VoiceState>({
    supported: !!Ctor,
    wakeListening: false,
    conversationActive: false,
    dictating: false,
    transcript: '',
    audioLevel: 0,
    speaking: false,
    error: null,
  })

  // Live mirror of the selected UI language — recognition/synthesis
  // callbacks are built once (or on restart) and must not close over a
  // stale value when the global LanguageProvider's language changes
  // mid-session (Phase 6: voice defaults follow the UI language).
  const languageRef = useRef(language)
  useEffect(() => {
    languageRef.current = language
  }, [language])

  const recogRef = useRef<SpeechRecognition | null>(null)
  const wantWakeRef = useRef(false) // should we auto-restart recognition on 'end'?
  const modeRef = useRef<'wake' | 'ptt' | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafRef = useRef<number | null>(null)
  const lastMeterAtRef = useRef(0)
  const dictatingRef = useRef(false) // live mirror of state.dictating — onresult closures must not read stale state
  const speakingRef = useRef(false) // live mirror of state.speaking — for barge-in

  // Priority 14 — session-chaining state, kept outside React state
  // since it's mutated inside recognition callbacks on every result.
  const lastResultAtRef = useRef(0)
  const committedTranscriptRef = useRef('') // finalized text accumulated across chained sessions
  const chainingRef = useRef(false) // true while we're mid multi-session utterance
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Priority 15 — active-conversation grace window.
  const conversationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const setConversationActive = useCallback((active: boolean) => {
    if (conversationTimerRef.current) clearTimeout(conversationTimerRef.current)
    setState((s) => ({ ...s, conversationActive: active }))
    if (active) {
      conversationTimerRef.current = setTimeout(() => {
        setState((s) => ({ ...s, conversationActive: false }))
      }, CONVERSATION_ACTIVE_MS)
    }
  }, [])

  // ── VU meter + waveform source (real mic level via Web Audio API) ──
  const startMeter = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const ctx = new AudioContext()
      audioCtxRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      source.connect(analyser)
      analyserRef.current = analyser
      const data = new Uint8Array(analyser.frequencyBinCount)

      const tick = () => {
        analyser.getByteTimeDomainData(data)
        let sumSq = 0
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128
          sumSq += v * v
        }
        const rms = Math.sqrt(sumSq / data.length)
        const now = performance.now()
        if (now - lastMeterAtRef.current > 60) {
          // throttle re-renders
          lastMeterAtRef.current = now
          setState((s) => ({ ...s, audioLevel: Math.min(1, rms * 4) }))
        }
        rafRef.current = requestAnimationFrame(tick)
      }
      tick()
    } catch {
      // mic permission denied for the meter specifically — recognition may still work
    }
  }, [])

  const stopMeter = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    audioCtxRef.current?.close().catch(() => {})
    audioCtxRef.current = null
    analyserRef.current = null
    setState((s) => ({ ...s, audioLevel: 0 }))
  }, [])

  // ── Core recognition lifecycle ──────────────────────────────────
  const buildRecognition = useCallback(
    (mode: 'wake' | 'ptt') => {
      if (!Ctor) return null
      const r = new Ctor()
      r.continuous = true
      r.interimResults = true
      r.lang = languageRef.current === 'kn' ? 'kn-IN' : 'en-US'

      r.onresult = (e: SpeechRecognitionEvent) => {
        lastResultAtRef.current = performance.now()

        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i]
          const alt = res[0]
          if (alt.confidence !== undefined && alt.confidence > 0 && alt.confidence < MIN_CONFIDENCE) continue
          const text = alt.transcript

          // Priority 16 — barge-in: any real speech while the
          // assistant is talking interrupts it immediately, whether
          // it's a wake-triggered command or a held-PTT one.
          if (speakingRef.current && text.trim()) {
            window.speechSynthesis?.cancel()
            speakingRef.current = false
            setState((s) => ({ ...s, speaking: false }))
          }

          const alreadyDictating = dictatingRef.current || state.conversationActive

          if (mode === 'wake' && !alreadyDictating) {
            const hit = findWakePhrase(text, wakePhrases)
            if (hit) {
              // Priority 15 — "Wake word should only activate
              // listening. NOT execute commands immediately." Only the
              // text *after* the wake phrase counts as command content.
              const remainder = text.slice(hit.endIndex).trim()
              dictatingRef.current = true
              committedTranscriptRef.current = ''
              setConversationActive(true)
              setState((s) => ({ ...s, dictating: true, transcript: remainder }))
              if (res.isFinal && remainder) {
                onCommand(remainder)
                dictatingRef.current = false
                committedTranscriptRef.current = ''
                setState((s) => ({ ...s, dictating: false, transcript: '' }))
              }
              continue
            }
            // Already-active conversation but this specific result
            // didn't carry the wake phrase and we weren't dictating —
            // nothing to do with it; wait for the next result.
            continue
          }

          // ptt mode, or wake mode already past the wake phrase
          // (dictating, or within the active-conversation window).
          dictatingRef.current = true
          setConversationActive(true)
          if (res.isFinal) {
            const full = (committedTranscriptRef.current + ' ' + text).trim()
            committedTranscriptRef.current = full
            chainingRef.current = false
            setState((s) => ({ ...s, transcript: full, dictating: true }))
            if (full) onCommand(full)
            committedTranscriptRef.current = ''
            dictatingRef.current = mode === 'ptt' // wake mode drops back to "waiting for follow-up" (grace window), ptt stays held
            setState((s) => ({ ...s, transcript: '', dictating: mode === 'ptt' }))
          } else {
            const live = (committedTranscriptRef.current + ' ' + text).trim()
            setState((s) => ({ ...s, transcript: live, dictating: true }))
          }
        }
      }

      r.onerror = (e: SpeechRecognitionErrorEvent) => {
        if (e.error === 'no-speech' || e.error === 'aborted') return
        setState((s) => ({ ...s, error: e.error }))
      }

      r.onend = () => {
        const wantsRestart = mode === 'wake' ? wantWakeRef.current : chainingRef.current || dictatingRef.current
        const sinceLastResult = performance.now() - lastResultAtRef.current
        const midUtterance = mode === 'ptt' && dictatingRef.current && sinceLastResult < RESTART_GRACE_MS

        if (mode === 'wake' && wantWakeRef.current) {
          // Background wake-listening session ended (browser's own
          // duration cap, or a wake word was just consumed above) —
          // always resume it; recognized transcript state is unaffected.
          try {
            r.start()
          } catch {
            /* already starting — ignore */
          }
        } else if (mode === 'ptt' && midUtterance) {
          // Priority 14 — this looks like a browser-imposed cutoff
          // mid-sentence (result arrived just before 'end'), not the
          // user actually pausing. Chain a fresh session transparently
          // instead of ending the turn.
          chainingRef.current = true
          try {
            r.start()
          } catch {
            /* ignore double-start */
          }
        } else if (mode === 'ptt') {
          committedTranscriptRef.current = ''
          chainingRef.current = false
          setState((s) => ({ ...s, dictating: false, transcript: '' }))
        }
        void wantsRestart
      }

      return r
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [Ctor, wakePhrases, onCommand, setConversationActive, state.conversationActive],
  )

  const toggleWakeListening = useCallback(() => {
    if (!Ctor) return
    if (state.wakeListening) {
      wantWakeRef.current = false
      dictatingRef.current = false
      recogRef.current?.stop()
      recogRef.current = null
      modeRef.current = null
      stopMeter()
      setConversationActive(false)
      setState((s) => ({ ...s, wakeListening: false, dictating: false, transcript: '' }))
    } else {
      wantWakeRef.current = true
      modeRef.current = 'wake'
      const r = buildRecognition('wake')
      recogRef.current = r
      r?.start()
      startMeter()
      setState((s) => ({ ...s, wakeListening: true, error: null }))
    }
  }, [Ctor, state.wakeListening, buildRecognition, startMeter, stopMeter, setConversationActive])

  const startPushToTalk = useCallback(() => {
    if (!Ctor) return
    // Push-to-talk takes priority — pause wake listening while held.
    if (state.wakeListening) {
      wantWakeRef.current = false
      recogRef.current?.stop()
    }
    modeRef.current = 'ptt'
    dictatingRef.current = true
    committedTranscriptRef.current = ''
    chainingRef.current = false
    lastResultAtRef.current = performance.now()
    const r = buildRecognition('ptt')
    recogRef.current = r
    try {
      r?.start()
    } catch {
      /* ignore double-start */
    }
    if (!streamRef.current) startMeter()
    setState((s) => ({ ...s, dictating: true, error: null }))
  }, [Ctor, state.wakeListening, buildRecognition, startMeter])

  const stopPushToTalk = useCallback(() => {
    chainingRef.current = false
    recogRef.current?.stop()
    if (state.wakeListening) {
      // resume background wake-word listening
      wantWakeRef.current = true
      modeRef.current = 'wake'
      const r = buildRecognition('wake')
      recogRef.current = r
      try {
        r?.start()
      } catch {
        /* ignore */
      }
    } else {
      stopMeter()
    }
  }, [state.wakeListening, buildRecognition, stopMeter])

  // ── Text-to-speech ──────────────────────────────────────────────
  const speak = useCallback(
    (text: string, onEnd?: () => void) => {
      if (typeof window === 'undefined' || !window.speechSynthesis) {
        onEnd?.()
        return
      }

      const wasWakeListening = wantWakeRef.current
      if (wasWakeListening) {
        wantWakeRef.current = false
        recogRef.current?.stop()
        recogRef.current = null
      }

      window.speechSynthesis.cancel()
      const utter = new SpeechSynthesisUtterance(text)
      utter.rate = 1.02
      utter.lang = languageRef.current === 'kn' ? 'kn-IN' : 'en-US'
      utter.onstart = () => {
        speakingRef.current = true
        setState((s) => ({ ...s, speaking: true }))
      }
      const resumeAndFinish = () => {
        speakingRef.current = false
        setState((s) => ({ ...s, speaking: false }))
        if (wasWakeListening) {
          wantWakeRef.current = true
          modeRef.current = 'wake'
          const r = buildRecognition('wake')
          recogRef.current = r
          try {
            r?.start()
          } catch {
            /* ignore */
          }
        }
        onEnd?.()
      }
      utter.onend = resumeAndFinish
      utter.onerror = resumeAndFinish
      window.speechSynthesis.speak(utter)
    },
    [buildRecognition],
  )

  // Priority 16 — progressive/streaming speech. Tracks how much of the
  // growing `text` has already been queued for speech and only speaks
  // the newly-completed sentence(s) each call, so narration starts
  // while the response is still generating instead of waiting for it
  // to finish. Multiple SpeechSynthesisUtterance calls queue and play
  // in order natively, which is what gives the "streaming" effect
  // without needing a streaming audio codec.
  const spokenUpToRef = useRef(0)
  const speakStream = useCallback(
    (text: string, done: boolean) => {
      if (typeof window === 'undefined' || !window.speechSynthesis) return
      const unspoken = text.slice(spokenUpToRef.current)
      if (!unspoken) return

      const [sentences, remainder] = splitCompleteSentences(unspoken)
      const toSpeak = done && remainder ? [...sentences, remainder] : sentences
      if (toSpeak.length === 0) return

      spokenUpToRef.current = text.length - (done ? 0 : remainder.length)

      for (const sentence of toSpeak) {
        const utter = new SpeechSynthesisUtterance(sentence)
        utter.rate = 1.02
        utter.lang = languageRef.current === 'kn' ? 'kn-IN' : 'en-US'
        utter.onstart = () => {
          speakingRef.current = true
          setState((s) => ({ ...s, speaking: true }))
        }
        const finish = () => {
          speakingRef.current = false
          setState((s) => ({ ...s, speaking: false }))
        }
        utter.onend = finish
        utter.onerror = finish
        window.speechSynthesis.speak(utter)
      }
    },
    [],
  )

  const resetSpeakStream = useCallback(() => {
    spokenUpToRef.current = 0
  }, [])

  const cancelSpeech = useCallback(() => {
    window.speechSynthesis?.cancel()
    speakingRef.current = false
    setState((s) => ({ ...s, speaking: false }))
  }, [])

  const getAnalyser = useCallback(() => analyserRef.current, [])

  useEffect(
    () => () => {
      wantWakeRef.current = false
      recogRef.current?.stop()
      stopMeter()
      window.speechSynthesis?.cancel()
      if (conversationTimerRef.current) clearTimeout(conversationTimerRef.current)
      if (restartTimerRef.current) clearTimeout(restartTimerRef.current)
    },
    [stopMeter],
  )

  const actions: VoiceActions = {
    toggleWakeListening,
    startPushToTalk,
    stopPushToTalk,
    speak,
    speakStream,
    resetSpeakStream,
    cancelSpeech,
    getAnalyser,
  }
  return { state, actions }
}
