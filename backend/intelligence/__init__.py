"""
SHERLOCK — `backend/intelligence/` package.

Pre-existing: `board_intelligence.py` (AI Suggestions panel on the
Investigation Board — unrelated, untouched here).

Stage G1 (new, additive): Criminology-Based Offender Profiling Engine,
implementing Requirement 5 of the challenge statement as a real,
explainable offender dossier — not a "profile page" that reformats a
person row, and not an LLM-generated character sketch. Every number in
`build_offender_profile()`'s output is computed deterministically from
FIRs, Accused/Victim/Witness records, Arrests, ChargeSheets,
Transactions, Weapons, Vehicles, PersonAssociations, and Organization
memberships already in the database — the same "no black-box scoring"
discipline `backend/agents/base/explainability.py` established for the
investigation pipeline, applied here to person-level profiling.

    criminal_history.py       — FIR/arrest/chargesheet counts, offence
                                 dates, repeat/habitual flags
    behavior_profiler.py      — escalation, violence/aggression,
                                 planning, mobility, target selection,
                                 time-of-crime profile
    modus_profiler.py         — weapon/vehicle usage, MO free-text
                                 keyword extraction, crime sequence
    network_profile.py        — associates, organizations, financial
                                 links, graph centrality/PageRank
    risk_engine.py            — weighted 0-100 risk score + band
    investigation_priority.py — Routine -> Critical classification
    profile_summary.py        — deterministic recommendations, each
                                 with a stated "because" reason
    offender_profiler.py      — build_offender_profile(), the one
                                 entry point that assembles all of the
                                 above into the Requirement 5 JSON shape
"""

from backend.intelligence.offender_profiler import build_offender_profile

__all__ = ["build_offender_profile"]
