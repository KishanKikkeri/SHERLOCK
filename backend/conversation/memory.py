"""
SHERLOCK — Stage F3: Conversational Intelligence — Conversation Memory Wrapper.

Reads, formats, and caches active context, entities, history, and findings
to present to the Conversation LLM Brain.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from backend.database.models import InvestigationSession, ConversationTurn
from backend.memory.conversation_memory import ConversationMemoryService

logger = logging.getLogger(__name__)


class ConversationStateMemory:
    def __init__(self, db, session_id: int):
        self.db = db
        self.session_id = session_id
        self.memory_service = ConversationMemoryService(db)

    def get_context_for_llm(self) -> dict:
        """Assembles a clean, structured context snapshot for the LLM Planner and Agent."""
        session = self.db.get(InvestigationSession, self.session_id)
        last_turn = self.memory_service.get_last_turn(self.session_id)
        turns = self.memory_service.get_history(self.session_id)

        # 1. Previous messages list
        previous_messages = []
        for t in turns:
            previous_messages.append({"role": "user", "text": t.raw_query})
            if t.response_summary:
                previous_messages.append({"role": "assistant", "text": t.response_summary})

        # 2. Last findings
        last_findings = []
        if last_turn and last_turn.findings_json:
            try:
                last_findings = json.loads(last_turn.findings_json)
            except Exception:
                logger.warning("Failed to decode findings_json for turn %s", last_turn.id)

        # 3. Active entities
        active_entities = []
        if last_turn and last_turn.entity_mentions_json:
            try:
                active_entities = json.loads(last_turn.entity_mentions_json)
            except Exception:
                logger.warning("Failed to decode entity_mentions_json for turn %s", last_turn.id)

        # 4. Clarification question
        has_pending_clarification = False
        pending_clarification = None
        if last_turn and last_turn.pending_clarification_json:
            has_pending_clarification = True
            try:
                pending_clarification = json.loads(last_turn.pending_clarification_json)
            except Exception:
                pass

        return {
            "session_id": self.session_id,
            "current_case_id": session.fir_id if session else None,
            "current_case_number": session.fir.fir_number if (session and session.fir) else None,
            "conversation_summary": session.context_summary if session else None,
            "active_entities": active_entities,
            "last_findings": last_findings,
            "previous_messages": previous_messages[-8:],  # limit to last 8 messages for token size
            "has_pending_clarification": has_pending_clarification,
            "pending_clarification": pending_clarification,
        }
