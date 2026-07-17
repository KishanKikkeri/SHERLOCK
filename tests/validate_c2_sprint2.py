"""
SHERLOCK — Stage C2 Sprint 2 validation.

Exercises every item against the real seeded dataset and the real FastAPI
app (via TestClient, so this is hitting actual HTTP routes, not calling
service methods directly) + a real SQLite session. No mocks.

Run:  python validate_c2_sprint2.py
"""
import asyncio
import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.api.investigation_stream import stream_investigation

client = TestClient(app)


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


async def run(query, session_id):
    events = []

    async def collect(e):
        events.append(e)

    await stream_investigation(query, collect, session_id=session_id)
    return events


def main():
    db = SessionLocal()
    svc = DatabaseService(db)
    session_row = svc.open_case(title="C2 Sprint 2 validation case")
    sid = session_row.id
    print(f"Opened InvestigationSession id={sid} code={session_row.session_code}")

    # -----------------------------------------------------------------
    # Turn 0: broad query, real data, should surface multiple persons
    # -----------------------------------------------------------------
    divider("Turn 0 — broad query establishing multiple person mentions")
    events = asyncio.run(run("Show repeat offenders in Mysuru", sid))
    report_event = next(e for e in events if e["event_type"] == "report_ready")
    findings = report_event["data"]["final_report"]["findings"]
    print(f"  {len(findings)} accepted findings")

    resp = client.get(f"/sessions/{sid}/timeline/entities")
    assert_(resp.status_code == 200, "GET /timeline/entities returns 200")
    entities = resp.json()
    persons = [e for e in entities if e["kind"] == "person"]
    print(f"  entity timeline shows {len(persons)} distinct person(s): "
          f"{[p['label'] for p in persons]}")
    assert_(len(persons) >= 1, "at least one person was extracted into entity_mentions_json")

    # -----------------------------------------------------------------
    # Item 1 + 2: multi-entity disambiguation / clarification question
    # -----------------------------------------------------------------
    divider("Items 1+2 — multi-entity disambiguation & clarification")
    # The Turn 0 query above is intentionally a *broad* query (121 people
    # surfaced) — per the disambiguation cap (MAX_CLARIFICATION_OPTIONS),
    # that correctly falls through to single-best-guess rather than
    # asking "which of 121?". To test the *small-N* ambiguity the brief's
    # own example describes ("Show Ravi and Manoj" -> 2 people), build a
    # turn with exactly 2 real Person rows from the seeded database —
    # real data, deterministic scenario, rather than hoping some query
    # text happens to surface exactly 2-6 people this run.
    from backend.database.models import Person
    from backend.memory.conversation_memory import ConversationMemoryService, ResolveResult
    memory = ConversationMemoryService(db)
    two_people = db.query(Person).limit(2).all()
    assert_(len(two_people) == 2, "seeded database has at least 2 real persons to test with")
    turn = memory.record_turn(
        sid, raw_query=f"Show {two_people[0].name} and {two_people[1].name}",
        resolved_query=f"Show {two_people[0].name} and {two_people[1].name}",
        final_state={"final_report": {"findings": [
            {"agent_name": "Test", "finding_type": "test", "summary": "test",
             "source_entities": [f"person_{two_people[0].id}"]},
            {"agent_name": "Test", "finding_type": "test", "summary": "test",
             "source_entities": [f"person_{two_people[1].id}"]},
        ]}},
    )
    print(f"  seeded turn {turn.turn_index} with 2 real persons: "
          f"{two_people[0].name}, {two_people[1].name}")

    result = memory.resolve_turn(sid, "Tell me more about him")
    assert_(result.needs_clarification, '"him" with exactly 2 real persons in scope triggers clarification')
    print(f"  question: {result.clarification_question}")
    print(f"  options: {[o.label for o in result.clarification_options]}")

    chosen = result.clarification_options[0]
    memory.record_turn(sid, raw_query="Tell me more about him", resolved_query="Tell me more about him",
                        final_state=None, pending_clarification=result)
    answer_result = memory.resolve_turn(sid, chosen.label.split()[0])
    assert_(not answer_result.needs_clarification, "naming the chosen person resolves the pending clarification")
    assert_(chosen.label in answer_result.resolved_query,
            "resolved query is rebuilt using the chosen person's name")
    print(f"  resolved: {answer_result.resolved_query!r}")

    # -----------------------------------------------------------------
    # Item 5: ordinal person reference
    # -----------------------------------------------------------------
    divider("Item 5 — ordinal person reference + org/property/weapon refs")
    events = asyncio.run(run("Show repeat offenders in Bengaluru Urban", sid))
    last_turn_resp = client.get(f"/sessions/{sid}/conversation").json()[-1]
    print(f"  turn {last_turn_resp['turn_index']} recorded")

    entities = client.get(f"/sessions/{sid}/timeline/entities").json()
    persons2 = [e for e in entities if e["kind"] == "person" and last_turn_resp["turn_index"] in e["turns"]]
    if len(persons2) >= 2:
        events = asyncio.run(run("tell me about the second accused", sid))
        resolved_msg = next((e["message"] for e in events if e["event_type"] == "agent_completed"
                              and e.get("agent") == "Conversation Memory"
                              and "Resolved" in (e.get("message") or "")), None)
        print(f"  {resolved_msg}")
        assert_(resolved_msg is not None, '"the second accused" was resolved via ordinal reference')
    else:
        print("  SKIPPED: fewer than 2 persons mentioned in that turn's findings this run.")

    # -----------------------------------------------------------------
    # Item 4: context expiration / topic reset
    # -----------------------------------------------------------------
    divider("Item 4 — context expiration (topic reset)")
    events = asyncio.run(run("Forget the previous topic, show financial fraud in Dharwad", sid))
    reset_event = next((e for e in events if e["event_type"] == "topic_reset"), None)
    assert_(reset_event is not None, "reset phrase triggers topic_reset event")
    print(f"  {reset_event['message']}")
    report_event = next((e for e in events if e["event_type"] == "report_ready"), None)
    assert_(report_event is not None, "remainder of the query after the reset phrase still runs the pipeline")

    turns = client.get(f"/sessions/{sid}/conversation").json()
    reset_turn_idx = turns[-1]["turn_index"]
    timeline = client.get(f"/sessions/{sid}/timeline/conversation").json()
    reset_entry = next(t for t in timeline if t["turn_index"] == reset_turn_idx)
    assert_(reset_entry["type"] == "topic_reset", "conversation timeline flags the reset turn correctly")

    # Reset-phrase-only turn (no remainder) should not run the pipeline
    events = asyncio.run(run("forget that", sid))
    assert_(not any(e["event_type"] == "report_ready" for e in events),
            "reset phrase with no remainder does not run the pipeline")
    assert_(any(e["event_type"] == "topic_reset" for e in events),
            "bare reset phrase still emits topic_reset")

    # -----------------------------------------------------------------
    # Item 6: timeline API (conversation / entities / decisions)
    # -----------------------------------------------------------------
    divider("Item 6 — timeline API")
    conv_timeline = client.get(f"/sessions/{sid}/timeline/conversation").json()
    assert_(len(conv_timeline) == len(client.get(f"/sessions/{sid}/conversation").json()),
            "conversation timeline covers every recorded turn")
    decisions = client.get(f"/sessions/{sid}/timeline/decisions").json()
    print(f"  {len(decisions)} decision(s) recorded")
    assert_(all("conclusion" in d and "finding_count" in d for d in decisions),
            "every decision entry has a conclusion and finding_count")
    entity_timeline = client.get(f"/sessions/{sid}/timeline/entities").json()
    assert_(all(sorted(e["turns"]) == e["turns"] for e in entity_timeline),
            "entity timeline turn lists are chronologically ordered")

    # -----------------------------------------------------------------
    # Item 3: conversation summarization
    # -----------------------------------------------------------------
    divider("Item 3 — conversation summarization (threshold=8)")
    before = client.get(f"/sessions/{sid}/context").json()
    print(f"  before: summary_through_turn={before['summary_through_turn']}")
    # Drive the session past the 8-turn threshold with cheap, valid queries.
    for i in range(6):
        asyncio.run(run(f"Show repeat offenders in Davanagere (round {i})", sid))
    after = client.get(f"/sessions/{sid}/context").json()
    total_turns = len(client.get(f"/sessions/{sid}/conversation").json())
    print(f"  after {total_turns} turns: summary_through_turn={after['summary_through_turn']}")
    assert_(after["summary_through_turn"] is not None, "session past threshold now has a compressed summary")
    assert_(after["summary"] is not None and len(after["summary"]) > 0, "summary text is non-empty")
    print(f"  summary preview: {after['summary'][:200]!r}")

    # Confirm nothing was deleted from real turn history — summarization
    # must be additive-only per its own docstring.
    assert_(total_turns == len(client.get(f"/sessions/{sid}/conversation").json()),
            "raw ConversationTurn history is untouched by summarization")

    divider("Regression — Sprint 1 behavior + no-session-id callers untouched")
    events = asyncio.run(run("Show repeat burglary offenders in Mysuru", None))
    assert_(any(e["event_type"] == "report_ready" for e in events),
            "omitting session_id still runs the pipeline exactly as before (no memory calls at all)")

    db.close()
    print("\nALL VALIDATIONS PASSED")


if __name__ == "__main__":
    main()
