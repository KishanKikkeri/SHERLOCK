"""
SHERLOCK — Conversation V2: Centralized Tool Registry.

Every capability the LLM can invoke — search, investigation, analytics,
forecasting, PDF export — is registered here as a named tool with a JSON
Schema description and an async handler function.

The LLM never calls backend services directly. Everything goes through
the ToolRegistry. This replaces the old if/elif dispatch chain in
``backend/conversation/tools.py``.

Design decisions:
  - **Declarative**: tools self-register with schema + handler at import time
  - **Unified context**: every tool receives a ``ToolContext`` with
    conversation_id, investigation_id, language, and a DB session
  - **Provider-agnostic schemas**: stored in OpenAI-function-calling format;
    adapters for Claude/Gemini convert at call time (same as before)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Execution context passed to every tool handler."""
    db: Any                              # SQLAlchemy session
    conversation_id: int | None = None
    investigation_id: int | None = None
    language: str = "en"


@dataclass
class ToolDefinition:
    """One registered tool."""
    name: str
    description: str
    parameters: dict                     # JSON Schema (OpenAI format)
    handler: Callable[..., Awaitable[dict]]  # async (ctx, **kwargs) → dict
    # If True, this tool's result should be streamed as agent-timeline
    # events (e.g. the 20-agent investigation pipeline).
    streams_events: bool = False


class ToolRegistry:
    """Centralized registry of all tools the LLM can invoke.

    Usage::

        registry = ToolRegistry()
        registry.register(ToolDefinition(...))

        # For LLM system prompt / tool declarations
        schemas = registry.get_all_schemas()

        # Execute a tool call from the LLM
        result = await registry.execute("search_person", {"name": "Ravi"}, ctx)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            logger.warning("Overwriting tool registration: %s", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_schema(self, name: str) -> dict | None:
        tool = self._tools.get(name)
        if tool is None:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }

    def get_all_schemas(self) -> list[dict]:
        """All tool schemas in OpenAI function-calling format."""
        return [self.get_schema(name) for name in self._tools]  # type: ignore[misc]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    async def execute(
        self, name: str, arguments: dict, ctx: ToolContext
    ) -> dict:
        """Execute a registered tool by name.

        Returns the tool's structured result dict. Raises ValueError for
        unknown tools. Tool handler exceptions propagate unchanged.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        logger.info("ToolRegistry executing: %s(%s)", name, arguments)
        return await tool.handler(ctx, **arguments)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
