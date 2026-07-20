// Ported from frontend/src/lib/voice-commands.ts (Golden Rule 4).
// Deliberately simple keyword/phrase matching, not full NLU — same
// philosophy as the backend's VoiceCommandRouter (command_router.py):
// a small, fixed vocabulary so this is reliable without a round-trip
// to a language model. This vocabulary is for board-UI actions only
// and never touches the server; investigation-level voice queries go
// through POST /voice/command instead (see voice/VoicePage.tsx).

export type BoardVoiceCommand =
  | { type: 'add_sticky' }
  | { type: 'add_hypothesis' }
  | { type: 'toggle_link_mode' }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'auto_layout' }
  | { type: 'reset_view' }
  | { type: 'zoom'; direction: 'in' | 'out' }
  | { type: 'pan'; direction: 'left' | 'right' | 'up' | 'down' }
  | { type: 'present' }
  | { type: 'exit_presentation' }
  | { type: 'exit_board' }
  | { type: 'unrecognized'; raw: string }

interface Rule {
  pattern: RegExp
  build: () => BoardVoiceCommand
}

const RULES: Rule[] = [
  { pattern: /\b(sticky|note)\b/, build: () => ({ type: 'add_sticky' }) },
  { pattern: /\bhypothes/, build: () => ({ type: 'add_hypothesis' }) },
  { pattern: /\b(link|connect)\b/, build: () => ({ type: 'toggle_link_mode' }) },
  { pattern: /\bundo\b/, build: () => ({ type: 'undo' }) },
  { pattern: /\bredo\b/, build: () => ({ type: 'redo' }) },
  { pattern: /\b(auto.?layout|organi[sz]e|tidy)\b/, build: () => ({ type: 'auto_layout' }) },
  { pattern: /\b(reset|center|fit)\b.*\bview\b|\bzoom to fit\b/, build: () => ({ type: 'reset_view' }) },
  { pattern: /\bzoom in\b/, build: () => ({ type: 'zoom', direction: 'in' }) },
  { pattern: /\bzoom out\b/, build: () => ({ type: 'zoom', direction: 'out' }) },
  { pattern: /\bpan left\b|\bmove left\b/, build: () => ({ type: 'pan', direction: 'left' }) },
  { pattern: /\bpan right\b|\bmove right\b/, build: () => ({ type: 'pan', direction: 'right' }) },
  { pattern: /\bpan up\b|\bmove up\b/, build: () => ({ type: 'pan', direction: 'up' }) },
  { pattern: /\bpan down\b|\bmove down\b/, build: () => ({ type: 'pan', direction: 'down' }) },
  { pattern: /\bstop present|exit present|end present\b/, build: () => ({ type: 'exit_presentation' }) },
  { pattern: /\bpresent(ation)?\b/, build: () => ({ type: 'present' }) },
  { pattern: /\b(exit|leave|close) board\b|\bback to workspace\b/, build: () => ({ type: 'exit_board' }) },
]

export function parseVoiceCommand(raw: string): BoardVoiceCommand {
  const lower = raw.toLowerCase().trim()
  for (const rule of RULES) {
    if (rule.pattern.test(lower)) return rule.build()
  }
  return { type: 'unrecognized', raw }
}
