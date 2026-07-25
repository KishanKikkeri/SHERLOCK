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


# -- Priority 25/28/30: localization ----------------------------------------
#
# These stub out TranslationService.batch_translate so the assertions
# don't depend on ANTHROPIC_API_KEY being set — they check *which*
# strings get sent for translation and *where the results land back*,
# not translation quality.

class _StubResult:
    def __init__(self, text):
        self.text = text
        self.warnings = []


def _stub_batch_translate(monkeypatch):
    calls = {}

    def fake_batch_translate(self, texts, target_language, source_language="en"):
        calls["texts"] = list(texts)
        return [_StubResult(f"[{target_language}] {t}") for t in texts]

    monkeypatch.setattr(
        "backend.language.translation_service.TranslationService.batch_translate",
        fake_batch_translate,
    )
    return calls


def _sample_final_report(**overrides):
    base = {
        "query": "who is connected to Ravi Kumar",
        "narrative": "Ravi Kumar has 3 known associates.",
        "findings": [_finding(summary="Retrieved 5 FIRs.", evidence=["Month 3: arrest"])],
        "rejected_findings": [],
        "agents_consulted": ["CrimeRecords"],
    }
    base.update(overrides)
    return base


def test_language_en_never_calls_translator(monkeypatch):
    calls = _stub_batch_translate(monkeypatch)
    build_executive_report(_sample_final_report(), language="en")
    assert calls == {}


def test_language_kn_localizes_prose_fields(monkeypatch):
    calls = _stub_batch_translate(monkeypatch)
    report = build_executive_report(_sample_final_report(narrative_language="en"), language="kn")

    assert report["summary"] == "[kn] Ravi Kumar has 3 known associates."
    assert report["title"] == "[kn] who is connected to Ravi Kumar"
    assert report["key_findings"] == ["[kn] Retrieved 5 FIRs."]
    assert report["timeline"][0]["label"] == "[kn] Month 3: arrest"
    # summary WAS sent for translation since narrative_language != "kn"
    assert "Ravi Kumar has 3 known associates." in calls["texts"]


def test_already_native_narrative_is_not_retranslated(monkeypatch):
    calls = _stub_batch_translate(monkeypatch)
    report = build_executive_report(
        _sample_final_report(narrative="ರವಿ ಕುಮಾರ್‌ಗೆ 3 ಪರಿಚಿತರಿದ್ದಾರೆ.", narrative_language="kn"),
        language="kn",
    )
    # narrative_language already matches the requested language, so the
    # summary is passed through untouched rather than sent back through
    # the EN->KN translator (which would garble already-Kannada text).
    assert report["summary"] == "ರವಿ ಕುಮಾರ್‌ಗೆ 3 ಪರಿಚಿತರಿದ್ದಾರೆ."
    assert "ರವಿ ಕುಮಾರ್‌ಗೆ 3 ಪರಿಚಿತರಿದ್ದಾರೆ." not in calls["texts"]
    # everything else (title, key_findings, ...) still gets localized
    assert report["title"] == "[kn] who is connected to Ravi Kumar"


def test_metrics_entities_and_sources_are_never_translated(monkeypatch):
    _stub_batch_translate(monkeypatch)
    report = build_executive_report(
        _sample_final_report(findings=[_finding(summary="x", source_entities=["person_1"],
                                                  metadata={"count": 3})]),
        language="kn",
    )
    assert report["metrics"]["count"] == 3
    assert report["entities"] == [{"type": "person", "id": "person_1"}]
    assert report["sources"] == ["TestAgent"]


def test_empty_report_is_also_localized(monkeypatch):
    calls = _stub_batch_translate(monkeypatch)
    report = build_executive_report(_sample_final_report(findings=[]), language="kn")
    assert report["key_findings"] == []
    assert report["recommendations"][0].startswith("[kn]")
    assert calls  # translator was actually invoked for the empty-report fallback text


def test_translation_failure_degrades_to_english(monkeypatch):
    def raising_batch_translate(self, texts, target_language, source_language="en"):
        raise RuntimeError("simulated translation outage")

    monkeypatch.setattr(
        "backend.language.translation_service.TranslationService.batch_translate",
        raising_batch_translate,
    )
    report = build_executive_report(_sample_final_report(), language="kn")
    # Degrades to the original English report rather than raising.
    assert report["summary"] == "Ravi Kumar has 3 known associates."
    assert report["key_findings"] == ["Retrieved 5 FIRs."]
