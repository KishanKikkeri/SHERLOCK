"""
SHERLOCK — Stage F2: Conversation Intelligence System (CIS) chat API.

Distinct from `backend/api/conversation.py` (Stage C2's read-only
history/timeline API, mounted under `/sessions/{id}/...`) — this router
is the *write* side: it's what the new unified frontend Conversation
screen actually talks to when someone sends a message. Mounted under
`/conversation` per the original CIS proposal:

    POST   /conversation/message              One turn, non-streaming
    POST   /conversation/stream               One turn, streamed (SSE)
    GET    /conversation/{session_id}/history  Chat-shaped turn history
    POST   /conversation/{session_id}/summarize
    POST   /conversation/{session_id}/export/pdf
    DELETE /conversation/{session_id}/history  Soft-clear (see manager.py)

`/ws/investigate` (backend/app/main.py) remains the primary live
streaming transport and is unchanged — `/conversation/stream` exists
for clients that would rather not manage a WebSocket (plain fetch,
curl, environments where WS is awkward), backed by the exact same
`stream_investigation` pipeline via `ConversationManager.stream_events`.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response as FastAPIResponse, StreamingResponse
from pydantic import BaseModel

from backend.conversation.manager import ConversationManager
from backend.database.config import SessionLocal
from backend.database.models import AuditAction
from backend.memory.conversation_memory import ConversationMemoryService
from backend.security import audit as security_audit
from backend.security.dependencies import AuthContext
from backend.security.permissions import RequirePermission, EXPORT_PDF, RUN_INVESTIGATION, VIEW_CASE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversation", tags=["conversation-engine"])


class MessageRequest(BaseModel):
    session_id: int | None = None
    message: str
    language: str | None = None
    enable_discussion: bool = False


# ---------------------------------------------------------------------------
# POST /conversation/message — non-streaming turn
# ---------------------------------------------------------------------------

@router.post("/message")
async def post_message(payload: MessageRequest, ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION))):
    if payload.language is not None and payload.language not in ("en", "kn"):
        raise HTTPException(status_code=422, detail="language must be 'en' or 'kn' if provided.")

    db = SessionLocal()
    try:
        manager = ConversationManager(db)
        result = await manager.handle_message(
            payload.session_id, payload.message,
            officer_id=ctx.officer_id, language=payload.language,
            enable_discussion=payload.enable_discussion,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        logger.exception("POST /conversation/message failed")
        raise HTTPException(status_code=500, detail="Conversation turn failed.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /conversation/stream — SSE turn
# ---------------------------------------------------------------------------

@router.post("/stream")
async def post_stream(payload: MessageRequest, ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION))):
    if payload.language is not None and payload.language not in ("en", "kn"):
        raise HTTPException(status_code=422, detail="language must be 'en' or 'kn' if provided.")

    async def event_source():
        db = SessionLocal()
        try:
            manager = ConversationManager(db)
            async for event in manager.stream_events(
                payload.session_id, payload.message,
                officer_id=ctx.officer_id, language=payload.language,
                enable_discussion=payload.enable_discussion,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception("POST /conversation/stream failed")
            yield f"data: {json.dumps({'event_type': 'error', 'message': str(e)})}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_source(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /conversation/{session_id}/history — chat-shaped turn history
# ---------------------------------------------------------------------------

@router.get("/{session_id}/history")
def get_chat_history(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    """Same underlying `ConversationTurn` rows as
    `GET /sessions/{id}/conversation` (backend/api/conversation.py), but
    reshaped into a flat user/assistant message list a chat UI can render
    directly instead of re-deriving that shape client-side."""
    db = SessionLocal()
    try:
        memory = ConversationMemoryService(db)
        turns = memory.get_history(session_id)
        messages = []
        for t in turns:
            messages.append({"role": "user", "turn_index": t.turn_index,
                              "text": t.raw_query, "created_at": t.created_at.isoformat(),
                              "archived": t.archived_at is not None})
            if t.pending_clarification_json:
                clarification = json.loads(t.pending_clarification_json)
                messages.append({"role": "assistant", "turn_index": t.turn_index,
                                  "text": clarification.get("question", ""),
                                  "type": "clarification", "options": clarification.get("options", []),
                                  "created_at": t.created_at.isoformat()})
            elif t.response_summary:
                messages.append({"role": "assistant", "turn_index": t.turn_index,
                                  "text": t.response_summary, "type": "answer",
                                  "created_at": t.created_at.isoformat()})
        return {"session_id": session_id, "messages": messages}
    except Exception:
        logger.exception("GET /conversation/%s/history failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch conversation history.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /conversation/{session_id}/summarize
# ---------------------------------------------------------------------------

@router.post("/{session_id}/summarize")
def post_summarize(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    db = SessionLocal()
    try:
        manager = ConversationManager(db)
        from backend.conversation.summarizer import summarize_now
        return summarize_now(db, session_id)
    except Exception:
        logger.exception("POST /conversation/%s/summarize failed", session_id)
        raise HTTPException(status_code=500, detail="Summarization failed.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /conversation/{session_id}/export/pdf
# ---------------------------------------------------------------------------

@router.post("/{session_id}/export/pdf")
def post_export_pdf(session_id: int, language: str = "en", request: Request = None,
                     ctx: AuthContext = Depends(RequirePermission(EXPORT_PDF))):
    if language not in ("en", "kn", "bilingual"):
        raise HTTPException(status_code=422, detail="language must be one of 'en', 'kn', 'bilingual'.")

    db = SessionLocal()
    try:
        manager = ConversationManager(db)
        pdf_bytes, warnings = manager.export_last_report_as_pdf(session_id, language=language)
        if pdf_bytes is None:
            raise HTTPException(status_code=404, detail=warnings[0] if warnings else
                                 "No investigation findings recorded for this session yet.")

        security_audit.record(
            db, AuditAction.REPORT_GENERATED,
            user_id=ctx.user_id, username=ctx.username, target=f"session:{session_id}",
            success=True, ip_address=(request.client.host if request and request.client else None),
            user_agent=(request.headers.get("user-agent") if request else None),
            metadata={"language": language, "source": "conversation"},
        )

        headers = {"Content-Disposition": f'attachment; filename="SHERLOCK-session-{session_id}.pdf"',
                   "Content-Length": str(len(pdf_bytes))}
        if warnings:
            headers["X-PDF-Warnings"] = " | ".join(warnings)
        return FastAPIResponse(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /conversation/%s/export/pdf failed", session_id)
        raise HTTPException(status_code=500, detail="PDF export failed.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# DELETE /conversation/{session_id}/history — soft-clear
# ---------------------------------------------------------------------------

@router.delete("/{session_id}/history")
def delete_history(session_id: int, ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION))):
    """Soft-archives every turn and records a topic-reset marker — see
    `ConversationManager._clear_history`'s docstring for why this is
    never a physical delete (Stage E5 governance rule)."""
    db = SessionLocal()
    try:
        manager = ConversationManager(db)
        turns = manager.memory.get_history(session_id)
        if not turns:
            return {"session_id": session_id, "archived_turns": 0}

        manager._clear_history(session_id, matched_phrase="cleared via DELETE /conversation/history")

        security_audit.record(
            db, AuditAction.RECORD_ARCHIVED,
            user_id=ctx.user_id, username=ctx.username, target=f"session:{session_id}:conversation_turns",
            success=True, metadata={"archived_turns": len(turns)},
        )
        return {"session_id": session_id, "archived_turns": len(turns)}
    except Exception:
        logger.exception("DELETE /conversation/%s/history failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to clear conversation history.")
    finally:
        db.close()
