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

## Before demo day

1. `npm run dev` against a live backend and click through both the landing → workspace transition and a real WebSocket investigation end-to-end in an actual browser — this was type-checked and build-verified in this sandbox but not visually rendered.
2. Test at 1440px (the spec's stated minimum width) and one laptop size below it.
3. Run the three official demo queries through the new UI specifically, since the components consume backend event/finding shapes that were validated against the old frontend, not yet against this one live.
