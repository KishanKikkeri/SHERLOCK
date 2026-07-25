"""
SHERLOCK — Executive Intelligence Summarizer.

    Question -> Planner -> Specialist Agents -> Evidence Validation
              -> Chief synthesis (final_report)
              -> **Executive Intelligence Summarizer (this module)**
              -> Structured report -> Analytics cards

This is a presentation-layer transform only. No specialist agent, the
Evidence Validation Agent, or the Chief Agent's narrative synthesis is
changed by this module — it consumes the *already-produced*
`final_report` dict (see `backend/agents/chief/agent.py::synthesis_node`)
and re-expresses it as the structured intelligence-report schema the
Analytics UI renders:

    title, summary, confidence, risk_level, key_findings,
    supporting_evidence, recommendations, metrics, entities,
    timeline, sources

Nothing here re-queries the graph, drops evidence, or reduces analytical
depth: every accepted AgentFinding still contributes, just aggregated,
ranked, and counted instead of dumped verbatim. The raw `final_report`
(all validated + rejected findings, full narrative) is always still
available alongside this output for a "Show Agent Trace" accordion —
see `backend/voice/command_router.py`, which attaches both.

Priority 25/28/30 (Project-wide Language Awareness): everything this
module builds — title, key findings, supporting evidence,
recommendations, timeline labels — is composed from deterministic
Python (counts, sorted lists, static phrases), not an LLM call, so
"generate natively" doesn't apply the way it does to ChiefAgent's
narrative. `build_executive_report(..., language=...)` instead
localizes the assembled strings in one batch via `TranslationService`
(see `_localize_executive_report`) — the same mechanism
`_localize_report` in `backend/api/investigation_stream.py` already
uses for specialist-agent finding summaries. The one field that can
already be native is `summary` (a verbatim copy of
`final_report["narrative"]`, which `ChiefAgent` may have generated
directly in `language` — see `final_report["narrative_language"]`);
`_localize_executive_report` skips re-translating it in that case to
avoid garbling an already-correct narrative.
"""
from __future__ import annotations

import logging
from collections import Counter

logger = logging.getLogger(__name__)

# Human-readable pluralization for the entity-type prefix used in
# AgentFinding.source_entities (e.g. "person_123" -> "person"). Falls
# back to "<type>(s)" for any prefix not listed here, so a new agent
# introducing a new entity prefix doesn't need this file touched.
_ENTITY_LABELS = {
    "person": "person(s) of interest",
    "location": "location(s)",
    "account": "financial account(s)",
    "organization": "organization(s)",
    "weapon": "weapon(s)",
    "fir": "FIR(s)",
    "officer": "officer(s)",
    "vehicle": "vehicle(s)",
    "case": "case(s)",
}

# finding_types that, when present alongside reasonable confidence,
# indicate something an officer should actively act on rather than
# just note. Used only to bias the Risk badge — never to filter or
# hide any finding.
_HIGH_RISK_TYPES = {
    "repeat_offender_network",
    "suspicious_pattern",
    "bank_network",
    "financial_network",
    "weapon_history",
    "behavioral_profile",
    "predictive_forecast",
    "hotspot_forecast",
}


def _entity_type(ref: str) -> str:
    return ref.split("_", 1)[0] if "_" in ref else ref


def _risk_level(mean_confidence: float, finding_types: set, accepted_count: int) -> str:
    if accepted_count == 0:
        return "Unknown"
    high_risk_hits = len(finding_types & _HIGH_RISK_TYPES)
    if mean_confidence >= 0.75 and high_risk_hits >= 2:
        return "High"
    if mean_confidence >= 0.55 or high_risk_hits >= 1:
        return "Medium"
    return "Low"


def _empty_report(final_report: dict, title: str | None, language: str = "en") -> dict:
    query = final_report.get("query", "")
    narrative = final_report.get("narrative", "") or ""
    rejected = final_report.get("rejected_findings", []) or []
    report = {
        "title": title or query or "Investigation report",
        "summary": narrative or "No validated findings were available for this query.",
        "confidence": 0,
        "risk_level": "Unknown",
        "key_findings": [],
        "supporting_evidence": [],
        "recommendations": [
            "Broaden the query, or confirm the relevant case data has been ingested, and re-run.",
        ],
        "metrics": {"findings_accepted": 0, "findings_rejected": len(rejected)},
        "entities": [],
        "timeline": [],
        "sources": sorted(set(final_report.get("agents_consulted", []))),
        # Priority 25/28/30: which language every prose field above is
        # actually in, so a consumer (e.g. AnalyticsTopicCard.tsx) can
        # tell this report is already localized and skip a redundant
        # (and potentially garbling) client-side re-translation pass.
        "language": language,
    }
    if language != "en":
        report = _localize_executive_report(report, final_report, language)
    return report


def build_executive_report(final_report: dict, *, title: str | None = None, language: str = "en") -> dict:
    """Transform a Chief-Agent `final_report` into the Analytics card schema.

    `final_report` is exactly the dict `synthesis_node` produces:
    {query, narrative, findings, rejected_findings, agents_consulted}.
    `findings` here are already the *accepted* (validated) ones.

    `language` (Priority 25/28/30, default "en"): localizes the assembled
    prose fields (not the numeric/structural ones) — see module
    docstring and `_localize_executive_report`.
    """
    accepted = final_report.get("findings", []) or []
    rejected = final_report.get("rejected_findings", []) or []
    query = final_report.get("query", "")
    narrative = final_report.get("narrative", "") or ""

    if not accepted:
        return _empty_report(final_report, title, language)

    # --- confidence ---------------------------------------------------
    confidences = [f.get("confidence", 0.0) for f in accepted]
    mean_confidence = sum(confidences) / len(confidences)
    confidence_pct = round(mean_confidence * 100)

    # --- ranked key findings --------------------------------------------
    ranked = sorted(accepted, key=lambda f: f.get("confidence", 0.0), reverse=True)
    key_findings = [f["summary"] for f in ranked[:6] if f.get("summary")]

    # --- risk level -------------------------------------------------------
    finding_types = {f.get("finding_type", "") for f in accepted}
    risk_level = _risk_level(mean_confidence, finding_types, len(accepted))

    # --- supporting evidence: counted, never dumped row-by-row -------------
    entity_counter: Counter = Counter()
    related_docs: set = set()
    for f in accepted:
        for ref in f.get("source_entities") or []:
            entity_counter[_entity_type(ref)] += 1
        for doc in f.get("related_documents") or []:
            related_docs.add(doc)

    supporting_evidence = [
        f"{count} {_ENTITY_LABELS.get(etype, etype + '(s)')}"
        for etype, count in entity_counter.most_common()
    ]
    if related_docs:
        supporting_evidence.append(f"{len(related_docs)} linked case document(s)")
    tail = f"{len(accepted)} finding(s) validated"
    if rejected:
        tail += f", {len(rejected)} rejected for insufficient evidence"
    supporting_evidence.append(tail)

    # --- recommendations: prefer real decision_support findings -------------
    decision_findings = [f for f in accepted if f.get("finding_type") == "decision_support"]
    if decision_findings:
        recommendations = [f["summary"] for f in decision_findings if f.get("summary")]
    else:
        recommendations = []
        for f in ranked[:3]:
            note = f.get("reasoning") or f.get("summary", "")
            if note and note not in recommendations:
                recommendations.append(note)
        if not recommendations:
            recommendations = ["Route findings to the assigned investigating officer for review."]

    # --- metrics: numeric metadata pulled up, not the whole blob ------------
    metrics: dict = {
        "findings_accepted": len(accepted),
        "findings_rejected": len(rejected),
        "agents_consulted": len(set(final_report.get("agents_consulted", []))),
    }
    for f in accepted:
        for k, v in (f.get("metadata") or {}).items():
            if isinstance(v, (int, float)) and k not in metrics:
                metrics[k] = v

    # --- entities -------------------------------------------------------------
    entities = [
        {"type": _entity_type(ref), "id": ref}
        for ref in sorted({r for f in accepted for r in (f.get("source_entities") or [])})
    ]

    # --- timeline: only what's actually dated in the evidence, never invented -
    timeline = []
    for f in accepted:
        for ev in f.get("evidence") or []:
            if ev.lower().startswith("month "):
                timeline.append({"label": ev, "agent": f.get("agent_name", "")})

    # --- sources ----------------------------------------------------------------
    sources = sorted({f.get("agent_name", "") for f in accepted if f.get("agent_name")})

    report = {
        "title": title or query or "Investigation report",
        "summary": narrative,
        "confidence": confidence_pct,
        "risk_level": risk_level,
        "key_findings": key_findings,
        "supporting_evidence": supporting_evidence,
        "recommendations": recommendations[:5],
        "metrics": metrics,
        "entities": entities[:25],
        "timeline": timeline[:10],
        "sources": sources,
        # Priority 25/28/30 — see _empty_report's identical field for why.
        "language": language,
    }
    if language != "en":
        report = _localize_executive_report(report, final_report, language)
    return report


def _localize_executive_report(report: dict, final_report: dict, language: str) -> dict:
    """Batch-localizes this module's deterministic presentation-layer
    prose (title/key_findings/supporting_evidence/recommendations/
    timeline labels) into `language`. None of it comes from an LLM, so
    "generate natively" doesn't apply the way it does to ChiefAgent's
    narrative — translating the already-computed strings (same
    mechanism `_localize_report` uses for specialist-agent finding
    summaries in backend/api/investigation_stream.py) is the correct
    fix here, not a re-implementation.

    `summary` is skipped when it's already native — it's a verbatim
    copy of `final_report["narrative"]`, which `ChiefAgent` may have
    generated directly in `language` already (see
    `final_report["narrative_language"]`); re-translating it would
    garble an already-correct narrative. `metrics` (numeric, keyed by
    machine-readable names the frontend matches on) and `entities`
    (type/id pairs, not prose) are never touched, same as
    `_localize_report` leaves finding metadata untouched. `sources`
    (agent names) and `timeline[].agent` are proper nouns and are left
    alone too.

    Best-effort: on any translation failure, returns `report` unchanged
    (English) — same degrade-to-original contract every other
    `TranslationService` caller in this codebase follows.
    """
    from backend.language.translation_service import TranslationService

    already_native_summary = final_report.get("narrative_language") == language
    key_findings = report["key_findings"]
    supporting_evidence = report["supporting_evidence"]
    recommendations = report["recommendations"]
    timeline_labels = [t["label"] for t in report["timeline"]]

    texts: list[str] = []
    if not already_native_summary and report["summary"]:
        texts.append(report["summary"])
    texts.append(report["title"])
    texts.extend(key_findings)
    texts.extend(supporting_evidence)
    texts.extend(recommendations)
    texts.extend(timeline_labels)

    try:
        results = TranslationService().batch_translate(texts, target_language=language, source_language="en")
    except Exception:
        logger.warning("Executive-report localization to %s failed; returning English text", language, exc_info=True)
        return report

    translated = [r.text for r in results]
    i = 0
    if not already_native_summary and report["summary"]:
        report["summary"] = translated[i]
        i += 1
    report["title"] = translated[i]
    i += 1
    n = len(key_findings)
    report["key_findings"] = translated[i:i + n]
    i += n
    n = len(supporting_evidence)
    report["supporting_evidence"] = translated[i:i + n]
    i += n
    n = len(recommendations)
    report["recommendations"] = translated[i:i + n]
    i += n
    n = len(timeline_labels)
    for entry, new_label in zip(report["timeline"], translated[i:i + n]):
        entry["label"] = new_label

    return report
