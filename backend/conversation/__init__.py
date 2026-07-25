"""
SHERLOCK — Stage F3: Conversation Intelligence System (CIS) facade.

Stage F2 established the CIS as a unified front door for chat. Stage F3
rewrites it as the *primary intelligence layer*:

  1. Intent classification (intent.py) decides what kind of message
     this is — greeting, chitchat, follow-up, investigation, or
     meta-command — so only investigation queries reach the 20-agent
     pipeline. Everything else gets an instant conversational reply.
  2. Conversational response formatting (responder.py) ensures every
     reply is 3–6 sentences, uses progressive disclosure, and never
     dumps agent names, confidence scores, or raw reports at the user.
  3. The ConversationManager (manager.py) is now the orchestrator brain,
     not a passthrough — it decides when to invoke the investigation
     pipeline (a tool) versus when to respond directly.

The investigation pipeline itself (LangGraph, all 20 agents,
SherlockState) is completely unchanged — it just stops being called
for "Hi" and "What about his brother?"
"""

from backend.conversation.orchestrator import ConversationOrchestrator

__all__ = ["ConversationOrchestrator"]

