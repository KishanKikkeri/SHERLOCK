# SHERLOCK — Changelog

All notable changes to this project are documented here, organised by build phase.

---

## Integration Release 4 — v3/v5 Merge: Case-Scoping Restoration

Base: `SHERLOCK-integrated-v5` (the larger, more current archive — already
a clean superset of `SHERLOCK-integrated-v3` on graph search, the
language-context middleware, and the standalone Voice page). One
functional regression found between the two and restored; everything
else in v5 was carried through unchanged.

**Restored — Case Scoping (Priority 5).** Present end-to-end in v3;
silently dropped at every layer somewhere between v3 and v5 (not
superseded by anything — the backend's `InvestigationSession.fir_id`
column and `open_case(fir_id=...)` path were still live in v5, just
nothing left to set it after session creation). Confirmed via a clean,
isolated `diff` against v3 at each layer (no other unrelated change
shared the same hunks), full backend test suite (104/104 passing,
including new coverage below), frontend `tsc -b` typecheck, and a
production `vite build` — all clean.
- `backend/database/service.py` — restored `DatabaseService.update_session_case()`
  and `DatabaseService.list_cases()`.
- `backend/api/sessions.py` — restored `PATCH /sessions/{id}/case`
  (`SetCaseRequest` body: `fir_id: int | None`).
- `backend/api/conversation_chat.py` — restored `GET /conversation/cases`
  (case-selector list, read-only).
- `backend/tests/test_case_scoping.py` — new: exercises both endpoints
  against the seeded synthetic dataset (list, search, set, clear,
  unknown-FIR rejection, unknown-session 404) so this can't silently
  regress again.
- `frontend/src/lib/types.ts` — restored `CaseOption`.
- `frontend/src/lib/queries/conversation.ts` — restored `useCases()` and
  `useSetSessionCase()`.
- `frontend/src/conversation/ConversationSidebar.tsx` — added a "Case
  scope" selector alongside the existing "Attach to session" selector.
  v3's version lived in a since-removed `ConversationToolbar` and
  lazily opened a new session via a `useStartNewConversation` hook that
  no longer exists in v5's session-creation flow; rebuilt to disable
  the selector until a session exists instead, matching how the
  sibling Summarize/Export/Clear controls already behave in v5, rather
  than reintroducing a hook that no longer fits the current
  architecture.

---

## Integration Release 3 — Graph Search, Voice/Conversation Parity, and Project-wide Language Awareness

Five uploads this round; four genuinely mergeable, one deliberately deferred.

**Merged — Graph Search & Navigation (Priority 18-23) + Voice/Conversation
Parity (Priority 14-17).** Source: `SHERLOCK-conversation-voice-graph-v1`,
confirmed to be a strict superset of the standalone
`SHERLOCK-graph-search-v1` patch (byte-identical `search.py`/
`graph_search.py`/tests) plus one additional, well-documented piece.
- `backend/graph/search.py` + `GET /graph/search` — entity detection
  across every identifier type on every query (no upfront classifier;
  pattern-shaped input like a plate or `FIR-YYYY-NNNN` gets boosted to
  an exact match instead), Python-side fuzzy scoring with a noise floor
  (SQL `ILIKE` alone can't match `"ka 01 ab 1234"` against a stored
  `"KA01AB1234"`), and a case-context relevance boost.
- `GET /graph/node/{node_type}/{entity_id}` — generalizes the
  Person-only ego-subgraph endpoint to every node label via an extracted
  `_build_ego_subgraph()` helper; `/graph/{person_id}` kept as the
  unchanged legacy route (verified byte-for-byte identical output to the
  generic route for the same person, live, not just in the test suite).
- `backend/voice/command_router.py`'s `_investigate` now delegates to
  the same `ConversationManager.handle_message()` text uses, instead of
  calling `run_investigation_once` directly — voice gets full intent
  parity with text (a spoken "summarize this" now actually triggers the
  summarize path instead of running as a literal investigation query;
  "clear the conversation" over voice reaches `clear_history`, which the
  old direct-call path had no route to at all). `VoicePage.tsx` and
  `useVoice.ts` (wake-phrase list, session-chaining past the browser
  recognizer's own cutoffs, active-conversation window, barge-in) were
  rewritten to read/write the same `useConversation()`/zustand store the
  Conversation screen uses, instead of a disconnected local `turns`
  array — verified live: a typed turn and a spoken turn on the same
  `session_id` now share one conversation, not two that happen to be
  compared.
- **Stated limitation, carried forward honestly:** actual browser
  microphone/`SpeechRecognition` timing behavior across Chrome/Edge/
  Safari was not verified in either that source tree or here — no audio
  device in either build sandbox. Backend routing and the frontend
  build/typecheck are verified; live mic behavior is not.

**Merged — Project-wide Language Awareness (Priority 24-32).** Source:
`SHERLOCK-integrated-v4` (a strict continuation of `-v3` — same 3 new
files, plus further refinement; `-v3` itself needed no separate merge).
- `backend/language/context.py` — a `ContextVar` + ASGI middleware
  (`LanguageContextMiddleware`, reading the new `X-App-Language` header
  frontend `api-client.ts` now sends on every request) giving every
  AI-generating service one place to ask "what language is this session
  using" — `resolve_language()` — instead of independently deciding (or
  never deciding, and silently defaulting to English) as `ChiefAgent`,
  `DiscussionEngine`, `SociologicalInsightsService`, and
  `ConversationMemoryService` each previously did. Mirrors
  `backend/security/request_context.py`'s existing pattern.
- `backend/language/prompting.py` — one shared `language_directive()`
  instructing Claude to generate output directly in the target language
  (no separate translation pass), plus a template-mode fallback so
  language still applies when `ANTHROPIC_API_KEY` is unset.
- Consolidated three previously-independent, drifting "what language is
  active" states — the conversation store's own `language`/`setLanguage`,
  `LanguageProvider`'s app-wide context, and `useVoice`'s STT/TTS locale
  (which defaulted to English because nothing passed it a language at
  all) — into the one global `LanguageProvider` context. Verified this
  doesn't conflict with the voice-parity work above: `VoicePage.tsx`
  already read language from the global context directly, never from
  the store, so removing the store's copy of it needed no further
  change there.
- `backend/intelligence/executive_summary.py` — `build_executive_report`
  now localizes its assembled prose (title, key findings, evidence,
  recommendations, timeline labels — deterministic strings, not LLM
  output, so batch-translated via the existing `TranslationService`
  rather than "generated natively") and skips re-translating `summary`
  when the underlying narrative was already generated natively in that
  language.
- Coordinated updates across `chief/agent.py`, `investigation_stream.py`,
  `discussion/engine.py`, `sociological_insights.py`,
  `conversation_memory.py`, `orchestrator/{graph,state}.py`,
  `voice_service.py`, and `AnalyticsTopicCard.tsx` (client-side
  translation now skipped when content is already native).

**Deliberately not merged — `SHERLOCK-integrated-v3__1_`.** Turned out
to be a substantially larger, separate "Conversation System Refactor"
(case-scoped conversations, a sidebar → chat-history redesign, and
removal of the standalone Voice page) touching core investigation
agents (`crime_records`, `financial`, `forecasting`, `pattern_analysis`)
and conflicting architecturally with the language consolidation above
(it still used the old per-store `language` field). Same call as the
duplicate offender-profiling engine two integration rounds ago: real,
substantial parallel work, not a mechanical merge — flagged for a
dedicated follow-up pass rather than rushed in alongside four other
lineages. Its "Voice page" removal was also evaluated against this
round's "keep the page, share its state" approach and not adopted, for
the same reasons stated when Voice was first kept as its own nav item
back in Stage F2.

**Validated post-merge:** `pytest backend/tests/` (99/99 — 66 prior +
8 graph-search + 3 voice-sharing + `test_language_context.py`), all 14
`tests/validate_*.py` stage scripts, `tsc -b` clean, `vite build` clean,
`oxlint` 0 errors, and a live `TestClient` sweep: fuzzy graph search,
generic vs. legacy graph-node-endpoint output equivalence, the
`X-App-Language` header round-tripping through the new middleware, a
spoken command reaching the `summarize` and previously-unreachable
`clear_history` intents, and pre-existing imperative voice shortcuts
(`open_case`) still working unchanged. 75 total registered API paths.

---

## Integration Release 2 — merging a fourth parallel workstream (i18n + executive summaries)

A fourth independently-diverged tree was merged in, forked earlier than
the other three (its `backend/agents/sociological_intelligence/agent.py`
was still the pre-upgrade Sprint B4 baseline). It contributed two
genuinely new, non-overlapping capabilities, plus one parallel
implementation of an already-integrated feature that was evaluated and
**not** merged.

**Merged in:**
- **App-wide i18n.** `frontend/src/providers/LanguageProvider.tsx` +
  `LanguageToggle.tsx`, wired into `AppProviders`. `backend/language/
  resources.py` expanded 168 → 807 lines (navigation, common, dashboard,
  board, analytics, voice, admin, audit, graph, errors, notifications,
  dialogs sections; nothing removed — verified no dropped keys before
  merging). Applied to every page this workstream had already wired
  (`AppShell`, `Nav`, dashboard, board, graph, investigations, admin,
  voice) via a straight wholesale adopt, since none of those files had
  been touched by any other merged workstream. `Nav.tsx` required a real
  3-way merge (not a wholesale copy) to keep both this workstream's
  `t(labelKey, fallbackLabel)` pattern and every nav item the other three
  workstreams had already added (Conversation, Offenders, Sociological
  Insights, Forecasting) — added `navigation.offenders`,
  `navigation.sociological_insights`, and `navigation.forecasting` keys
  (en + kn) to cover them. **The three new Kannada strings are a
  best-effort translation, not yet reviewed by a native speaker** —
  flagged rather than presented as verified. Also fixed a genuine
  pre-existing dead route while in this file: `/admin/audit`
  (`AuditLogPage`) had a translation key (`navigation.audit_log`)
  reserved for it but was never in `NAV_ITEMS` in any of the four trees —
  added it.
- **Executive Intelligence Summarizer.** `backend/intelligence/
  executive_summary.py` — a pure presentation-layer transform
  (`build_executive_report(final_report)`), turning a Chief Agent
  `final_report` into the ranked/counted card schema Analytics renders
  (risk badge, confidence, key findings, recommendations, supporting
  evidence, metrics). Wired into `backend/voice/command_router.py`'s
  `_investigate` handler (one added import, one added field on an
  existing response — nothing else in that file touched) and rendered by
  the adopted `AnalyticsTopicCard.tsx`, including live translation of the
  (English-only-generated) report content via `translateDynamic` when
  viewed in Kannada. This module was present but **completely unwired**
  in its source tree (no import anywhere in `backend/api/` or
  `main.py`) — found via the same orphaned-code check the rest of this
  integration has used throughout.

**Evaluated and deliberately not merged — a real parallel implementation,
not a mechanical conflict:** this tree had its own `backend/intelligence/
offender_profiler.py` (single-file, `build_offender_profile(person_id,
session)`) + `backend/api/offender_profile.py` (2 endpoints) +
`frontend/src/persons/OffenderProfilePage.tsx`, implementing the same
Requirement 5 as the already-integrated Stage G1 engine. Kept Stage G1's
version: broader API surface (5 endpoints vs. 2), real NetworkX
PageRank/centrality, the brief's exact stated risk weights, and its own
already-passing validation suite — all already wired into `Nav`/routes
and exercised by three merges' worth of regression tests. The other
tree's `test_offender_profiler.py` / `test_offender_profile_api.py` were
excluded rather than copied in, since they assert a different function
signature (`person_id` before `session`) than the version being kept and
would fail against it. Its one genuinely good idea not present in Stage
G1 — a "profile every accused person on a given FIR in one call" bulk
endpoint — is noted here as a worthwhile follow-up, not implemented in
this pass.

**Validated post-merge:** `pytest backend/tests/` (66/66 — 56 prior +
10 new), all 14 `tests/validate_*.py` stage scripts, `tsc -b` clean,
`vite build` clean, `oxlint` 0 errors, live `TestClient` checks of
`/language/resources/kn` (new keys resolve correctly) and a real voice
`_investigate` call (`executive_report` attached with a real computed
risk_level/confidence, not a stub).

---

## Integration Release — merging three parallel workstreams

Three independent workstreams had diverged from the same post-Stage-F base
and were merged into this single repository:

- **Analytics workstream:** `backend/analytics/` (hotspot/cluster/modus/
  seasonal/trend/summary engines), `backend/api/analytics.py`
  (`/analytics/dashboard`), and a rebuilt `frontend/src/analytics/` with a
  real Leaflet-based `HotspotMap` (new deps: `leaflet`, `leaflet.heat`,
  `react-leaflet`).
- **Forecasting + Sociological workstream:** `backend/forecasting/` (trend/
  hotspot/repeat-alert/gang-alert/anomaly/risk/early-warning engines,
  `/forecast/*`), `backend/intelligence/sociological_insights.py` +
  `backend/api/sociological.py` (`/analytics/sociological`, `/analytics/
  sociological/report`), and `frontend/src/forecasting/` +
  `frontend/src/sociological/`.
- **Conversation + Offender Profiling workstream:** already in this
  tree (Stage F2 / Stage G1 above).

**Merge process:** each workstream's genuinely new files (disjoint
directories/modules) were copied in as-is — no rewriting. Shared
integration points that every workstream had independently edited
(`backend/app/main.py` router registration, `frontend/src/app/routes.tsx`,
`frontend/src/components/layout/Nav.tsx`, `frontend/src/lib/types.ts`,
`backend/requirements.txt`, `frontend/package.json`) were hand-merged.

**One real conflict found and fixed, not just a mechanical merge:** the
Analytics/Conversation/Offender-Profiling base still had the *original*
`backend/agents/sociological_intelligence/agent.py` (Sprint B4 baseline —
simple demographic tabulation only), while the Forecasting/Sociological
workstream's `backend/intelligence/sociological_insights.py` and its test
suite (`backend/tests/test_sociological_insights.py`) were written against
an *upgraded* version of that same agent file (emits `social_risk_factors`
and `socioeconomic_correlation` findings in addition to
`sociological_profile`). Because the file existed, unchanged in name, on
both sides, a naive directory merge would have silently kept the stale
version and left one test failing
(`test_agent_emits_demographic_and_risk_findings`). Resolved by adopting
the upgraded `agent.py` and updating `backend/agents/base/
explainability.py`'s finding-type registry to match (two new entries).
This was found by diffing file *content*, not just file *presence*,
across all three trees — see the integration report for the full
methodology.

**Validated post-merge, all real (no mocks):** `pytest backend/tests/`
(56/56 passed), all 14 top-level `tests/validate_*.py` stage scripts
(14/14 passed), `tsc -b` (clean), `vite build` (clean), `oxlint` (0
errors), and a live `TestClient` smoke test of every new/merged endpoint
plus `/openapi.json` (73 registered paths, no collisions).

**Not independently re-verified in this pass** (see integration report):
`docker compose up` (no Docker daemon in the build sandbox — Dockerfile/
docker-compose.yml were identical across all three source trees, so
nothing here needed merging, but the actual container build wasn't
re-run), and a full manual click-through of every frontend page.

---

## Stage G1 — Criminology-Based Offender Profiling Engine

Implements Requirement 5 of the challenge statement: a deterministic,
explainable offender dossier per person — never LLM-generated, every
number computed from real FIR/Accused/Victim/Witness/Arrest/ChargeSheet/
Weapon/Vehicle/Transaction/PersonAssociation/OrganizationMembership
records, with a stated "because" reason behind every score.

- Added `backend/intelligence/` (alongside the pre-existing, unrelated
  `board_intelligence.py`): `criminal_history.py` (FIR/arrest/chargesheet
  roll-up, repeat/habitual flags), `behavior_profiler.py` (escalation —
  reuses `behavioral_intelligence` agent's own `VIOLENCE_WEIGHTS` for
  severity ordering rather than a second table — aggression, planning,
  mobility via real haversine distance between offence locations, target
  selection, time-of-crime profile), `modus_profiler.py` (weapon/vehicle/
  financial-method from real FKs, plus honestly-labeled deterministic
  keyword-bucket matching over free-text MO fields — not claimed as ML
  clustering, since this repo has no NLP dependency), `network_profile.py`
  (reuses the existing `GraphIntelligenceService.find_associates`, plus
  real NetworkX PageRank/degree-centrality/community-size when the active
  backend is NetworkX — degrades honestly on the Neo4j backend, which
  doesn't expose those, rather than faking numbers), `risk_engine.py`
  (the brief's exact weighted formula: Violence 25% / Repeat History 20% /
  Escalation 15% / Network 15% / Financial 10% / Mobility 5% / Weapons
  10%), `investigation_priority.py` (Routine → Critical ladder),
  `profile_summary.py` (rule-fired recommendations, each with a because),
  `offender_profiler.py` (`build_offender_profile()`, the single entry
  point assembling all of the above into the brief's exact JSON shape).
- Added `scipy` to `backend/requirements.txt` — required by
  `networkx.pagerank()` for the network centrality metrics above.
- Added `backend/api/offender_profile.py`: `GET /persons/{id}/profile`,
  `GET /persons/high-risk`, `POST /persons/profile/search`,
  `GET /persons/{id}/timeline`, `GET /persons/{id}/network`. Read-only;
  bulk endpoints build one `graph_service` and reuse it across every
  candidate rather than rebuilding the in-memory graph per person.
- Added `frontend/src/offender/`: `OffenderProfilePage`,
  `HighRiskPersonsPage`, `RiskGauge`, `BehaviorTimeline`, `CrimeHistory`,
  `ModusProfile`, `NetworkSummary`, `RecommendationPanel`,
  `EvidencePanel`. Per the brief's "do not duplicate UI": `NetworkSummary`
  shows analytics inline and links out to the existing `/graph/:personId`
  route + `GraphView` component for the actual force-directed
  visualization, rather than re-embedding it. New "Offenders" nav item.
- Added `tests/validate_stage_g1.py` — real seeded dataset, real
  FastAPI app, no mocks. Covers full profile shape, the risk formula's
  arithmetic, priority-ladder overrides, rule-fired recommendations, a
  zero-history edge case, an unknown-person error case, all 5 endpoints,
  and regression checks against `/investigate`, `/conversation/message`,
  `/health`.
- **Known limitations, documented rather than hidden:** (1) `Victim`
  records are person-linked only in this schema, so business/government/
  financial-institution "target selection" categories from the brief
  aren't separately modeled — see `behavior_profiler.py`'s `_target_selection`.
  (2) MO free-text "clustering" is deterministic keyword-bucket matching
  against a small stated vocabulary, not semantic/ML clustering — see
  `modus_profiler.py`'s module docstring. (3) Graph centrality/PageRank
  is only computed on the default NetworkX backend, not Neo4j — see
  `network_profile.py`'s `_graph_metrics`.

---

## Stage F2 — Conversation Intelligence System (unified chat interface)

Implements the "Conversation Intelligence System (CIS)" proposal: Conversation
becomes the primary interface rather than a frontend refactor of Voice, with
every other screen (Board, Analytics, Network, Findings) reachable as a tool
the conversation calls into — without reimplementing any of the orchestration,
memory, translation, voice, or reporting subsystems already built in Stages
C/D/E. New/changed, all additive:

- Added `backend/conversation/` — `session.py` (session get-or-create),
  `router.py` (meta-intent detection: summarize / export / clear vs.
  investigate), `citations.py` (validated findings -> evidence-card shape,
  entities resolved to labels), `prompts.py` (deterministic, template-based
  suggested follow-up questions — never freely LLM-generated, same
  philosophy as ChiefAgent/ConversationMemoryService), `summarizer.py`
  (on-demand summary, any conversation length), `manager.py`
  (`ConversationManager`, the single orchestration facade).
- Added `backend/api/conversation_chat.py`: `POST /conversation/message`
  (non-streaming turn), `POST /conversation/stream` (SSE — the same
  `stream_investigation` pipeline `/ws/investigate` uses, for clients that
  don't want to manage a WebSocket), `GET /conversation/{id}/history`
  (chat-shaped message list), `POST /conversation/{id}/summarize`,
  `POST /conversation/{id}/export/pdf`, `DELETE /conversation/{id}/history`
  (soft-archive only — Stage E5's "no physical deletion" rule is
  unconditional; a topic-reset marker turn is what actually stops
  pronoun/entity carry-forward, reusing the existing tested mechanism).
- Added `frontend/src/conversation/`: `ConversationPage` (primary screen),
  `ConversationProvider` + `hooks/useConversation.ts` (SSE-driven turn
  handling), `store.ts` (zustand), `ConversationMessage`, `EvidenceCard`,
  `AgentExecutionTimeline`, `SuggestedQuestions`, `ConversationSidebar`,
  `VoiceButton`, `ChatComposer`. `VoiceButton` wires into the *same*
  `useVoice` hook and `sendMessage` call as typed input — voice is one
  input into the conversation, not a separate feature.
- `Nav.tsx`: "Conversation" promoted to the top nav item; `/` now redirects
  to `/conversation` instead of `/dashboard`. "Voice" is kept as its own
  item (not deleted) for the dedicated hands-free/server-audio experience —
  see Nav.tsx's own comment for the reasoning.
- Added `tests/validate_stage_f2.py` — real seeded SQLite dataset, real
  FastAPI app, real LangGraph pipeline, real PDF bytes; no mocks. Covers
  session bootstrap, pronoun carry-forward through the new endpoint,
  citation/entity shape, all three meta-intents, soft-clear + row
  survival, SSE event shape, and regression checks against
  `/ws/investigate`, `/investigate`, `/health`.
- **Known limitation, documented rather than hidden:** `export_last_report_as_pdf`
  reconstructs a minimal report (`narrative` + `findings`) from what
  `ConversationTurn` actually persists, not the richer in-memory
  `final_report` (no stored `audit_trail`) — see
  `backend/conversation/manager.py`'s docstring.

---

## v1.0.0 — Submission Release

*Phase 7: Documentation, demo polish, and final validation*

- Added Prevention Intelligence Agent (patrol, surveillance, CCTV, PMLA recommendations)
- Added Financial Intelligence Agent (money-mule ring detection, fan-in pattern analysis)
- Added PDF investigation report export (ReportLab, case ID, timeline, confidence heatmap)
- Added "All findings evidence-backed and validated" banner to Command Center header
- Updated quick-query presets to match the three official demo queries exactly
- Fixed financial query routing: NetworkAnalysis now runs for all query types
- Added `docs/pitch_deck.html` — 8-slide keyboard-navigable presentation
- Added `docs/JUDGE_QA.md` — word-for-word answers to 8 judge questions
- Added `docs/DEMO_SCRIPT.md` — timed, narrated demo flow
- Added `docs/ARCHITECTURE.md`, `SYSTEM_DESIGN.md`, `DATA_MODEL.md`, `GRAPH_SCHEMA.md`
- Added `docs/AGENT_DESIGN.md`, `API_REFERENCE.md`, `DEPLOYMENT_GUIDE.md`
- Added `docs/FEATURE_MAPPING.md`, `VALIDATION_REPORT.md`, `PERFORMANCE_REPORT.md`
- Added `docs/FUTURE_ROADMAP.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- **Validation:** 3/3 demos PASS, 0 rejected findings, avg 1.4s investigation time

---

## v0.6.0 — Command Center

*Phase 6: Frontend + WebSocket streaming*

- Built SHERLOCK Command Center (`frontend/index.html`) — single-file React application
- Dark intelligence aesthetic: IBM Plex Mono + IBM Plex Sans, amber/cyan on near-black
- Live Metrics Strip: 7 stats from `/metrics` endpoint
- Investigation Feed: WebSocket-streamed per-agent events with status icons
- Crime Intelligence Graph: D3 force-directed ego-subgraph, drag + zoom
- Crime Trends Chart: monthly bar chart, festival months highlighted amber
- District Hotspots Panel: ranked bar chart
- Evidence & Validation Panel: findings with confidence badges
- Report Modal: narrative + findings + prevention recommendations + PDF export button
- Query Bar: free-form NL input + quick-query presets + Enter-to-submit
- FastAPI WebSocket endpoint (`/ws/investigate`) with streaming LangGraph integration
- `GET /metrics`, `GET /graph/{person_id}`, `POST /export/pdf`, `GET /health`
- `backend/app/server.py`: single-command startup serving frontend at `/`

---

## v0.5.0 — Intelligence Layer (LangGraph)

*Phase 5: Multi-agent orchestration*

- Implemented `AgentFinding` dataclass — frozen inter-agent contract
- Implemented `SherlockState` TypedDict with `operator.add` reducers
- Implemented `BaseAgent` abstraction with plan-driven skip logic
- Implemented `query_parser.py` — rule-based NLU (crime type, district, intent flags)
- Implemented `ChiefAgent` — `plan_node` + `synthesis_node`, optional Claude narrative
- Implemented `CrimeRecordsAgent` — SQL retrieval, passes `graph_context` downstream
- Implemented `NetworkAnalysisAgent` — repeat offenders + associate networks via graph_service
- Implemented `PatternAnalysisAgent` — clusters, seasonal spikes, hotspot forecasts
- Implemented `EvidenceValidationAgent` — mandatory gate, three validation rules
- Built LangGraph 6-node graph: chief_plan → crime_records → network_analysis → pattern_analysis → evidence_validation → chief_synthesis
- Built `stream_investigation()` — wraps `graph.stream()`, emits WebSocket events per node
- **Milestone:** Demo 1 query answered end-to-end through the full agent pipeline

---

## v0.4.0 — Graph Intelligence Service

*Phase 2C: Query abstraction layer*

- Implemented `GraphIntelligenceService` abstract interface
- Implemented `NetworkXGraphService` with 5 core queries + `get_metrics()`
- Implemented `Neo4jGraphService` with equivalent Cypher queries
- `get_graph_service()` factory: selects backend from `GRAPH_BACKEND` env var
- `find_repeat_offenders()` — PERSON_COMMITTED_CRIME edge counting
- `find_associates()` — PERSON_ASSOCIATED_WITH / PERSON_LINKED_TO_PERSON traversal
- `find_financial_network()` — bidirectional transaction tracing
- `find_location_clusters()` — district/month crime aggregation
- `find_connection()` — shortest path between two persons
- Built `demo_graph_queries.py` — milestone demo validating all 5 queries
- **Milestone:** Crime Intelligence Graph operational, festival-season spike confirmed (94%)

---

## v0.3.0 — Graph Builders

*Phase 2B: SQL → Graph pipeline*

- Implemented `builder_networkx.py` — builds in-memory MultiDiGraph from SQLAlchemy session
- Implemented `builder_neo4j.py` — batched UNWIND/MERGE writes to Neo4j
- Implemented `neo4j_client.py` — driver wrapper with `run_query`, `run_write`, `run_write_batch`
- Implemented `graph/schema.py` — frozen node labels, relationship types, constraint statements
- Added Docker Compose: Postgres + Neo4j services
- All 11 relationship types implemented and verified

---

## v0.2.0 — Synthetic Dataset

*Phase 3: Reproducible test data with injected patterns*

- Implemented `generate_synthetic_data.py` with seeded Faker (Karnataka-specific)
- Injected 4 deliberate patterns: festival spike, repeat offenders, name aliases, money-mule ring
- Implemented `inspect_data.py` for dataset sanity checking
- **Validated:** 92% of Mysuru burglaries in Sep–Nov; top repeat offenders with 20–21 crimes

---

## v0.1.0 — Data Foundation

*Phase 1: Core entities and database layer*

- Defined all 10 SQLAlchemy models: `Person`, `PersonAlias`, `Location`, `Crime`, `FIR`, `PersonCrimeLink`, `Vehicle`, `Phone`, `BankAccount`, `Transaction`, `PersonAssociation`
- Implemented `database/config.py` with SQLite default + Postgres override
- Implemented `CrimeType`, `FIRStatus`, `PersonRole`, `RelationType`, `Gender` enumerations
- Established full repository structure per architecture freeze
- `PersonCrimeLink.raw_name_used` — the entity resolution challenge field
- `BankAccount.is_flagged_mule` and `Transaction.is_suspicious` — financial intelligence flags
