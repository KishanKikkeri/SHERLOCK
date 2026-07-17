"""
SHERLOCK — Stage C4 Sprint 3 validation.

Two kinds of checks, both against the real seeded database and real
FastAPI app:

1. A natural, full end-to-end run with `enable_discussion=True` — proves
   opinions/consensus/streaming/persistence all work on real pipeline
   output, no mocks.
2. A constructed scenario (real Person/FIR ids from the seeded DB, but
   deliberately opposed synthetic findings) to prove the disagreement
   detector actually fires — because, as this validation itself
   discovered, this deterministic rule-based agent set essentially never
   produces genuine >35%-confidence-spread disagreement naturally (see
   the sprint report for the actual observed spread distribution: max
   0.25 across 152 real multi-agent entity groups in one full run).
   That's an honest finding about the dataset/agents, not something to
   paper over by lowering the threshold until noise looks like debate.

Run: python validate_c4_sprint3.py
"""
import asyncio
import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.database.models import Person, FIR
from backend.api.investigation_stream import stream_investigation
from backend.discussion.engine import DiscussionEngine, AgentOpinion

client = TestClient(app)


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


async def run(query, session_id=None, enable_discussion=False):
    events = []

    async def collect(e):
        events.append(e)

    await stream_investigation(query, collect, session_id=session_id, enable_discussion=enable_discussion)
    return events


def main():
    db = SessionLocal()
    svc = DatabaseService(db)
    session_row = svc.open_case(title="C4 Sprint 3 validation case")
    sid = session_row.id
    print(f"Opened InvestigationSession id={sid}")

    # -----------------------------------------------------------------
    # Regression: enable_discussion defaults to False, must be inert
    # -----------------------------------------------------------------
    divider("Regression — discussion mode off by default")
    events = asyncio.run(run("Show repeat burglary offenders in Mysuru"))
    assert_(any(e["event_type"] == "report_ready" for e in events), "plain call still produces a report")
    assert_(not any(e["event_type"].startswith("discussion_") for e in events),
            "no discussion_* events sent when enable_discussion is omitted")

    # -----------------------------------------------------------------
    # Full natural run with discussion enabled
    # -----------------------------------------------------------------
    divider("Natural end-to-end run with enable_discussion=True")
    events = asyncio.run(run("Show repeat offenders in Mysuru", session_id=sid, enable_discussion=True))
    assert_(any(e["event_type"] == "discussion_started" for e in events), "discussion_started event sent")
    opinion_events = [e for e in events if e["event_type"] == "discussion_opinion"]
    consensus_events = [e for e in events if e["event_type"] == "discussion_consensus"]
    print(f"  {len(opinion_events)} opinion events streamed")
    assert_(len(opinion_events) > 0, "at least one agent opinion streamed")
    assert_(len(consensus_events) == 1, "exactly one consensus event streamed")
    consensus = consensus_events[0]["data"]
    print(f"  overall_confidence={consensus['overall_confidence']} "
          f"consensus_score={consensus['consensus_score']} "
          f"agreement={consensus['agreement_count']} disagreement={consensus['disagreement_count']}")
    assert_(0.0 <= consensus["overall_confidence"] <= 1.0, "overall_confidence is a valid probability")
    assert_(0.0 <= consensus["consensus_score"] <= 1.0, "consensus_score is a valid probability")
    print(f"  recommended_conclusion: {consensus_events[0]['message'][:150]!r}")

    report_event = next(e for e in events if e["event_type"] == "report_ready")
    assert_(report_event["data"]["final_report"], "Chief's own final_report is unaffected/still present")

    # Persistence
    resp = client.get(f"/sessions/{sid}/discussions")
    assert_(resp.status_code == 200, "GET /sessions/{id}/discussions returns 200")
    records = resp.json()
    assert_(len(records) == 1, "exactly one DiscussionRecord persisted for this turn")
    rec = records[0]
    assert_(rec["query"] == "Show repeat offenders in Mysuru", "persisted record has the right query")
    assert_(len(rec["opinions"]) == len(opinion_events), "persisted opinions match streamed opinions")
    assert_(rec["consensus"]["overall_confidence"] == consensus["overall_confidence"],
            "persisted consensus matches streamed consensus")

    resp2 = client.get(f"/discussions/{rec['id']}")
    assert_(resp2.status_code == 200 and resp2.json()["id"] == rec["id"], "GET /discussions/{id} returns the same record")

    # -----------------------------------------------------------------
    # Constructed disagreement scenario (real entities, synthetic opposed findings)
    # -----------------------------------------------------------------
    divider("Constructed disagreement scenario")
    real_person = db.query(Person).first()
    findings = [
        {"agent_name": "FinancialAgent", "finding_type": "fraud_assessment",
         "summary": f"No suspicious transaction pattern found for {real_person.name}.",
         "evidence": ["Account transaction history reviewed, no flags."],
         "confidence": 0.85, "source_entities": [f"person_{real_person.id}"], "validated": True},
        {"agent_name": "BehavioralIntelligence", "finding_type": "behavioral_risk",
         "summary": f"{real_person.name} shows high-risk behavioral indicators.",
         "evidence": ["Repeat association with flagged individuals."],
         "confidence": 0.30, "source_entities": [f"person_{real_person.id}"], "validated": True},
        # A finding with no evidence at all -> missing_evidence, an implicit "need more data" signal.
        {"agent_name": "WitnessIntelligence", "finding_type": "witness_review",
         "summary": f"Insufficient witness statements on record for {real_person.name}.",
         "evidence": [], "confidence": 0.0, "source_entities": [f"person_{real_person.id}"], "validated": False},
    ]
    engine = DiscussionEngine(session=db)
    opinions = engine.build_opinions(findings)
    assert_(len(opinions) == 3, "all 3 synthetic findings became opinions")
    missing = [o for o in opinions if o.missing_evidence]
    assert_(len(missing) == 1 and missing[0].agent_name == "WitnessIntelligence",
            "the no-evidence finding is flagged missing_evidence")

    disagreements = engine.detect_disagreements(opinions)
    assert_(len(disagreements) == 1, "FinancialAgent vs BehavioralIntelligence spread (0.55) triggers a disagreement")
    d = disagreements[0]
    assert_(d.entity_label == real_person.name, "disagreement resolved to the real person's actual name, not just an id")
    assert_(d.confidence_spread == 0.55, f"confidence spread computed correctly (got {d.confidence_spread})")
    print(f"  explanation: {d.explanation}")
    assert_(len(d.explanation) > 0, "a non-empty explanation was generated")
    assert_("FinancialAgent" in d.explanation and "BehavioralIntelligence" in d.explanation,
            "explanation names both disagreeing agents")

    consensus2 = engine.compute_consensus(opinions, disagreements)
    assert_(consensus2.disagreement_count == 1, "consensus reflects the one disagreement")
    assert_("WitnessIntelligence" in consensus2.evidence_requests,
            "consensus surfaces the agent that lacked evidence, as an evidence request")
    print(f"  evidence_requests: {consensus2.evidence_requests}")

    db.close()
    print("\nALL VALIDATIONS PASSED")


if __name__ == "__main__":
    main()
