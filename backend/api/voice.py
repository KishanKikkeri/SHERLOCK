"""
SHERLOCK — Stage C3: Voice command API.

    POST /voice/command   { "transcript": "...", "session_id": 12 }

The browser does STT (via `useVoice.ts`'s existing wake-word/push-to-talk
Web Speech API wrapper) and posts the resulting text here; this endpoint
classifies and executes it (session lifecycle, board, report, or a
free-text investigation query) and returns a short spoken_response the
browser hands straight to `useVoice`'s existing `speak()` for TTS. No
audio ever crosses the wire in either direction — same "no server
round-trip for voice itself" design the existing frontend voice layer
already uses for board commands.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.voice.command_router import VoiceCommandRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceCommandRequest(BaseModel):
    transcript: str
    session_id: int | None = None


@router.post("/command")
async def voice_command(body: VoiceCommandRequest):
    session = SessionLocal()
    try:
        cmd_router = VoiceCommandRouter(session)
        result = await cmd_router.route(body.transcript, session_id=body.session_id)
        return result.to_dict()
    except Exception:
        logger.exception("POST /voice/command failed for transcript: %r", body.transcript)
        raise HTTPException(status_code=500, detail="Voice command failed.")
    finally:
        session.close()
