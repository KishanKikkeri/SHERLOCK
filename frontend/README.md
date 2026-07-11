# SHERLOCK Command Center — Frontend v2

A ground-up redesign per the Product Design Specification: "Operating System for Investigators" — Palantir Gotham meets Linear meets Apple HIG. Not a dashboard. Not cyberpunk. Precision, restraint, intelligence-first.

## Status

- **Type-checked:** `npx tsc --noEmit` → 0 errors
- **Production build:** `npx vite build` → succeeds, 615 modules, ~95KB gzipped JS
- **Not yet runtime-verified in a browser** — do this before demo day (see below)

## Stack

React 18 + TypeScript (strict) + Vite + D3 (graph only, lazy-loaded) + CSS Modules with a hand-built design token system (no Tailwind — tokens are defined once in `src/styles/tokens.css` and consumed via `var()`).

## Run it

```bash
cd frontend-v2
npm install
npm run dev          # http://localhost:5173, proxies /ws and /api to localhost:8000
```

Requires the SHERLOCK backend running on port 8000 (see root `backend/` README). Set `VITE_API_URL` if your backend isn't on localhost:8000.

```bash
npm run build         # production build → dist/
npm run preview       # serve the production build locally
```

## What was implemented from the spec

**Landing screen** — near-empty, SHERLOCK wordmark, single search input, 3 suggested queries, auto-focus on mount, subtle dot-grid background, "evidence-backed" badge pinned bottom.

**Investigation workspace** — three-column layout (timeline / graph / findings) + pinned bottom console, exactly per the wireframe. No sidebar nav, no tabs, single screen.

**Investigation Timeline** (left) — vertical step list with connector lines, live status icons (pending/running/complete/skipped), progress bar, elapsed-time counter. No spinners — the running state uses a rotating ring icon + animated ellipsis, matching "never use loading spinners, communicate progress."

**Intelligence Graph** (center) — D3 force-directed graph with animated node entrance (staggered radius transition, not instant dump), drag, zoom/pan, entity-type colour coding, hover state, legend. Lazy-imports D3 so it doesn't block initial paint.

**Detective Notes** (right) — findings rendered as expandable notes (not generic cards): type, confidence badge, validated/rejected tag, summary, and an expand-to-reveal evidence + agent source trail — matching the "Finding → Evidence → Reasoning Path → Confidence → Source" explainability requirement.

**Recommended Operational Actions** (right) — prevention findings get their own labelled section with a left amber accent border, distinct from analytical findings.

**Natural Language Console** (bottom) — pinned, supports query history via ↑/↓, global `/` keyboard shortcut to focus, Enter to submit, visually distinct running state.

**PDF Export** — appears only after `status === 'complete'`, calls the existing `/export/pdf` backend endpoint, downloads via blob.

**Metrics** — subtle pill cluster in the header (not a dominant strip), persons/crimes/edges/repeat-offenders only, exactly the "never dominate the UI" instruction.

## Design tokens

All colours, spacing, typography, and motion durations are defined once in `src/styles/tokens.css` as CSS custom properties — exactly matching the PDS colour palette (`#0B1220` base, `#38BDF8` accent, Inter typeface, 4px spacing grid). No component hardcodes a colour or spacing value.

## What's intentionally not yet done

Per the PDS's own phased process (research → IA → wireframes → hi-fi → **design system** → **implementation** → polish → usability review), this delivers through the implementation stage. Not yet built:

- Framer Motion (current animations are CSS transitions/keyframes — functionally equivalent for this scope, but the spec named Framer Motion specifically; swap-in is straightforward since all motion is already isolated to token-driven durations/easings)
- shadcn/ui components (no component needed one yet — buttons/inputs are hand-built to match tokens exactly)
- TanStack Query (single WebSocket-driven data flow didn't need it; would matter more with more REST polling)
- React Hook Form (only one freeform text input exists; not enough form complexity to justify it yet)
- Keyboard navigation audit, screen-reader label pass, contrast audit (basic `aria-label`s are in place throughout, but a full accessibility review is outlined as Step 7 of the spec's process and hasn't been run)
- The graph's "node clustering" and "relationship highlighting on selection" — base graph is built; clustering and click-to-highlight are the natural next layer

## Phase 3 — Investigation Board (Digital War Room)

Added under `src/components/board/` + `src/hooks/useBoard.ts` + `src/lib/board-types.ts`. Reachable via a new **Board** button in the workspace header; renders as its own top-level app mode (`App.tsx` now has `landing | workspace | board`), separate from the three-column workspace.

**Built:**

- **Infinite canvas** — CSS-transform pan (drag empty background) + wheel zoom (0.3×–2.5×), dot-grid background matching the existing token-driven aesthetic.
- **Cards** — three kinds (`evidence`, `note`, `hypothesis`) in one component. Evidence cards inherit entity-type colour coding from the same palette as the Intelligence Graph. Hypothesis cards carry a confidence slider. Sticky notes have a 6-colour swatch picker.
- **Drag & drop, manual linking, edit/delete links** — click-to-link mode (click card A, then card B); links render as an SVG overlay in the same transformed coordinate space as the cards so they track pan/zoom without recomputation; click a link to select and remove it.
- **"Add from findings"** — pulls any `AgentFinding` from the live investigation straight onto the board as an evidence card, preserving `confidence` and a back-reference to the source finding.
- **Undo/redo** — history stack over structural edits (add/delete card, add/delete link, text edits). Card drags only commit one history entry on release, not per-frame.
- **Snapshots (version history)** — named, timestamped, persisted to `localStorage` (this is a real browser app, not a Claude artifact, so `localStorage` is appropriate here); save/restore/delete from the toolbar.
- **Auto-layout** — force-directed re-layout via the same lazy-loaded `d3-force` pattern as the Intelligence Graph, run headless (no visible simulation tick) and committed as one history entry.
- **Presentation mode** — pin cards for the sequence, then step through them one at a time with the toolbar hidden and non-pinned cards dimmed to 15% opacity; the view auto-centers/zooms on each pinned card.

**Deliberately deferred — the "AI-Assisted Board" half of Phase 3:**

Suggested relationships, missing-evidence detection, hidden-connection discovery, hypothesis confidence scoring *by the model*, evidence-contradiction detection, and investigation replay all require new backend/agent endpoints (there's nothing in `api.ts` for any of these yet). The board's data model (`BoardCard`, `BoardLink`) is shaped so these can slot in later as suggestion overlays without a rework — e.g. a suggested link can reuse `BoardLink` with a `confidence` field, or a suggested card can be rendered as a `BoardCard` with a distinct "suggested" style before the user accepts it. Wiring this up is the natural next slice, once the corresponding agent/endpoint exists.

**Not yet done within the built scope:**

- No visual regression test in an actual browser — type-checked and build-verified in this sandbox, same caveat as the rest of this repo.
- No keyboard-only path for linking/deleting cards (mouse/pointer only right now).
- No multi-select / marquee-select of cards.

## Phase 4 — Conversational Investigation

New: `src/hooks/useVoice.ts`, `src/hooks/useTextToSpeech.ts`, `src/lib/voice-commands.ts`, `src/lib/speech-types.d.ts`, `src/components/board/VoiceIndicator.tsx`. Extends `NLConsole.tsx` and `FindingsPanel.tsx`. No new backend calls — everything here runs client-side against the browser's native Web Speech API.

**Voice Interface (built):**

- **Wake word** — toggle "listening for 'Sherlock'" in the console and on the board; continuous recognition, auto-restarts itself if the browser's own silence-timeout ends the session.
- **Push-to-talk** — hold the 🎙 button, speak, release; works independently of wake-word listening (pauses it, then resumes it on release if it was on).
- **Speech-to-text** — via `SpeechRecognition`/`webkitSpeechRecognition`. Feature-detected: on Firefox (no support) the mic buttons don't render and a plain note explains why, rather than silently failing.
- **Text-to-speech** — "Read summary aloud" on the findings panel reads the final report narrative via `SpeechSynthesisUtterance`; fully standard, works everywhere.
- **"Noise filtering" — actual scope:** the Web Speech API gives no raw-audio access, so there's no true denoising hook available from JS. What's implemented is a confidence threshold (results below ~35% confidence are discarded as noise) and debounced interim results. This is worth knowing before claiming "noise filtering" as a checked box in a demo — it filters *low-confidence transcriptions*, not acoustic noise.
- **Voice activity detection — actual scope:** implemented as a real mic-level VU meter (Web Audio API `AnalyserNode`, RMS of the waveform), shown while listening. It's an honest audio-level indicator, not a speech/non-speech classifier — good enough to show the mic is live and picking something up, not a true VAD model.

**Voice-Controlled Board (built):** a fixed vocabulary (`src/lib/voice-commands.ts`) drives every board affordance already built in Phase 3 — add sticky note, add hypothesis, toggle link mode, undo/redo, auto-layout, reset/zoom/pan the view, start/stop presentation, exit the board. Deliberately simple regex/keyword matching rather than an LLM round-trip, since the command set is small and fixed; reliability matters more than flexibility here.

**Conversational reply loop (added after initial Phase 4 build):** originally, voice input just fed the same one-shot query box as typing, with TTS only available via a manual "read aloud" button — a person talking to it still ended in silence and had to go read the screen. Now:
- `useVoice` is lifted to `WorkspaceLayout` (one instance, shared by the console and the findings panel) instead of living privately inside `NLConsole`. A query flagged `viaVoice` gets its result *spoken automatically* once the investigation completes or errors — typed queries still only get the manual button, since someone typing at a desk didn't ask to be talked at.
- The Investigation Board speaks its command confirmations too ("Added a sticky note") instead of only showing a silent toast, through the same `voice.actions.speak`.
- **Echo/feedback-loop fix:** `useVoice.speak()` now pauses wake-word listening for the duration of the utterance and resumes it afterward. Without this, an open mic listening for "Sherlock" could pick up Sherlock's own voice output as a new command, or worse, re-trigger the wake word if it ever appeared in what was being read back. This is handled once, inside the hook, so every caller (console, board) gets it for free rather than each needing to manage mic state around its own `speak()` calls.
- The standalone `useTextToSpeech` hook from the original Phase 4 build was removed — having two independent `SpeechSynthesis` consumers in the same tree risked one silently stepping on the other's `speaking` state, since the browser's synth queue is a single global regardless of which hook instance queued the utterance.

**Conversational AI / AI Discussion Mode — deliberately deferred:**

The roadmap's "multi-turn memory," "clarification dialogue," "AI debates," and "ask specialists directly" all require the *backend* to hold conversation state and orchestrate agent-to-agent dialogue — there's nothing to build on the frontend alone here yet. The current WebSocket protocol (`createInvestigationSocket` in `api.ts`) sends one `{query}` and receives a single pipeline run to `report_ready`; there's no session/thread concept, and `WSEvent`'s `event_type` enum has no slot for a mid-investigation clarifying question or an agent-to-agent message. What's built now is a full spoken *round-trip* (ask → real backend investigation → spoken answer), which is further than plain one-shot parity — but it's still one query in, one answer out, not a back-and-forth dialogue with memory of earlier turns.

If/when the backend adds session memory and a debate/discussion event type, the natural next slice is a chat-thread UI (turns, not one query box) plus a "Discussion" view rendering agent-to-agent messages — both are additive to what's here, not a rework.

## Before demo day

1. `npm run dev` against a live backend and click through both the landing → workspace transition and a real WebSocket investigation end-to-end in an actual browser — this was type-checked and build-verified in this sandbox but not visually rendered.
2. Test at 1440px (the spec's stated minimum width) and one laptop size below it.
3. Run the three official demo queries through the new UI specifically, since the components consume backend event/finding shapes that were validated against the old frontend, not yet against this one live.
