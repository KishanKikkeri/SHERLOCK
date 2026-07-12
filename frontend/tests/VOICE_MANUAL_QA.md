# SHERLOCK Voice — Manual QA Checklist (checklist item 9)

Web Speech API (`SpeechRecognition` / `SpeechSynthesis`) needs a real
browser with mic permission and an actual microphone — none of which
exist in this sandbox — so this couldn't be exercised automatically.
`parseVoiceCommand()`'s pure logic IS covered by automated tests
(`src/lib/__tests__/voice-commands.test.ts`); everything below wraps
that logic in real browser/mic behavior and needs a human pass.

Grounded in what `hooks/useVoice.ts` actually implements — check off
against that file if behavior seems off, rather than assuming a bug.

## Browser support (per the file's own support note)
- [ ] Chrome: wake word + push-to-talk + TTS all work
- [ ] Edge: same
- [ ] Safari 16+: same (older Safari has no SpeechRecognition — confirm the `supported` flag correctly disables voice UI, not just fails silently)
- [ ] Firefox: `supported` is false; UI cleanly degrades to text-only input (no dead mic button, no console errors)

## Permissions
- [ ] First-time mic permission prompt appears when enabling wake listening or push-to-talk
- [ ] Denying permission surfaces a real error in `state.error`, not a silent no-op
- [ ] Revoking permission mid-session (browser site settings) is handled — does the wake listener try to restart in a loop?

## Wake word
- [ ] Saying "sherlock" (`DEFAULT_WAKE_WORD`) while `wakeListening` is on starts dictation
- [ ] Wake listener survives a long idle period (30+ min) without silently dying — Chrome's SpeechRecognition is known to auto-stop after ~60s of silence; confirm `useVoice.ts` restarts it (checklist calls this out explicitly: "wake listener recovery")
- [ ] Backgrounding the browser tab and returning doesn't leave wake listening in a stuck "on" state that isn't actually listening

## Push-to-talk
- [ ] Holding the button captures audio only while held; releasing stops cleanly
- [ ] Rapid press/release (spam-clicking) doesn't throw or leave two overlapping recognition sessions running — worth checking directly against the code: does `startPushToTalk`/`stopPushToTalk` guard against being called while a session is already active?

## Confidence gating / noise (MIN_CONFIDENCE = 0.35)
- [ ] Mumbled/quiet speech below the confidence threshold is treated as noise, not misfired as a command
- [ ] Background noise (TV, other conversation) doesn't spuriously trigger the wake word
- [ ] VU meter visibly tracks actual mic input level (speak louder → bar moves)

## Command confirmation
- [ ] Recognized commands (add sticky, undo, zoom in, etc.) give some visible/audible confirmation before executing, per checklist "command confirmation" — confirm what the actual UX is (toast? spoken confirmation via `speak()`? none?) and whether that's sufficient for something destructive like "undo"

## TTS / auto-speak / interruption
- [ ] `speak()` reads investigation narratives aloud when auto-speak is on
- [ ] Starting a new command while TTS is speaking correctly interrupts it (`cancelSpeech`) rather than queuing/overlapping
- [ ] `speaking` state correctly reflects actual audio playback, not just "TTS was told to start"

## Feedback-loop prevention
- [ ] TTS audio played through speakers is NOT picked back up by the mic and misinterpreted as a new command/wake word (a real risk if wake listening stays on during `speak()` — confirm `useVoice.ts` pauses recognition while speaking, or that echo cancellation is relied on and actually works on your test hardware)

## Cross-cutting
- [ ] All of the above repeated at least once on a laptop with built-in mic/speakers (worst case for feedback loops), not just with headphones
