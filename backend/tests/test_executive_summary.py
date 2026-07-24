"""
Tests for backend/intelligence/executive_summary.py — the presentation
layer transform between a Chief-Agent `final_report` and the structured
Analytics card schema. No orchestration graph involved; these operate on
plain dicts shaped like real `synthesis_node` output.
"""

from backend.intelligence.executive_summary import build_executive_report


def _finding(**overrides):
    base = {
        "agent_name": "TestAgent",
        "finding_type": "crime_pattern",
        "summary": "Some validated finding.",
        "evidence": [],
        "confidence": 0.6,
        "source_entities": [],
        "metadata": {},
        "validated": True,
        "reasoning": "",
        "related_documents": [],
    }
    base.update(overrides)
    return base


def test_no_accepted_findings_returns_safe_empty_report():
    report = build_executive_report({
        "query": "Any repeat offenders in district X?",
        "narrative": "No validated findings were available.",
        "findings": [],
        "rejected_findings": [_finding(validated=False, confidence=0.2)],
        "agents_consulted": ["NetworkAnalysisAgent"],
    })

    assert report["title"] == "Any repeat offenders in district X?"
    assert report["confidence"] == 0
    assert report["risk_level"] == "Unknown"
    assert report["key_findings"] == []
    assert report["metrics"]["findings_rejected"] == 1
    assert report["sources"] == ["NetworkAnalysisAgent"]


def test_key_findings_are_ranked_by_confidence_desc():
    report = build_executive_report({
        "query": "q",
        "narrative": "n",
        "findings": [
            _finding(summary="low", confidence=0.3),
            _finding(summary="high", confidence=0.9),
            _finding(summary="mid", confidence=0.6),
        ],
        "rejected_findings": [],
        "agents_consulted": ["TestAgent"],
    })
    assert report["key_findings"][0] == "high"
    assert report["key_findings"][-1] == "low"


def test_supporting_evidence_counts_entities_instead_of_dumping_rows():
    report = build_executive_report({
        "query": "q",
        "narrative": "n",
        "findings": [
            _finding(source_entities=["person_1", "person_2", "location_belagavi"],
                     related_documents=["FIR-1"]),
        ],
        "rejected_findings": [],
        "agents_consulted": ["TestAgent"],
    })
    assert "2 person(s) of interest" in report["supporting_evidence"]
    assert "1 location(s)" in report["supporting_evidence"]
    assert "1 linked case document(s)" in report["supporting_evidence"]
    # Never a raw per-row dump of the underlying findings/evidence
    assert "person_1" not in " ".join(report["supporting_evidence"])


def test_decision_support_findings_become_recommendations_verbatim():
    report = build_executive_report({
        "query": "q",
        "narrative": "n",
        "findings": [
            _finding(finding_type="decision_support", summary="Escalate to district magistrate.", confidence=0.8),
            _finding(finding_type="crime_pattern", summary="unrelated pattern", confidence=0.5),
        ],
        "rejected_findings": [],
        "agents_consulted": ["DecisionSupportAgent"],
    })
    assert report["recommendations"] == ["Escalate to district magistrate."]


def test_timeline_only_pulled_from_month_prefixed_evidence():
    report = build_executive_report({
        "query": "q",
        "narrative": "n",
        "findings": [
            _finding(evidence=["Month 2026-01: 4 case(s)", "unrelated evidence line"]),
        ],
        "rejected_findings": [],
        "agents_consulted": ["ForecastingAgent"],
    })
    assert len(report["timeline"]) == 1
    assert report["timeline"][0]["label"] == "Month 2026-01: 4 case(s)"


def test_numeric_metadata_surfaces_in_metrics_without_duplicating_keys():
    report = build_executive_report({
        "query": "q",
        "narrative": "n",
        "findings": [
            _finding(metadata={"projected_next_month": 14, "district": "Belagavi"}),
        ],
        "rejected_findings": [],
        "agents_consulted": ["ForecastingAgent"],
    })
    assert report["metrics"]["projected_next_month"] == 14
    # non-numeric metadata (e.g. "district") is not pulled into metrics
    assert "district" not in report["metrics"]
