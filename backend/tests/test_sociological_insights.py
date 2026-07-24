"""
SHERLOCK — Agent 2 (Sociological Crime Insights) test coverage.

Covers: SociologicalInsightsService (the deterministic analytics engine),
SociologicalIntelligenceAgent (the pipeline-facing wrapper), and the
GET /analytics/sociological[/report] endpoints. Does NOT re-test the full
LangGraph pipeline — see test_orchestrator_pipeline.py for that; this
file exercises the new module directly plus its HTTP surface.
"""

from backend.database.models import Accused
from backend.intelligence.sociological_insights import SociologicalInsightsService


def test_dashboard_has_real_sample_size(db_session):
    svc = SociologicalInsightsService(db_session)
    dashboard = svc.build_dashboard()

    assert dashboard["scope"]["accused_sample_size"] > 0
    assert dashboard["demographics"]["accused"]["sample_size"] == dashboard["scope"]["accused_sample_size"]
    # Every accused person has gender/age recorded — distributions must sum to the sample size.
    assert sum(dashboard["demographics"]["accused"]["gender_distribution"].values()) == dashboard["scope"]["accused_sample_size"]


def test_unavailable_dimensions_are_reported_not_fabricated(db_session):
    svc = SociologicalInsightsService(db_session)
    dashboard = svc.build_dashboard()

    for dim in ("urbanization_analysis", "migration_analysis", "economic_stress_analysis", "education_analysis"):
        assert dashboard[dim]["available"] is False
        assert "reason" in dashboard[dim]

    availability = dashboard["data_availability"]
    assert availability["income_group"] == "unavailable"
    assert availability["age"] == "available"


def test_extension_point_produces_real_output_when_fed_data(db_session):
    """The urbanization placeholder is a real interface, not just a stub
    — feeding it a classification should produce a real correlation, not
    another 'unavailable' response."""
    svc = SociologicalInsightsService(db_session)
    from backend.database.models import Location

    districts = [d for (d,) in db_session.query(Location.district).distinct().all()]
    classification = {d: ("urban" if i % 2 == 0 else "rural") for i, d in enumerate(districts)}

    result = svc.urbanization_analysis(classification)
    assert result["available"] is True
    assert sum(result["crime_count_by_urbanization_tier"].values()) > 0


def test_social_risk_factors_are_internally_consistent(db_session):
    svc = SociologicalInsightsService(db_session)
    dashboard = svc.build_dashboard()
    risk = dashboard["social_risk_factors"]

    # Repeat offenders computed here must be a subset of all accused persons.
    all_accused_ids = {row[0] for row in db_session.query(Accused.person_id).distinct().all()}
    assert set(risk["repeat_offender_communities"]["person_ids"]).issubset(all_accused_ids)

    # Every district in the vulnerability breakdown must have a positive crime count.
    for entry in risk["community_vulnerability"]["by_district_crime_density"]:
        assert entry["crime_count"] > 0


def test_scoping_to_a_person_subset_narrows_results(db_session):
    svc = SociologicalInsightsService(db_session)
    all_ids = sorted({row[0] for row in db_session.query(Accused.person_id).distinct().all()})
    assert len(all_ids) >= 2

    subset = all_ids[:1]
    scoped = svc.build_dashboard(accused_person_ids=subset)
    full = svc.build_dashboard()

    assert scoped["scope"]["accused_sample_size"] <= full["scope"]["accused_sample_size"]
    assert scoped["scope"]["scoped_to_investigation"] is True
    assert full["scope"]["scoped_to_investigation"] is False


def test_report_has_the_seven_required_sections(db_session):
    svc = SociologicalInsightsService(db_session)
    report = svc.build_report()

    for key in ("executive_summary", "key_findings", "risk_factors", "evidence", "recommendations", "confidence", "supporting_data"):
        assert key in report

    assert isinstance(report["key_findings"], list) and report["key_findings"]
    assert 0.0 <= report["confidence"]["score"] <= 1.0
    # Supporting data must trace back to the same dashboard shape — no
    # summary claim without an underlying number to check it against.
    assert "social_risk_factors" in report["supporting_data"]


def test_agent_emits_demographic_and_risk_findings(db_session):
    from backend.agents.sociological_intelligence.agent import SociologicalIntelligenceAgent

    agent = SociologicalIntelligenceAgent(db_session)
    findings = agent.run({"graph_context": {}})

    finding_types = {f.finding_type for f in findings}
    assert "sociological_profile" in finding_types
    assert "social_risk_factors" in finding_types
    for f in findings:
        assert f.confidence > 0
        assert f.summary


def test_sociological_dashboard_endpoint(api_client):
    resp = api_client.get("/analytics/sociological")
    assert resp.status_code == 200
    body = resp.json()
    assert "demographics" in body
    assert "social_risk_factors" in body
    assert "correlation_matrix" in body


def test_sociological_report_endpoint(api_client):
    resp = api_client.get("/analytics/sociological/report")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "executive_summary", "key_findings", "risk_factors", "evidence",
        "recommendations", "confidence", "supporting_data",
    }
