# SHERLOCK — Validation Report

*Generated from live test runs on the synthetic Karnataka dataset (500 persons, 1,001 crimes)*

---

## Test Environment

| Parameter | Value |
|-----------|-------|
| Dataset | Synthetic Karnataka crime data |
| Persons | 500 |
| Crimes / FIRs | 1,001 |
| Graph Relationships | 10,454 |
| Backend | NetworkX (in-memory, dev) |
| LLM API | Not required (deterministic template mode) |
| Platform | Python 3.11 · LangGraph 1.2.5 |

---

## Demo 1 — Crime Pattern Discovery

**Query:**
> "Show repeat burglary offenders operating in Mysuru during festival seasons and identify future hotspots."

### Agent Execution

| Agent | Status | Time | Message |
|-------|--------|------|---------|
| Chief Investigation Officer (plan) | ✓ DONE | ~50ms | Investigation plan created. Agents: CrimeRecords, NetworkAnalysis, PatternAnalysis, PreventionAgent |
| Crime Records Agent | ✓ DONE | ~200ms | Retrieved 110 burglary FIR(s) in Mysuru during festival season (Sep-Nov) |
| Network Analysis Agent | ✓ DONE | ~400ms | Identified 34 repeat offender(s) within investigation scope |
| Financial Intelligence Agent | — SKIPPED | 0ms | Not required for this query |
| Pattern & MO Agent | ✓ DONE | ~200ms | Festival season concentration 94% detected in Mysuru |
| Prevention Intelligence Agent | ✓ DONE | ~50ms | 4 recommendations generated |
| Evidence Validation Agent | ✓ DONE | ~50ms | 10 findings: 10 accepted, 0 flagged, 0 rejected |
| Chief Investigation Officer (synthesis) | ✓ DONE | ~20ms | Final report generated |

### Findings Summary

| Finding | Agent | Type | Confidence | Validated |
|---------|-------|------|-----------|-----------|
| 34 repeat offenders in scope | Network Analysis | repeat_offender_network | 92% | ✅ |
| Top offender + 5 associates | Network Analysis | criminal_association | 85% | ✅ |
| Top crime clusters: Mysuru Oct (44), Sep (37) | Pattern & MO | crime_pattern | 88% | ✅ |
| 94% festival concentration in Mysuru | Pattern & MO | seasonal_spike | 90% | ✅ |
| Festival hotspot forecast | Pattern & MO | hotspot_forecast | 70% | ✅ |
| 110 burglary FIRs retrieved | Crime Records | case_records | 100% | ✅ |
| Patrol density — Mysuru festival season | Prevention | patrol_strategy | 88% | ✅ |
| Surveillance — top 5 repeat offenders | Prevention | surveillance_action | 85% | ✅ |
| CCTV deployment — 30 days pre-Dasara | Prevention | prevention_recommendation | 82% | ✅ |
| Inter-district coordination | Prevention | prevention_recommendation | 75% | ✅ |

**Result: PASS — 10/10 findings validated, 0 rejected**
**Total time: 1,556ms | PDF: 9KB**

---

## Demo 2 — Financial Intelligence

**Query:**
> "Trace the financial network linked to fraud cases and identify suspicious money movement patterns."

### Agent Execution

| Agent | Status | Time | Message |
|-------|--------|------|---------|
| Chief Investigation Officer (plan) | ✓ DONE | ~50ms | Plan: CrimeRecords, NetworkAnalysis, FinancialAgent, PatternAnalysis, PreventionAgent |
| Crime Records Agent | ✓ DONE | ~200ms | Retrieved 158 fraud FIR(s) |
| Network Analysis Agent | ✓ DONE | ~350ms | Identified 50 repeat offenders across all cases |
| Financial Intelligence Agent | ✓ DONE | ~180ms | Money-mule network: 8 accounts, ₹8.1L hub fan-in |
| Pattern & MO Agent | ✓ DONE | ~180ms | Festival fraud concentration detected in Belagavi (71%) |
| Prevention Intelligence Agent | ✓ DONE | ~50ms | 5 recommendations including PMLA referral |
| Evidence Validation Agent | ✓ DONE | ~50ms | 12 findings: 12 accepted, 0 flagged, 0 rejected |
| Chief Investigation Officer (synthesis) | ✓ DONE | ~20ms | Final report generated |

### Findings Summary

| Finding | Agent | Type | Confidence | Validated |
|---------|-------|------|-----------|-----------|
| 8-account mule ring, ₹8.1L hub | Financial | financial_network | 93% | ✅ |
| Fan-in aggregation pattern | Financial | suspicious_pattern | 89% | ✅ |
| 50 repeat offenders detected | Network Analysis | repeat_offender_network | 75% | ✅ |
| Top offender + associates | Network Analysis | criminal_association | 85% | ✅ |
| Top fraud clusters | Pattern & MO | crime_pattern | 88% | ✅ |
| 71% festival concentration in Belagavi | Pattern & MO | seasonal_spike | 90% | ✅ |
| 158 fraud FIRs retrieved | Crime Records | case_records | 100% | ✅ |
| Patrol — Belagavi festival season | Prevention | patrol_strategy | 88% | ✅ |
| Surveillance — repeat offenders | Prevention | surveillance_action | 85% | ✅ |
| Account freeze + ED/PMLA referral | Prevention | prevention_recommendation | 91% | ✅ |
| CCTV deployment | Prevention | prevention_recommendation | 82% | ✅ |
| Inter-district coordination | Prevention | prevention_recommendation | 75% | ✅ |

**Result: PASS — 12/12 findings validated, 0 rejected**
**Total time: 1,117ms | PDF: 10KB**

---

## Demo 3 — Criminal Association Discovery

**Query:**
> "Find hidden relationships between repeat offenders and identify potential organized crime groups."

### Agent Execution

| Agent | Status | Time | Message |
|-------|--------|------|---------|
| Chief Investigation Officer (plan) | ✓ DONE | ~50ms | Plan: CrimeRecords, NetworkAnalysis, PatternAnalysis, PreventionAgent |
| Crime Records Agent | ✓ DONE | ~250ms | Retrieved 1001 crime FIR(s) (no type/district filter) |
| Network Analysis Agent | ✓ DONE | ~450ms | Identified 50 repeat offenders across all cases |
| Financial Intelligence Agent | — SKIPPED | 0ms | Not required for this query |
| Pattern & MO Agent | ✓ DONE | ~400ms | Crime clusters detected across all districts |
| Prevention Intelligence Agent | ✓ DONE | ~50ms | 4 recommendations generated |
| Evidence Validation Agent | ✓ DONE | ~50ms | 9 findings: 9 accepted, 0 flagged, 0 rejected |
| Chief Investigation Officer (synthesis) | ✓ DONE | ~20ms | Final report generated |

**Result: PASS — 9/9 findings validated, 0 rejected**
**Total time: 1,394ms | PDF: 9KB**

---

## Aggregate Results

| Metric | Demo 1 | Demo 2 | Demo 3 | Total |
|--------|--------|--------|--------|-------|
| Total time | 1,556ms | 1,117ms | 1,394ms | avg 1,356ms |
| Agents fired | 6 | 7 | 6 | — |
| Agents skipped | 1 | 0 | 1 | — |
| Analysis findings | 6 | 7 | 5 | 18 |
| Prevention recommendations | 4 | 5 | 4 | 13 |
| Rejected findings | **0** | **0** | **0** | **0** |
| Validation rate | 100% | 100% | 100% | **100%** |
| PDF generated | ✅ 9KB | ✅ 10KB | ✅ 9KB | — |

---

## Evidence Validation Rules (Applied to All Findings)

| Rule | Effect |
|------|--------|
| `evidence` list is empty | Finding rejected — `validated=False` |
| `confidence < 0.60` | Finding flagged — `validated=True`, noted |
| `evidence` present AND `confidence >= 0.60` | Finding validated — `validated=True` |

**No finding without evidence reaches the final report.** This is enforced programmatically by `EvidenceValidationAgent` on every investigation, regardless of which agents ran.

---

## Additional Graph Validation

| Query | Result |
|-------|--------|
| `find_repeat_offenders(min_crimes=5)` | Returns top offenders with 20–21 crimes each ✅ |
| `find_associates(top_offender_id)` | Returns 5 named associates with edge types ✅ |
| `find_financial_network(hub_account_id)` | Returns 29 suspicious transactions, ₹8.1L total ✅ |
| `find_location_clusters(crime_type='burglary')` | Mysuru Sep/Oct/Nov = 110 of 117 = 94% ✅ |
| `find_connection(mule_a, mule_b)` | 2-hop path found via shared associate ✅ |

*All graph queries validated against the synthetic dataset with known injected patterns.*

---

**Validation conclusion: SHERLOCK is demo-ready. All three official queries pass with 100% finding validation rate and zero evidence-less claims.**
