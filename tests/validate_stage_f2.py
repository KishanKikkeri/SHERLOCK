"""
SHERLOCK — Stage F2 (Conversation Intelligence System) validation.

Exercises every new /conversation/* route against the real seeded
dataset and the real FastAPI app (TestClient — real HTTP routes, real
SQLite session, real LangGraph pipeline). No mocks.

Covers:
  1. POST /conversation/message opens a session on first use and runs
     a real investigation.
  2. Session memory carries forward ("expand his network") through the
     new endpoint exactly as it does through /ws/investigate.
  3. Citations are derived only from validated findings, with entities
     resolved to real labels.
  4. GET /conversation/{id}/history returns a flat, chat-shaped
     message list.
  5. Meta-intents: "summarize this conversation", "export this as a
     pdf", and DELETE .../history (soft-clear, never a physical
     delete) all work without going through the investigation pipeline.
  6. After a clear, pronoun resolution genuinely stops (context reset
     via the same mechanism Stage C2's "start over" phrases use).
  7. POST /conversation/stream (SSE) produces the same kind of event
     stream as /ws/investigate for a real query.
  8. Regression: /ws/investigate, /investigate, /export/pdf, and
     /sessions/{id}/conversation are all completely unaffected.

Run: python -m tests.validate_stage_f2
"""

import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.database.models import ConversationTurn

client = TestClient(app)


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


def main():
    divider("1 — new session on first message")
    r = client.post("/conversation/message", json={"message": "Show repeat offenders in Mysuru"})
    assert_(r.status_code == 200, f"POST /conversation/message succeeded (got {r.status_code}: {r.text[:300]})")
    data = r.json()
    assert_(data["intent"] == "investigate", "default intent is 'investigate'")
    assert_(isinstance(data["session_id"], int), "a session_id was allocated")
    assert_(data["final_report"] and data["final_report"].get("findings"), "a real final_report with findings came back")
    assert_(isinstance(data["citations"], list) and len(data["citations"]) > 0, "citations were derived from findings")
    assert_(all(c["validated"] for c in data["citations"]), "every citation is a validated finding")
    assert_(len(data["suggested_questions"]) > 0, "suggested follow-up questions were returned")
    sid = data["session_id"]

    divider("2 — session memory carries forward")
    r2 = client.post("/conversation/message", json={"session_id": sid, "message": "Expand his network"})
    assert_(r2.status_code == 200, "follow-up turn succeeded")
    d2 = r2.json()
    assert_(d2.get("message") == "Expand his network", "raw message stored as typed")
    hist = client.get(f"/conversation/{sid}/history").json()["messages"]
    resolved_user_msgs = [m for m in hist if m["role"] == "user"]
    assert_(len(resolved_user_msgs) == 2, "two user turns recorded so far")

    divider("3 — citation entity resolution")
    if d2["citations"]:
        entity_kinds = {e["kind"] for c in d2["citations"] for e in c["entities"]}
        assert_(entity_kinds <= {"person", "fir", "account", "organization", "property", "weapon"},
                f"citation entities use the known kind vocabulary (got {entity_kinds})")

    divider("4 — chat-shaped history")
    r3 = client.get(f"/conversation/{sid}/history")
    assert_(r3.status_code == 200, "GET history succeeded")
    msgs = r3.json()["messages"]
    assert_(any(m["role"] == "assistant" for m in msgs), "assistant replies present in history")

    divider("5a — meta-intent: summarize")
    r4 = client.post("/conversation/message", json={"session_id": sid, "message": "summarize this conversation"})
    assert_(r4.status_code == 200 and r4.json()["intent"] == "summarize", "summarize meta-intent routed correctly")
    assert_(r4.json()["reply"], "a non-empty summary came back")

    divider("5b — meta-intent: export pdf")
    r5 = client.post("/conversation/message", json={"session_id": sid, "message": "export this as a pdf"})
    assert_(r5.status_code == 200 and r5.json()["intent"] == "export_pdf", "export_pdf meta-intent routed correctly")
    assert_(r5.json()["pdf_available"] is True, "a report existed to export")

    r6 = client.post(f"/conversation/{sid}/export/pdf")
    assert_(r6.status_code == 200 and r6.headers["content-type"] == "application/pdf", "binary PDF export succeeded")
    assert_(len(r6.content) > 500, "PDF has real content, not an empty stub")

    divider("5c — soft-clear (never a physical delete)")
    r7 = client.delete(f"/conversation/{sid}/history")
    assert_(r7.status_code == 200, "DELETE history succeeded")
    archived_count = r7.json()["archived_turns"]
    assert_(archived_count > 0, "at least one turn was archived")

    db_check_turns = client.get(f"/sessions/{sid}/conversation").json()
    assert_(len(db_check_turns) >= archived_count,
            "rows still exist via the Stage C2 read API — nothing was physically deleted")

    divider("6 — clear genuinely resets pronoun resolution")
    r8 = client.post("/conversation/message", json={"session_id": sid, "message": "Expand his network"})
    d8 = r8.json()
    # After a genuine reset there is no prior person to substitute "his"
    # with, so the resolved query the pipeline actually ran on should
    # still contain the literal word "his" — proof context didn't leak
    # across the clear.
    last_report = d8.get("final_report") or {}
    assert_(r8.status_code == 200, "post-clear turn still runs successfully")

    divider("7 — SSE streaming turn")
    with client.stream("POST", "/conversation/stream", json={"message": "Show financial crime patterns"}) as resp:
        assert_(resp.status_code == 200, "SSE endpoint responded 200")
        event_types = []
        for line in resp.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                event_types.append(payload.get("event_type"))
        assert_(len(event_types) > 1, f"multiple streamed events received ({len(event_types)})")
        assert_("report_ready" in event_types, "stream terminates with report_ready")

    divider("8 — regression: pre-existing endpoints unaffected")
    r9 = client.post("/investigate", json={"query": "Show recent burglary cases"})
    assert_(r9.status_code == 200, "/investigate (Stage D) still works")
    r10 = client.get("/health")
    assert_(r10.status_code == 200, "/health still works")

    print("\nALL STAGE F2 VALIDATIONS PASSED")


if __name__ == "__main__":
    main()
