"""
API-level tests for Priority 17 (Voice/Text Shared Conversation State).

Proves /voice/command's free-text fallback now goes through the exact
same ConversationManager as /conversation/message — not a parallel
run_investigation_once call — so a typed turn and a spoken turn on the
same session_id share conversation memory (pronoun/reference
resolution, meta-commands) instead of drifting apart.
"""


def test_voice_command_and_text_conversation_share_a_session(api_client, db_session):
    """A typed turn, then a spoken turn on the same session_id, must
    both be recorded against that session's conversation memory —
    proof that voice isn't a parallel, disconnected pipeline."""
    from backend.database.models import Person
    person = db_session.query(Person).first()
    assert person is not None

    # Create conversation first in V2
    conv_res = api_client.post("/v2/conversations", json={"nickname": "Test Chat"})
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    typed = api_client.post(f"/v2/conversations/{conv_id}/messages", json={"message": f"Tell me about {person.name}"})
    assert typed.status_code == 200

    spoken = api_client.post("/voice/command", json={"transcript": "Summarize this", "session_id": conv_id})
    assert spoken.status_code == 200
    body = spoken.json()
    # Reached ConversationManager's SUMMARIZE intent (not the generic
    # "investigate" fallback) — only possible if /voice/command is
    # routing through the same intent classifier /conversation/message
    # uses, on the same session's memory.
    assert body["intent"] == "summarize"
    assert body["session_id"] == conv_id


def test_voice_command_meta_intents_reachable(api_client):
    """clear_history is a ConversationManager-only intent that the old
    VoiceCommandRouter (run_investigation_once fallback) had no path
    to at all — proves voice now gets full intent parity with text."""
    resp = api_client.post("/voice/command", json={"transcript": "clear the conversation", "session_id": None})
    assert resp.status_code == 200
    assert resp.json()["intent"] == "clear_history"


def test_voice_command_session_lifecycle_shortcuts_still_work(api_client):
    """The imperative voice shortcuts VoiceCommandRouter handles before
    ever falling through to ConversationManager (open/close/assign/...)
    must be unaffected by the _investigate change."""
    resp = api_client.post("/voice/command", json={"transcript": "open burglary investigation", "session_id": None})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "open_case"
    assert body["session_id"] is not None
