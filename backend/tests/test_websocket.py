"""
WebSocket protocol test (/ws/investigate) — checklist item 6 ("websocket
protocol") and item 2 ("websocket events", "completion events").

Uses FastAPI's TestClient websocket support (Starlette under the hood),
so this runs the *real* stream_investigation() coroutine, not a mock.
"""

VALID_EVENT_TYPES = {
    "investigation_started", "agent_started", "agent_completed",
    "agent_skipped", "finding_produced", "validation_complete",
    "report_ready", "error",
}


def test_websocket_emits_started_then_report_ready(api_client):
    with api_client.websocket_connect("/ws/investigate") as ws:
        ws.send_json({"query": "Show repeat burglary offenders."})

        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["event_type"] in ("report_ready", "error"):
                break

    assert events[0]["event_type"] == "investigation_started"
    assert events[-1]["event_type"] == "report_ready", (
        "pipeline did not reach report_ready — last event was "
        f"{events[-1]!r}"
    )
    for event in events:
        assert event["event_type"] in VALID_EVENT_TYPES
        assert "timestamp" in event


def test_websocket_rejects_empty_query_without_crashing(api_client):
    with api_client.websocket_connect("/ws/investigate") as ws:
        ws.send_json({"query": "   "})
        event = ws.receive_json()
    assert event["event_type"] == "error"
    assert "Empty query" in event["message"]


def test_websocket_agent_completed_events_carry_findings_payload(api_client):
    """
    The frontend's activity feed and findings board render off of
    `data.new_findings` / `data.validated_findings` on agent_completed
    events — confirm that shape survives the full pipeline, not just the
    final report.
    """
    with api_client.websocket_connect("/ws/investigate") as ws:
        ws.send_json({"query": "Show money trail linked to fraud."})
        agent_events = []
        while True:
            event = ws.receive_json()
            if event["event_type"] in ("agent_completed", "agent_skipped"):
                agent_events.append(event)
            if event["event_type"] in ("report_ready", "error"):
                break

    assert agent_events, "expected at least one agent_completed/agent_skipped event"
    for event in agent_events:
        assert "data" in event
        assert "new_findings" in event["data"]
        assert "validated_findings" in event["data"]
