# SHERLOCK — Agent Mapping

**Sprint B3 · Deliverable 4**

Two parts: **Part 1** documents the 11 agents that actually exist, verified against `backend/agents/*/agent.py` and the pipeline wiring in `backend/orchestrator/graph.py`. **Part 2** proposes the specialist divisions the alignment brief's target schema (`docs/DATABASE_ANALYSIS/05_GRAPH_MAPPING.md`, `06_SCHEMA_MIGRATION.md`) implies but that don't exist yet — these are planned, not built.

---

## Part 1 — Implemented agents

Pipeline order, per `backend/orchestrator/graph.py`:

```
chief_plan → crime_records → network_analysis → entity_resolution →
timeline_reconstruction → financial_agent → similar_case →
pattern_analysis → forecasting_agent → prevention_agent →
evidence_validation → chief_synthesis
```

Every specialist returns a list of `AgentFinding` objects (`backend/agents/base/finding.py`) — the one shared contract every agent and the frontend `findings/FindingsPanel.tsx` consume. No agent passes free-form text to another.

---

### Chief Investigation Officer — Orchestrator

| | |
|---|---|
| **Role** | Plans (which specialists run, what filters apply) and synthesizes the final report. Never touches the database or `graph_service` directly. |
| **Consumes** | The raw NL query (plan) / `validated_findings` (synthesis) |
| **Outputs** | Investigation plan (filters: crime type, district, festival season) / final narrative report |
| **Reasoning** | Deterministic template by default; Claude-generated narrative if `ANTHROPIC_API_KEY` is set — pipeline works either way |
| **Graph position** | Entry (`chief_plan`) and exit (`chief_synthesis`) |

---

### Crime Records Agent — Tier 1

| | |
|---|---|
| **Consumes** | `crimes`, `locations`, `firs`, `person_crime_links` |
| **Outputs** | `case_records` — matching FIR/crime records, scoped by crime type + district |
| **Reasoning** | Direct SQL filter/join, no inference — "pure facts," per its own module docstring |
| **Evidence** | Row-level: crime IDs, FIR numbers |
| **Consumed by (downstream)** | Sets case scope that Network Analysis and Similar Case implicitly build on (first in the pipeline after planning) |

---

### Network Analysis Agent — Tier 2

| | |
|---|---|
| **Consumes** | Crime Intelligence Graph: `PERSON_ASSOCIATED_WITH`, `PERSON_LINKED_TO_PERSON`, `PERSON_COMMITTED_CRIME` edges |
| **Outputs** | `repeat_offender_network`, `criminal_association` |
| **Reasoning** | Graph traversal — edge-count ranking for repeat offenders, association-edge walk for criminal ties |
| **Evidence** | Cites specific graph edge types in its findings |
| **Note** | Explicitly scoped to accused persons identified by Crime Records — doesn't run network analysis on the whole graph, only the case-relevant subset |

---

### Entity Resolution Agent — Tier 1

| | |
|---|---|
| **Consumes** | `person_crime_links.raw_name_used` only — deliberately never sees `person_aliases` (ground truth), to make resolution a genuine inference task rather than a lookup |
| **Outputs** | `entity_resolution`, `entity_resolution_flag` |
| **Reasoning** | Three-tier matching: exact match against `Person.name`, then progressively fuzzier matching (per its module docstring) |
| **Evidence** | Raw name variant → resolved canonical person, with confidence per match tier |

---

### Timeline Reconstruction Agent — Tier 2

| | |
|---|---|
| **Consumes** | `crimes.timestamp`, scoped to crime IDs from Crime Records |
| **Outputs** | `investigation_timeline` |
| **Reasoning** | Chronological ordering only — explicitly described in its docstring as "a simple, real" approach, not pattern inference (that's Pattern Analysis's job) |
| **Evidence** | Ordered crime timestamps |

---

### Financial Intelligence Agent — Tier 2

| | |
|---|---|
| **Consumes** | `bank_accounts` (filtered `is_flagged_mule=True`), `transactions` |
| **Outputs** | `financial_network`, `suspicious_pattern` |
| **Reasoning** | Hub-account identification (highest incoming transaction count among flagged mules), fan-in pattern detection |
| **Evidence** | Account numbers, transaction totals, flags |

---

### Similar Case Agent — Tier 2

| | |
|---|---|
| **Consumes** | `crimes.modus_operandi`, scoped by crime type |
| **Outputs** | `similar_case` |
| **Reasoning** | Text similarity scoring between MO descriptions across cases not already on the same FIR |
| **Evidence** | Pairwise crime comparisons with similarity score |

---

### Pattern & MO Agent — Tier 2

| | |
|---|---|
| **Consumes** | `graph_service.find_location_clusters()` — no direct SQL |
| **Outputs** | `crime_pattern`, `seasonal_spike`, `hotspot_forecast` (conditionally, when `wants_forecast=True`) |
| **Reasoning** | Location-cluster analysis grouped by district/month |
| **Evidence** | Cluster statistics, seasonal concentration percentages |

---

### Forecasting Agent — Tier 2

| | |
|---|---|
| **Consumes** | `graph_service.find_location_clusters()` at larger `top_n` (500 vs. Pattern's 50) |
| **Outputs** | `hotspot_forecast` |
| **Reasoning** | Same clustering primitive as Pattern Analysis, wider net — deliberately overlapping data source, distinct purpose (forecasting vs. pattern description) |
| **Evidence** | Forward-looking cluster projections |

---

### Prevention Intelligence Agent — Tier 2 (downstream-only)

| | |
|---|---|
| **Consumes** | `state["findings"]` only — never touches raw data, per its own module docstring |
| **Outputs** | `patrol_strategy`, `surveillance_action`, `prevention_recommendation` (×2 variants) |
| **Reasoning** | Converts upstream findings (Network, Pattern, Financial) into concrete recommendations — patrol density, surveillance orders, CCTV, PMLA/ED referral, inter-district coordination |
| **Evidence** | Cites the upstream finding(s) each recommendation is derived from |

---

### Evidence Validation Agent — Governance (mandatory gate)

| | |
|---|---|
| **Consumes** | All `AgentFinding` objects produced so far in the pipeline |
| **Outputs** | `validation_summary` + annotates every finding with `validated`/`validation_notes` |
| **Reasoning** | Explicit rule-based validation (not ML) — rejects unsupported claims |
| **Evidence** | Per-finding accept/reject with stated reason |
| **Position** | Last specialist before `chief_synthesis` — the Chief only ever reads `validated_findings`, so nothing reaches the final report unvalidated |

---

## Agent → table matrix (implemented agents only)

| Agent | locations | persons | crimes | firs | person_crime_links | vehicles | phones | bank_accounts | transactions | person_associations | Graph only |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Crime Records | ✓ | | ✓ | ✓ | ✓ | | | | | | |
| Network Analysis | | | | | | | | | | | ✓ |
| Entity Resolution | | | | | ✓ | | | | | | |
| Timeline Reconstruction | | | ✓ | | | | | | | | |
| Financial | | | | | | | | ✓ | ✓ | | |
| Similar Case | | | ✓ | | | | | | | | |
| Pattern Analysis | | | | | | | | | | | ✓ |
| Forecasting | | | | | | | | | | | ✓ |
| Prevention | | | | | | | | | | | (findings only) |
| Evidence Validation | | | | | | | | | | | (findings only) |
| Chief | | | | | | | | | | | (findings only) |

**No agent currently touches `vehicles` or `phones`** — both are graph nodes (`Vehicle`, `Phone`) with zero agent consumers. This was flagged in `docs/DATABASE_ANALYSIS/02_TABLE_CATALOG.md` as a real gap, not a documentation omission, and it matters for Part 2 below: any new Vehicle/Phone-centric agent has full data to work with already, it just doesn't exist yet.

---

## Part 2 — Planned specialist divisions (not implemented)

These follow directly from the Sprint A/B gap analysis (`05_GRAPH_MAPPING.md`, `06_SCHEMA_MIGRATION.md`, and Part 2 of the RTM) and from the two currently-unused asset tables noted above. None of these have any code today — this is a proposal for Sprint D scoping, not a status report.

### Asset Intelligence Agent *(new)*

| | |
|---|---|
| **Would consume** | `vehicles`, `phones` — currently orphaned graph nodes with zero agent consumers |
| **Would output** | Vehicle/phone ownership chains, shared-asset flags (e.g. two accused sharing a registered vehicle) |
| **Why it's missing matters** | This is the lowest-effort addition in this whole list — the data and graph nodes already exist; only the agent logic is missing |

### Call Detail Record (CDR) Agent *(new)*

| | |
|---|---|
| **Would consume** | New `call_records` table (proposed in `06_SCHEMA_MIGRATION.md`) + existing `phones` |
| **Would output** | Call-pattern findings feeding the target `CALLS` graph relationship |
| **Dependency** | Blocked on schema migration item — `call_records` doesn't exist yet |

### Officer & Accountability Agent *(new)*

| | |
|---|---|
| **Would consume** | New `officer_details`, `units` tables |
| **Would output** | `INVESTIGATED_BY`, `WORKS_AT`, `REPORTS_TO` relationship data; officer workload/caseload views |
| **Dependency** | Blocked on the `officer_details`/`units` migration — today `firs.investigating_officer` is a free-text string with nothing to query |

### Legal Classification Agent *(new)*

| | |
|---|---|
| **Would consume** | New `crime_heads`, `crime_sub_heads`, `acts`, `sections` |
| **Would output** | Applicable Act/Section suggestions per crime, replacing the current flat 6-value `CrimeType` enum |
| **Dependency** | Blocked on the Crime Head/Sub Head migration |

### Evidence & Property Custody Agent *(new)*

| | |
|---|---|
| **Would consume** | New `properties` table |
| **Would output** | Chain-of-custody findings, feeding the target `Property` graph node — currently seized evidence has no home anywhere in the schema |
| **Dependency** | Blocked on the `properties` table migration |
| **Relationship to existing Evidence Validation Agent** | Different job entirely despite the name overlap — Evidence Validation validates *AI findings*; this proposed agent would track *physical/seized evidence*. Worth a clearer name if both exist (e.g. "Property Custody Agent") to avoid confusion in the docs and UI. |

### Court & Disposition Agent *(new)*

| | |
|---|---|
| **Would consume** | New `courts` table, `firs.status` |
| **Would output** | `TRIED_IN` relationship data, case-disposition tracking (chargesheet → trial → conviction) |
| **Dependency** | Blocked on the `courts` table migration |

### Language Agent *(planned, already named in `FEATURE_MAPPING.md`)*

| | |
|---|---|
| **Status** | Stub referenced as "Phase 7D" in existing docs; no code exists |
| **Would consume** | Query text + response text (translation layer, not a data-querying agent) |
| **Note** | Architecturally different from the other planned agents — sits at the NL Console boundary, not inside the investigation pipeline |

### Voice Agent *(partially started)*

| | |
|---|---|
| **Status** | Frontend has `board/VoiceIndicator.tsx` and the stabilization pass mentions a "voice conversational-loop," but no backend Voice Agent directory exists |
| **Recommendation** | Verify what the frontend hook actually does (browser Web Speech API only, vs. a real backend integration) before scoping this as new work — it may be closer to done than this table implies |

---

## Summary table — all agents, implemented and planned

| Agent | Status | Blocked on |
|---|---|---|
| Chief, Crime Records, Network Analysis, Entity Resolution, Timeline Reconstruction, Financial, Similar Case, Pattern Analysis, Forecasting, Prevention, Evidence Validation | ✅ Implemented | — |
| Asset Intelligence | 🔲 Planned | Nothing — data already exists |
| CDR / Call Analysis | 🔲 Planned | `call_records` migration |
| Officer & Accountability | 🔲 Planned | `officer_details`/`units` migration |
| Legal Classification | 🔲 Planned | `crime_heads`/`sections` migration |
| Evidence & Property Custody | 🔲 Planned | `properties` migration |
| Court & Disposition | 🔲 Planned | `courts` migration |
| Language | 🔲 Planned, named in prior docs | None (independent of schema work) |
| Voice | ⚠ Partial | Needs verification, not necessarily new build |

**11 implemented, 6 fully blocked on schema migration, 1 unblocked and ready (Asset Intelligence), 2 in an unclear partial state worth a quick verification pass before scoping as new work.**

---

Next per the brief's sequencing would be Deliverable 5 (AI Capability Matrix) or Deliverable 8 (Implementation Backlog) — the Asset Intelligence Agent above is a natural first backlog item since it's the only planned agent with zero migration dependency.
