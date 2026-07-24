"""
SHERLOCK — Stage F2: Conversation Intelligence System (CIS) facade.

This package does NOT reimplement investigation orchestration, memory,
translation, voice, or reporting — all of that already exists and is
battle-tested (backend/orchestrator, backend/memory, backend/language,
backend/voice, backend/reporting). What was still missing, per the CIS
proposal, was a single, coherent front door that:

  1. turns a raw chat message into either a meta-command (summarize,
     export, clear) or an investigation query (router.py),
  2. runs it through the existing session-aware pipeline and shapes the
     result for a chat UI rather than a raw SherlockState (manager.py),
  3. turns validated findings into citation-style evidence the frontend
     can render as cards, not just prose (citations.py),
  4. offers deterministic, template-based follow-up question suggestions
     the way the rest of this codebase prefers over freely-generated
     LLM text (prompts.py), and
  5. exposes the existing rolling-summary mechanism as an on-demand
     action instead of only an automatic 8-turn threshold (summarizer.py).

Nothing here talks to the database directly except via `DatabaseService`
/ `ConversationMemoryService`, per the existing "DatabaseService is the
only class allowed to know SQL" rule.
"""

from backend.conversation.manager import ConversationManager

__all__ = ["ConversationManager"]
