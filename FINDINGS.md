# SHERLOCK v1.0 — Stabilization Pass: Findings Report
Generated during a broad, flag-over-fix pass across backend + frontend-v2.
Repo: KishanKikkeri/SHERLOCK (backend) + your uploaded `frontend-v2` (frontend).

**How to read this:** every item below was actually verified against the real
code/build/tests in this session — not inferred from the handover doc's wishlist.
Where I couldn't verify something myself (needs a browser, mic, live Neo4j, or
Anthropic credits), I wrote an automated test/script you can run, and said so.

**Already fixed (not just flagged)** — these were crash-level bugs blocking
everything else, so I fixed them before doing the broad pass:
- `backend/requirements.txt` was missing `networkx` and `reportlab`, both of
  which are imported directly by backend code (`backend/graph/*`,
  `backend/reporting/pdf_export.py`). A fresh `pip install -r requirements.txt`
  followed by starting the app would crash with `ModuleNotFoundError` on
  either the first graph call or the first PDF export. Verified fixed: fresh
  venv install → `import backend.app.server` succeeds.
- Removed `chromadb` and `langchain-anthropic` from requirements.txt — neither
  is imported anywhere in the codebase (agents call the `anthropic` SDK
  directly). Dead weight, slower installs, larger attack surface for no gain.

---

## 1. Backend Review
- **No `logging` module used anywhere** in the entire backend (0 of 47 .py
  files import `logging`). A handful of scripts use bare `print()`
  (`builder_neo4j.py`, `server.py`, dataset scripts) but the FastAPI app
  itself has no structured logging at all. Concretely: the WebSocket
  handler's `except Exception as e` in `app/main.py` only sends the error
  back to the client — it's never logged server-side, so a production
  incident leaves zero server-side trace.
- `backend/schemas/` is an empty `__init__.py` stub. `pydantic` is listed as
  a dependency but never actually used for request/response validation —
  `/export/pdf` takes `payload: dict = Body(...)` with no schema at all, so
  malformed input fails somewhere inside `pdf_export.py` with whatever error
  that code happens to raise, not a clean 422.
- `datasets/generate_synthetic_data.py` only exposes a CLI `main()` behind
  `argparse` — no importable function, so anything (including this pass's
  own test fixtures) that wants a dataset in-process has to shell out to it
  as a subprocess. Fine for a one-off script; worth a proper function
  signature if this becomes something other code depends on.
- Positive finding: dependency management is otherwise clean — every other
  import in the codebase resolves to something declared in requirements.txt.

## 2. LangGraph Pipeline
- Verified end-to-end with real runs (no mocking) via
  `backend/tests/test_orchestrator_pipeline.py`: the full
  chief_plan → crime_records → network_analysis → financial_agent →
  pattern_analysis → prevention_agent → evidence_validation → chief_synthesis
  chain completes cleanly, produces a non-empty final report even for a
  "no matching data" query, and is deterministic given the same seeded
  dataset (no accidental nondeterminism from unsorted dict/set iteration).
- Confirmed the `ANTHROPIC_API_KEY`-unset degrade path in `ChiefAgent`
  (falls back to a deterministic template narrative) actually works — this
  is the exact situation a fresh clone / CI runner will be in, and it's
  solid.
- WebSocket completion events verified in `backend/tests/test_websocket.py`:
  every investigation reaches `report_ready` (or a clean `error` event,
  never a hang), `agent_completed`/`agent_skipped` events carry the
  `new_findings`/`validated_findings` payload shape the frontend expects.
- Minor dead protocol surface: `EventType.AGENT_STARTED`,
  `FINDING_PRODUCED`, and `VALIDATION_COMPLETE` are defined in
  `backend/api/events.py` but never emitted by `investigation_stream.py`,
  and never referenced anywhere in the frontend either. Either wire them up
  or drop them — right now they're just unused enum members on both ends.

## 3. Agent Review
- All 7 agents that actually exist (Chief, Crime Records, Network Analysis,
  Financial, Pattern Analysis, Prevention, Evidence Validation) are wired
  into the graph and exercised by the pipeline tests above.
- "Forecasting" and "Timeline" from the handover doc's checklist aren't
  missing agents — they're capabilities folded into Pattern Analysis /
  Chief respectively (`hotspot_forecast` is emitted by Pattern Analysis when
  `wants_forecast=True`), and `docs/FEATURE_MAPPING.md` describes this
  accurately. Not a bug.
- **Real doc/code mismatch:** `docs/ARCHITECTURE.md` explicitly describes an
  "Entity Resolution" agent/capability (`person_aliases` exists "specifically
  for Entity Resolution... so the resolution agent's accuracy can be
  scored") — but no entity-resolution agent, module, or scoring logic exists
  anywhere in `backend/agents/`. Either the doc is describing a roadmap item
  as if it's implemented, or there's a missing agent. Worth resolving one
  way or the other before a demo, since a judge reading ARCHITECTURE.md
  would reasonably expect to see it work.
- "Similar Case" (from the handover checklist) doesn't appear in the agents
  directory OR in the docs — likely a roadmap item that made it into the
  stabilization checklist prematurely. Confirm before assuming it's a gap.

## 4. Database
- Schema/FK relationships are consistent and correctly typed (verified by
  successfully generating and querying a synthetic dataset through 21
  passing tests).
- **No indexes on any foreign key column** anywhere in
  `backend/database/models.py` (`person_id`, `crime_id`, `owner_id`,
  `sender_account_id`, `receiver_account_id`, etc. — zero `index=True`
  usages in the whole file). Doesn't matter at demo scale (SQLite scans a
  few hundred rows in milliseconds — see the performance numbers below),
  but matters a lot the moment this points at Postgres with real data
  volume, especially since every graph rebuild joins across exactly these
  columns.

## 5. Graph Layer
- NetworkX backend verified via `backend/tests/test_graph_service.py`:
  `find_repeat_offenders` ordering, `min_crimes` threshold filtering,
  `find_associates` shape (and that a person is never their own associate),
  `find_connection` (trivial same-person case, and the unreachable-pair
  case degrades to `found: False` instead of raising), `find_location_clusters`
  ordering — all real assertions against real data, all passing.
- Neo4j backend (`service_neo4j.py`) implements the same interface but I
  couldn't exercise it — no Neo4j instance running in this sandbox. Wrote
  `backend/scripts/stress_test_graph.py` so you can run the same shape of
  checks against Neo4j once `docker-compose up` is running, and compare
  timing directly against NetworkX on the same dataset size (see
  Performance section below for what I actually measured with NetworkX).

## 6. API
- All 4 non-websocket endpoints verified with real requests in
  `backend/tests/test_api.py`: `/health`, `/metrics` (correct shape, nonzero
  counts), `/graph/{person_id}` (known person returns a populated ego-graph,
  unknown person returns an empty-but-200 graph rather than a 500),
  `/export/pdf` (returns an actual `%PDF`-prefixed byte stream).
- **Found and confirmed:** `/graph/{person_id}` and `/metrics` both
  hardcode `get_graph_service(backend="networkx", ...)`, ignoring the
  `GRAPH_BACKEND` env var that `/ws/investigate` (via
  `investigation_stream.py`) also hardcodes to `"networkx"` independently.
  So setting `GRAPH_BACKEND=neo4j` in production would silently have zero
  effect on any of the three call sites — they'd all keep using NetworkX
  regardless. If Neo4j is meant to be a real production path, this needs
  fixing in three places, not one.
- `person_id` in `/graph/{person_id}` has no `ge=0` constraint — negative
  IDs pass FastAPI's int validation and just fall through to "not found",
  which isn't a crash but is a slightly misleading 200-with-empty-graph
  instead of a clean 422. Documented as a test in `test_api.py`.
- No Pydantic request model on `/export/pdf` (see item 1).

## 7. Frontend
- `frontend-v2` builds clean: `tsc` (full project type-check) and
  `vite build` both pass with zero errors or warnings.
- Zero `: any` usages anywhere in the TypeScript — genuinely strict.
- Zero leftover `console.log`/`console.error` debug statements.
- Accessibility attributes (`aria-*`/`role=`) present in 21 of 23
  components; the two without any are `BoardToolbar.tsx` and
  `WorkspaceLayout.tsx` — worth a pass, though toolbar buttons do have
  visible text labels which screen readers can still use.
- Global `:focus-visible` styling exists in `styles/tokens.css` with a
  proper color token — keyboard focus indication is handled, not missing.
- `prefers-reduced-motion` is handled in `styles/tokens.css`.
- **No React Error Boundary anywhere in the component tree** (`App.tsx`
  renders `LandingScreen` / `WorkspaceLayout` / `InvestigationBoard`
  directly, no wrapping boundary). A runtime exception in any child
  component — the board, the graph panel, voice, anything — currently
  white-screens the whole app with no fallback UI and no way to recover
  short of a manual reload. Given this is meant to be demoed live to
  judges, this is the single highest-value frontend fix on this list.
- No XSS-risk patterns found (`dangerouslySetInnerHTML`, `eval`, raw
  `innerHTML`) — clean on that front.

## 8. Investigation Board
- Wrote `frontend-v2/tests/e2e/board-stress.spec.ts` (Playwright) — adds
  300 sticky notes through the real toolbar button (not a store shortcut),
  times whether add-latency grows with card count, then exercises
  auto-layout/undo/redo/reset-view/pan/zoom/presentation-mode against the
  populated board and asserts no uncaught page errors. **Not run here** — no
  browser/display in this sandbox. Run it yourself per the instructions at
  the top of the file.
- **Testability gap found while writing that script:** none of the board
  components (`InvestigationBoard.tsx`, `BoardToolbar.tsx`) expose
  `data-testid` attributes, so the script has to fall back to visible
  button text and CSS-module class-prefix selectors, which are more
  fragile than test-ids. Worth adding before this becomes a real CI
  suite — I noted exactly where in the script's comments.
- `useBoard.ts` (undo/redo/snapshot state) is 205 lines of inline
  `useState` logic with no exported pure reducer — meaning undo/redo
  correctness can only be tested by actually rendering the hook (or the
  Playwright route above), not with fast, isolated unit tests. Consider
  extracting the state machine into a pure `(state, action) => state`
  reducer purely for testability; not required for it to work correctly.

## 9. Voice
- The parsing layer (`lib/voice-commands.ts`) IS unit-tested now:
  `frontend-v2/src/lib/__tests__/voice-commands.test.ts`, 12 tests, all
  passing, covering every command type plus the present/exit_presentation
  ordering the handover doc specifically calls out.
- **Real bug found and confirmed by a failing-documented test:** the
  `exit_presentation` regex is
  `/\bstop present|exit present|end present\b/`. Because `\b` only binds
  to the alternative it's directly attached to in a regex, the middle
  alternative `exit present` has **no word boundary on either side**.
  Confirmed with a live test: the phrase `"please dont exit presentmania
  now"` matches and is misclassified as `exit_presentation`, purely
  because it contains the literal substring "exit present" inside a
  longer word. Intended fix is something like
  `/\b(stop|exit|end) presenting?\b/`. Left unfixed per "flag over fix" —
  the test documents current behavior explicitly as a bug, not a spec.
- Everything downstream of parsing (`hooks/useVoice.ts`: wake word,
  push-to-talk, mic permissions, TTS, feedback-loop prevention, browser
  support) needs a real mic/browser I don't have here. Wrote
  `frontend-v2/tests/VOICE_MANUAL_QA.md` — a checklist grounded in what
  the actual code does (e.g. it specifically calls out Chrome's known
  ~60s SpeechRecognition auto-stop and asks you to confirm
  `useVoice.ts` actually recovers from it, since "wake listener recovery"
  is explicitly named in the original checklist).

## 10. Graph Visualization
- Covered by the same Playwright script (item 8) for pan/zoom/drag
  responsiveness — the board and graph-vis panel share the same canvas
  interaction model in this codebase. Not separately re-tested.

## 11. Performance
- **Measured, not estimated:** with a 300-person / 600-crime synthetic
  dataset, building the NetworkX graph from the SQL database takes
  ~440ms, and `find_connection` (shortest path) takes ~38ms median. Full
  numbers below (from `backend/scripts/stress_test_graph.py`, actually
  executed this session):

  | Operation | median |
  |---|---|
  | graph build/connect | 442 ms |
  | find_repeat_offenders | 2.5 ms |
  | find_associates | 0.01 ms |
  | find_location_clusters | 2.4 ms |
  | get_metrics | 2.6 ms |
  | find_connection (max_hops=6) | 38 ms |

- The important number is the **440ms graph build**, because — per the
  item 6 finding — `/metrics`, `/graph/{person_id}`, and every single
  `/ws/investigate` call all independently rebuild the entire in-memory
  NetworkX graph from scratch, with no caching between requests. At this
  dataset size that's a ~450ms tax before any actual query runs, on
  *every* request. This will get materially worse as the dataset grows —
  worth either caching the built graph between requests (invalidated on
  writes) or moving to the Neo4j backend for anything beyond demo scale.
- Re-run `stress_test_graph.py` with `GRAPH_BACKEND=neo4j` once
  `docker-compose up` is running, and with a larger dataset
  (`--persons 5000 --crimes 20000`), to see where NetworkX actually stops
  being viable — I didn't have Neo4j available to measure that side
  myself.

## 12. Accessibility
- See item 7: aria coverage is good (21/23 components), focus-visible
  styling and reduced-motion support both exist globally. Two components
  (`BoardToolbar.tsx`, `WorkspaceLayout.tsx`) have no aria attributes at
  all — worth a manual screen-reader pass on those two specifically.

## 13. Security Review
- CORS is wide open (`allow_origins=["*"]`, `allow_methods=["*"]`,
  `allow_headers=["*"]`) with a comment acknowledging it
  ("tighten in production; open for hackathon dev") — so the team already
  knows, it just hasn't been done. Flagging since "prepare the project"
  for production is explicitly in scope.
- **No `.env.example` anywhere in the repo**, despite the backend reading
  `DATABASE_URL`, `GRAPH_BACKEND`, `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`,
  and `ANTHROPIC_API_KEY`, and the frontend reading `VITE_API_URL`. A new
  contributor has to grep the source to discover any of these.
  `NEO4J_PASSWORD` defaults to the literal string `"sherlock123"` if unset
  — fine for local dev (matches docker-compose's own dev credentials), but
  worth a loud comment or a hard failure in a real prod config rather than
  a silent fallback.
- **Zero authentication/authorization code exists anywhere** — no JWT
  handling, no auth middleware, no user model, nothing. The handover doc
  explicitly says "no production auth implementation required... only
  prepare the project" — right now there's literally nothing prepared,
  not even a stubbed dependency-injection hook for where auth would plug
  in later. Worth at least a `get_current_user` stub that's a no-op today,
  so wiring in real auth later doesn't require touching every endpoint.
- No hardcoded real secrets found anywhere (grepped for
  `password = "..."` literals outside of the known dev-default cases
  above).

## 14. Documentation
- `README.md`, `docs/ARCHITECTURE.md`, `docs/FEATURE_MAPPING.md`,
  `docs/API_REFERENCE.md`, `docs/FUTURE_ROADMAP.md`, `docs/AGENT_DESIGN.md`,
  `docs/DATA_MODEL.md`, `docs/GRAPH_SCHEMA.md`, `docs/SYSTEM_DESIGN.md`,
  `docs/PERFORMANCE_REPORT.md`, `docs/VALIDATION_REPORT.md` all exist and
  are UTF-8.
- **Concrete bug: `README.md` at the repo root is saved as UTF-16LE with
  CRLF line endings** — every other markdown file in the repo (including
  `frontend/README.md`) is plain UTF-8. This is very likely to render as
  garbled text or a "binary file" warning on some viewers/tools (GitHub
  itself usually handles it, but any local tooling, `grep`, static site
  generator, or CI step that assumes UTF-8 will choke on it — it broke a
  plain `grep` in this session). Trivial fix: re-save as UTF-8. Flagging
  rather than fixing since you asked for a flag-over-fix pass.
- No dedicated "Demo Guide," "Judge QA," "Developer Guide," "Installation
  Guide," or "Deployment Guide" docs exist as named files — the closest
  equivalents are spread across README.md and the docs/ files above.
  Whether that's a real gap depends on what the README already covers;
  worth a quick read-through against the handover checklist's exact list.

## 15. Testing
Before this pass: **zero automated tests existed anywhere in the repo**
(no `pytest`, no `conftest.py`, no frontend test runner configured — only
two manual demo scripts, `demo_investigation.py` and
`demo_graph_queries.py`, meant to be read, not asserted against).

Added this session, all actually run and passing:
- `backend/tests/` — 21 pytest tests (`test_api.py`, `test_graph_service.py`,
  `test_orchestrator_pipeline.py`, `test_websocket.py`) plus
  `conftest.py` (isolated temp-SQLite dataset per session, zero external
  services required). Run with:
  `pip install -r backend/requirements-dev.txt && pytest backend/tests/`
- `frontend-v2/src/lib/__tests__/voice-commands.test.ts` — 12 vitest tests
  for the voice command parser. Run with `npm test`.
- `frontend-v2/tests/e2e/board-stress.spec.ts` — Playwright stress test
  for the board (needs a real browser — not run in this sandbox, see
  in-file instructions).
- `backend/scripts/stress_test_graph.py` — graph performance script
  (actually run against NetworkX this session; rerun with
  `GRAPH_BACKEND=neo4j` once you have Neo4j up).
- `frontend-v2/tests/VOICE_MANUAL_QA.md` — grounded manual QA checklist
  for the mic/browser-dependent parts of voice.

Not covered: unit tests for individual agent classes in isolation (only
tested via the full pipeline), Neo4j-backend graph tests, and any load
test beyond the 300-card board / 300-person graph scale used here.

## 16. Production Readiness
- `docker/docker-compose.yml` only defines Postgres + Neo4j infra
  containers — **there's no Dockerfile for the backend or frontend
  themselves**, so "docker-compose up" alone doesn't get you a running
  SHERLOCK app, just its two datastores.
- No `.env.example` (see item 13).
- No health-check-based container orchestration is possible yet since
  there's no app Dockerfile, though the `/health` endpoint itself exists
  and works and would slot in fine once one exists.
- No CI config (`.github/workflows/`, etc.) exists to actually run the new
  test suite automatically — worth adding now that there's something to run.

---

## Suggested priority order (given everything above)
1. Add a React Error Boundary — highest risk-to-effort ratio for a live
   demo (item 7).
2. Fix the three hardcoded `backend="networkx"` call sites, or explicitly
   document that `GRAPH_BACKEND` is currently a no-op (item 6/11).
3. Add `.env.example` for both backend and frontend-v2 (item 13/16).
4. Fix the `exit_presentation` regex bug (item 9) — small, well-understood,
   test already documents the exact fix needed.
5. Re-save `README.md` as UTF-8 (item 14) — trivial.
6. Everything else in this report, roughly in the order it's listed above.
