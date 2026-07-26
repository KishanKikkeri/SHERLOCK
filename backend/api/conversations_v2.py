"""
SHERLOCK — Conversation V2: Conversations V2 REST API.

Provides CRUD, chat composition, SSE streaming, and PDF export for the
new V2 conversation threads. Includes:
  - Create/List/Get/Update/Soft-Delete conversations
  - Message history
  - Non-streaming message (POST /messages)
  - SSE streaming message (POST /stream)
  - PDF report export (POST /export/pdf)
"""

import json
import logging
from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, Response as FastAPIResponse
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.database.models.conversation_v2 import ConversationV2, MessageV2
from backend.conversation_v2.orchestrator import LLMOrchestrator
from backend.security.dependencies import AuthContext
from backend.security.permissions import (
    RequirePermission,
    VIEW_CASE,
    MANAGE_CASE,
    RUN_INVESTIGATION,
    EXPORT_PDF,
)
from backend.security import audit as security_audit
from backend.database.models import AuditAction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v2/conversations", tags=["conversations-v2"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class CreateConversationRequest(BaseModel):
    investigation_id: Optional[int] = None
    nickname: Optional[str] = None
    language: Optional[str] = "en"  # "en" | "kn" | "hi"


class UpdateConversationRequest(BaseModel):
    nickname: Optional[str] = None
    language: Optional[str] = None
    pinned: Optional[bool] = None
    archive: Optional[bool] = None  # True to archive, False to unarchive


class SendMessageRequest(BaseModel):
    message: str
    language: Optional[str] = None



def _serialize_conversation(row: ConversationV2) -> dict:
    return {
        "id": row.id,
        "investigation_id": row.investigation_id,
        "nickname": row.nickname,
        "language": row.language,
        "pinned": row.pinned,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_message(row: MessageV2) -> dict:
    def safe_json_load(raw: str | None) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "role": row.role,
        "content": row.content,
        "tool_calls": safe_json_load(row.tool_calls_json),
        "tool_name": row.tool_name,
        "tool_result": safe_json_load(row.tool_result_json),
        "tool_call_id": row.tool_call_id,
        "metadata": safe_json_load(row.metadata_json) or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@router.post("")
def create_conversation(
    payload: CreateConversationRequest,
    _ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION)),
):
    db = SessionLocal()
    try:
        nickname = payload.nickname or "New Conversation"
        conv = ConversationV2(
            investigation_id=payload.investigation_id,
            nickname=nickname,
            language=payload.language or "en",
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return _serialize_conversation(conv)
    except Exception:
        db.rollback()
        logger.exception("Failed to create conversation")
        raise HTTPException(status_code=500, detail="Failed to create conversation.")
    finally:
        db.close()


@router.get("")
def list_conversations(
    investigation_id: Optional[int] = None,
    include_archived: bool = False,
    _ctx: AuthContext = Depends(RequirePermission(VIEW_CASE)),
):
    db = SessionLocal()
    try:
        query = db.query(ConversationV2).filter(ConversationV2.is_deleted == False)
        if investigation_id is not None:
            query = query.filter(ConversationV2.investigation_id == investigation_id)
        if not include_archived:
            query = query.filter(ConversationV2.archived_at == None)

        rows = (
            query.order_by(ConversationV2.pinned.desc())
            .order_by(ConversationV2.updated_at.desc())
            .all()
        )
        return [_serialize_conversation(r) for r in rows]
    except Exception:
        logger.exception("Failed to list conversations")
        raise HTTPException(status_code=500, detail="Failed to list conversations.")
    finally:
        db.close()


@router.get("/cases")
def list_cases(
    search: Optional[str] = None,
    _ctx: AuthContext = Depends(RequirePermission(VIEW_CASE)),
):
    """List and search case records or FIRs."""
    db = SessionLocal()
    try:
        from backend.database.service import DatabaseService
        svc = DatabaseService(db)
        cases = svc.list_cases(search=search)
        res = []
        for c in cases:
            crime_type = c.crime.type if c.crime else None
            district = c.crime.location.district if c.crime and c.crime.location else None
            res.append({
                "fir_id": c.id,
                "fir_number": c.fir_number,
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "crime_type": crime_type.value if hasattr(crime_type, "value") else str(crime_type) if crime_type else None,
                "district": district,
                "filed_date": c.filed_date.isoformat() if c.filed_date else None,
            })
        return res
    finally:
        db.close()


@router.get("/{id}")
def get_conversation(
    id: int,
    _ctx: AuthContext = Depends(RequirePermission(VIEW_CASE)),
):
    db = SessionLocal()
    try:
        row = db.get(ConversationV2, id)
        if not row or row.is_deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return _serialize_conversation(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get conversation")
        raise HTTPException(status_code=500, detail="Failed to fetch conversation.")
    finally:
        db.close()


@router.patch("/{id}")
def update_conversation(
    id: int,
    payload: UpdateConversationRequest,
    _ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION)),
):
    db = SessionLocal()
    try:
        row = db.get(ConversationV2, id)
        if not row or row.is_deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        if payload.nickname is not None:
            row.nickname = payload.nickname
        if payload.language is not None:
            if payload.language not in ("en", "kn", "hi"):
                raise HTTPException(status_code=422, detail="Language must be 'en', 'kn', or 'hi'.")
            row.language = payload.language
        if payload.pinned is not None:
            row.pinned = payload.pinned
        if payload.archive is not None:
            if payload.archive:
                row.archived_at = datetime.utcnow()
            else:
                row.archived_at = None

        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _serialize_conversation(row)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to update conversation")
        raise HTTPException(status_code=500, detail="Failed to update conversation.")
    finally:
        db.close()


@router.delete("/{id}")
def delete_conversation(
    id: int,
    _ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION)),
):
    """Soft-delete conversation by setting `is_deleted`."""
    db = SessionLocal()
    try:
        row = db.get(ConversationV2, id)
        if not row or row.is_deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        row.is_deleted = True
        row.updated_at = datetime.utcnow()
        db.commit()
        return {"id": id, "status": "deleted"}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to delete conversation")
        raise HTTPException(status_code=500, detail="Failed to delete conversation.")
    finally:
        db.close()


@router.post("/{id}/duplicate")
def duplicate_conversation(
    id: int,
    _ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION)),
):
    """Duplicate a conversation and its messages."""
    db = SessionLocal()
    try:
        row = db.get(ConversationV2, id)
        if not row or row.is_deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        copied = ConversationV2(
            investigation_id=row.investigation_id,
            nickname=f"Copy of {row.nickname}",
            language=row.language,
        )
        db.add(copied)
        db.commit()
        db.refresh(copied)

        # Copy messages
        msgs = (
            db.query(MessageV2)
            .filter(MessageV2.conversation_id == id)
            .order_by(MessageV2.created_at.asc())
            .all()
        )
        for m in msgs:
            new_m = MessageV2(
                conversation_id=copied.id,
                role=m.role,
                content=m.content,
                tool_calls_json=m.tool_calls_json,
                tool_name=m.tool_name,
                tool_result_json=m.tool_result_json,
                tool_call_id=m.tool_call_id,
                metadata_json=m.metadata_json,
            )
            db.add(new_m)

        db.commit()
        return _serialize_conversation(copied)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to duplicate conversation")
        raise HTTPException(status_code=500, detail="Failed to duplicate conversation.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Message / Chat Endpoints
# ---------------------------------------------------------------------------

@router.get("/{id}/messages")
def get_messages(
    id: int,
    _ctx: AuthContext = Depends(RequirePermission(VIEW_CASE)),
):
    """Retrieve full message history for a conversation."""
    db = SessionLocal()
    try:
        row = db.get(ConversationV2, id)
        if not row or row.is_deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        msgs = (
            db.query(MessageV2)
            .filter(MessageV2.conversation_id == id)
            .order_by(MessageV2.created_at.asc())
            .all()
        )
        return [_serialize_message(m) for m in msgs]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get messages")
        raise HTTPException(status_code=500, detail="Failed to fetch messages.")
    finally:
        db.close()


@router.post("/{id}/messages")
async def post_message(
    id: int,
    payload: SendMessageRequest,
    ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION)),
):
    """Send a message to the conversation (non-streaming)."""
    db = SessionLocal()
    try:
        row = db.get(ConversationV2, id)
        if not row or row.is_deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        if payload.language and payload.language in ("en", "kn", "hi"):
            row.language = payload.language
            db.commit()

        active_lang = payload.language or row.language or "en"
        orchestrator = LLMOrchestrator(db)
        result = await orchestrator.handle_message(
            conversation_id=id,
            message=payload.message,
            language=active_lang,
            investigation_id=row.investigation_id,
        )

        # Refresh messages to return the full conversation including assistant response
        msgs = (
            db.query(MessageV2)
            .filter(MessageV2.conversation_id == id)
            .order_by(MessageV2.created_at.desc())
            .limit(5)
            .all()
        )
        return {
            "reply": result.reply,
            "conversation_id": result.conversation_id,
            "tool_calls": result.tool_calls,
            "citations": result.citations,
            "recent_messages": [_serialize_message(m) for m in reversed(msgs)],
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to send message")
        raise HTTPException(status_code=500, detail="Message processing failed.")
    finally:
        db.close()


@router.post("/{id}/stream")
async def post_stream(
    id: int,
    payload: SendMessageRequest,
    ctx: AuthContext = Depends(RequirePermission(RUN_INVESTIGATION)),
):
    """Send a message to the conversation with SSE streaming."""
    db = SessionLocal()
    row = db.get(ConversationV2, id)

    if not row or row.is_deleted:
        db.close()
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if payload.language and payload.language in ("en", "kn", "hi"):
        row.language = payload.language
        db.commit()

    active_lang = payload.language or row.language or "en"
    db.close()

    async def event_generator():
        stream_db = SessionLocal()
        try:
            orchestrator = LLMOrchestrator(stream_db)
            async for event in orchestrator.stream_message(
                conversation_id=id,
                message=payload.message,
                language=active_lang,
                investigation_id=row.investigation_id,
            ):
                payload_data = {
                    "event_type": event.event_type,
                    "message": event.message,
                    "agent": event.agent,
                    "data": event.data,
                }
                yield f"data: {json.dumps(payload_data)}\n\n"

        except Exception as e:
            logger.exception("Streaming event generation failed")
            error_payload = {
                "event_type": "error",
                "message": str(e),
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Export Endpoint
# ---------------------------------------------------------------------------

@router.post("/{id}/export/pdf")
def export_pdf(
    id: int,
    request: Request = None,
    ctx: AuthContext = Depends(RequirePermission(EXPORT_PDF)),
):
    """Export conversation and findings as a PDF report."""
    db = SessionLocal()
    try:
        row = db.get(ConversationV2, id)
        if not row or row.is_deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        # Re-use pdf generation. We can build it from messages of this conversation
        msgs = (
            db.query(MessageV2)
            .filter(MessageV2.conversation_id == id)
            .order_by(MessageV2.created_at.asc())
            .all()
        )
        if not msgs:
            raise HTTPException(status_code=404, detail="No messages in this conversation to export.")

        # Build PDF from simple text flow
        # In a real environment, we'd use reportlab or reuse generate_investigation_pdf.
        # Let's import from backend.reporting.pdf_export
        from backend.reporting.pdf_export import generate_investigation_pdf, pdf_export_warnings

        # Compile simple findings mock to make PDF export compatible
        # findings = [{'title': '...', 'description': '...'}]
        findings = []
        for m in msgs:
            if m.role == "assistant" and m.content:
                findings.append({
                    "title": f"Response {m.created_at.strftime('%Y-%m-%d %H:%M')}",
                    "description": m.content,
                    "finding_type": f"Response {m.created_at.strftime('%Y-%m-%d %H:%M')}",
                    "summary": m.content,
                    "confidence": 1.0,
                    "evidence_refs": [],
                })

        final_report = {
            "query": f"Conversation V2 Export — '{row.nickname}'",
            "narrative": "This document contains the archived discussion and evidence records from the conversation.",
            "findings": findings,
            "rejected_findings": [],
            "evidence_log": [],
        }

        pdf_bytes = generate_investigation_pdf(
            final_report=final_report,
            language=row.language,
        )

        security_audit.record(
            db, AuditAction.REPORT_GENERATED,
            user_id=ctx.user_id, username=ctx.username, target=f"conversation:{id}",
            success=True, ip_address=(request.client.host if request and request.client else None),
            user_agent=(request.headers.get("user-agent") if request else None),
            metadata={"language": row.language, "source": "conversation_v2"},
        )

        headers = {
            "Content-Disposition": f'attachment; filename="SHERLOCK-chat-{id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        }
        warnings = pdf_export_warnings(final_report, row.language)
        if warnings:
            headers["X-PDF-Warnings"] = " | ".join(warnings)
        return FastAPIResponse(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except HTTPException:
        raise
    except Exception:
        logger.exception("PDF export failed for conversation %d", id)
        raise HTTPException(status_code=500, detail="PDF export failed.")
    finally:
        db.close()

