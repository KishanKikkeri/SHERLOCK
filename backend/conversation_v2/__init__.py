"""
SHERLOCK — Conversation V2 package.

Replaces the old ``backend/conversation/`` system with an LLM-first,
tool-driven architecture that strictly separates Conversation from
Investigation.
"""

from backend.conversation_v2.orchestrator import LLMOrchestrator

__all__ = ["LLMOrchestrator"]
