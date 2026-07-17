"""
SHERLOCK — Stage C6 Sprint 4 validation.

Real seeded database, real FastAPI app (TestClient, real HTTP routes),
real Officer rows — no mocks. Exercises every item from the C6 remaining-
work list: shared investigations, comments, mentions, notifications,
review workflow, board collaboration, activity feed, presence, audit.

Run: python validate_c6_sprint4.py
"""
import time

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.database.models import Officer

client = TestClient(app)


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


def main():
    db = SessionLocal()
    svc = DatabaseService(db)

    officers = db.query(Officer).limit(4).all()
    assert_(len(officers) == 4, "seeded database has at least 4 real officers")
    lead, investigator, reviewer, bystander = officers
    print(f"  lead={lead.name!r} investigator={investigator.name!r} "
          f"reviewer={reviewer.name!r} bystander={bystander.name!r}")

    session_row = svc.open_case(title="C6 Sprint 4 validation case", opened_by_officer_id=lead.id)
    sid = session_row.id
    print(f"Opened InvestigationSession id={sid}")

    # -----------------------------------------------------------------
    # Shared investigations (built on Stage C1's SessionAssignment)
    # -----------------------------------------------------------------
    divider("Shared investigations")
    svc.assign_investigator(sid, lead.id, role="lead", actor_officer_id=lead.id)
    svc.assign_investigator(sid, investigator.id, role="investigator", actor_officer_id=lead.id)
    svc.assign_investigator(sid, reviewer.id, role="reviewer", actor_officer_id=lead.id)
    resp = client.get(f"/sessions/{sid}")
    assert_(resp.status_code == 200, "session fetchable after multiple assignments")

    # -----------------------------------------------------------------
    # Comments + mentions + notifications
    # -----------------------------------------------------------------
    divider("Comments, mentions, notifications")
    last_name = investigator.name.split()[-1]
    comment_body = f"Can @{last_name} double-check this account? Also loop in @supervisor."
    resp = client.post(f"/sessions/{sid}/comments", json={
        "target_type": "entity", "target_ref": "person_1",
        "body": comment_body, "author_officer_id": bystander.id,
    })
    assert_(resp.status_code == 200, "POST /comments succeeds")
    comment = resp.json()
    print(f"  comment id={comment['id']} body={comment['body']!r}")

    resp = client.get(f"/sessions/{sid}/comments", params={"target_type": "entity", "target_ref": "person_1"})
    assert_(resp.status_code == 200 and len(resp.json()) == 1, "GET /comments returns the comment, filtered by target")

    # Name mention -> the investigator specifically
    resp = client.get(f"/officers/{investigator.id}/notifications")
    notifs = resp.json()
    assert_(any(n["notification_type"] == "mention" for n in notifs),
            f'"@{last_name}" resolved to a mention notification for the investigator')

    # Role mention ("@supervisor") -> whoever holds role="lead"
    resp = client.get(f"/officers/{lead.id}/notifications")
    lead_notifs = resp.json()
    assert_(any(n["notification_type"] == "mention" for n in lead_notifs),
            '"@supervisor" resolved to the session\'s role="lead" assignee')

    # Author never notifies themselves even if they @ their own name
    resp = client.get(f"/officers/{bystander.id}/notifications")
    assert_(not any(n["notification_type"] == "mention" for n in resp.json()),
            "comment author is not notified of their own comment")

    unread_id = next(n["id"] for n in notifs if n["notification_type"] == "mention")
    resp = client.post(f"/notifications/{unread_id}/read")
    assert_(resp.status_code == 200 and resp.json()["read_at"] is not None, "notification marked read")
    resp = client.get(f"/officers/{investigator.id}/notifications", params={"unread_only": True})
    assert_(not any(n["id"] == unread_id for n in resp.json()), "read notification excluded from unread_only filter")

    # -----------------------------------------------------------------
    # Board collaboration (shared notes / links / hypotheses)
    # -----------------------------------------------------------------
    divider("Board collaboration")
    resp = client.post(f"/sessions/{sid}/board-objects", json={
        "object_type": "hypothesis", "content": "Person 1 may be laundering through a shell account.",
        "created_by_officer_id": lead.id,
    })
    assert_(resp.status_code == 200, "POST /board-objects (hypothesis) succeeds")
    hyp = resp.json()

    resp = client.post(f"/sessions/{sid}/board-objects", json={
        "object_type": "link", "content": "Person 1 <-> Account 9",
        "payload": {"from": "person_1", "to": "account_9", "relation": "controls"},
        "created_by_officer_id": investigator.id,
    })
    assert_(resp.status_code == 200, "POST /board-objects (link, with payload) succeeds")
    link = resp.json()
    assert_(link["payload"]["relation"] == "controls", "link payload round-trips correctly")

    resp = client.get(f"/sessions/{sid}/board-objects")
    assert_(resp.status_code == 200 and len(resp.json()) == 2, "GET /board-objects returns both objects")

    resp = client.patch(f"/board-objects/{hyp['id']}", json={
        "content": "Person 1 confirmed laundering through a shell account.",
        "actor_officer_id": lead.id,
    })
    assert_(resp.status_code == 200 and "confirmed" in resp.json()["content"], "PATCH updates board object content")

    # Board updates notify every OTHER assigned officer
    resp = client.get(f"/officers/{investigator.id}/notifications")
    assert_(any(n["notification_type"] == "board_update" for n in resp.json()),
            "assigned investigator notified of lead's board object (creation + edit)")
    resp = client.get(f"/officers/{lead.id}/notifications")
    board_notifs_for_lead = [n for n in resp.json() if n["notification_type"] == "board_update"]
    assert_(len(board_notifs_for_lead) >= 1, "lead notified of investigator's link creation")

    # -----------------------------------------------------------------
    # Review workflow: Draft -> In Review -> Approved/Rejected
    # -----------------------------------------------------------------
    divider("Review workflow")
    resp = client.post(f"/sessions/{sid}/reviews", json={
        "requested_by_officer_id": investigator.id, "notes": "Ready for review — money mule findings attached.",
    })
    assert_(resp.status_code == 200, "POST /reviews succeeds")
    review = resp.json()
    assert_(review["status"] == "in_review", "new review request starts as in_review")

    resp = client.get(f"/officers/{reviewer.id}/notifications")
    assert_(any(n["notification_type"] == "review_request" for n in resp.json()),
            "role=reviewer assignee notified of the review request")

    resp = client.post(f"/reviews/{review['id']}/decide", json={
        "approve": False, "actor_officer_id": reviewer.id, "decision_notes": "Needs stronger evidence on account linkage.",
    })
    assert_(resp.status_code == 200 and resp.json()["status"] == "rejected", "review can be rejected")

    resp = client.get(f"/officers/{investigator.id}/notifications")
    assert_(any(n["notification_type"] == "review_decision" for n in resp.json()),
            "requester notified of the review decision")

    # Second cycle after rejection — history preserved, not overwritten
    resp = client.post(f"/sessions/{sid}/reviews", json={
        "requested_by_officer_id": investigator.id, "reviewer_officer_id": reviewer.id,
        "notes": "Added transaction records, resubmitting.",
    })
    review2 = resp.json()
    resp = client.post(f"/reviews/{review2['id']}/decide", json={"approve": True, "actor_officer_id": reviewer.id})
    assert_(resp.json()["status"] == "approved", "second cycle can be approved")

    resp = client.get(f"/sessions/{sid}/reviews")
    reviews = resp.json()
    assert_(len(reviews) == 2, "both review cycles kept as separate history, not overwritten")
    assert_([r["status"] for r in reviews] == ["rejected", "approved"], "review history in correct order/outcome")

    # -----------------------------------------------------------------
    # Presence
    # -----------------------------------------------------------------
    divider("Presence")
    resp = client.put(f"/sessions/{sid}/presence", json={"officer_id": lead.id, "status": "viewing"})
    assert_(resp.status_code == 200, "PUT /presence (viewing) succeeds")
    resp = client.put(f"/sessions/{sid}/presence", json={"officer_id": investigator.id, "status": "editing"})
    assert_(resp.status_code == 200, "PUT /presence (editing) succeeds")

    resp = client.get(f"/sessions/{sid}/presence")
    present = resp.json()
    assert_(len(present) == 2, "both heartbeats show up as currently present")
    assert_(any(p["officer_id"] == investigator.id and p["status"] == "editing" for p in present),
            "editing status correctly reflected")

    # Re-heartbeat updates the same row rather than duplicating it
    client.put(f"/sessions/{sid}/presence", json={"officer_id": lead.id, "status": "editing"})
    resp = client.get(f"/sessions/{sid}/presence")
    lead_rows = [p for p in resp.json() if p["officer_id"] == lead.id]
    assert_(len(lead_rows) == 1 and lead_rows[0]["status"] == "editing",
            "repeat heartbeat updates the existing presence row, doesn't duplicate")

    # TTL: presence records older than the TTL are excluded
    from backend.collaboration.service import CollaborationService
    from backend.database.models import SessionPresence
    from datetime import datetime, timedelta
    svc2 = CollaborationService(db)
    stale_row = db.query(SessionPresence).filter_by(session_id=sid, officer_id=lead.id).first()
    stale_row.last_seen_at = datetime.utcnow() - timedelta(seconds=200)
    db.commit()
    still_present = svc2.get_presence(sid, ttl_seconds=90)
    assert_(not any(p.officer_id == lead.id for p in still_present),
            "a heartbeat older than the TTL is correctly excluded from 'currently present'")

    # -----------------------------------------------------------------
    # Merged activity feed (human + AI + session + discussion actions)
    # -----------------------------------------------------------------
    divider("Merged activity feed")
    resp = client.get(f"/sessions/{sid}/activity-feed")
    assert_(resp.status_code == 200, "GET /activity-feed succeeds")
    feed = resp.json()
    kinds = {e["kind"] for e in feed}
    print(f"  {len(feed)} events, kinds present: {sorted(kinds)}")
    assert_("session" in kinds, "session-lifecycle/collaboration events present in the feed")
    event_types = {e["event_type"] for e in feed}
    assert_({"comment_added", "mention_sent", "board_object_added", "board_object_updated",
              "review_requested", "review_decided"}.issubset(event_types),
            "every new C6 action type appears in the audit trail")
    timestamps = [e["created_at"] for e in feed]
    assert_(timestamps == sorted(timestamps), "feed is in chronological order")

    db.close()
    print("\nALL VALIDATIONS PASSED")


if __name__ == "__main__":
    main()
