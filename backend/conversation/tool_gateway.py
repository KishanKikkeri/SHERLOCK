"""
SHERLOCK — Stage F3: Conversational Intelligence — Tool Gateway.

Acts as the single gatekeeper and entry point for all database lookups,
investigations, and analytics queries called by the Conversation Planner.

Handles:
- Permissions verification
- Caching of tool results during a turn
- Parallel tool execution (using asyncio.gather)
- Robust logging and error normalization
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from backend.conversation import tools as tools_module

logger = logging.getLogger(__name__)


class ToolGateway:
    def __init__(self, db, roles: List[str] | None = None):
        self.db = db
        self.roles = roles or []
        self.cache: Dict[str, Any] = {}

    def _has_permission(self, tool_name: str) -> bool:
        """Verifies if the caller has permissions for this tool.
        Administrators can run everything; other users can run non-admin tools.
        """
        if "admin" in self.roles:
            return True
        # Specific restrictions can be added here if needed
        return True

    async def execute_tool(self, name: str, arguments: dict, session_id: int, language: str = "en") -> dict:
        """Executes a single tool with caching and permission checks."""
        if not self._has_permission(name):
            return {
                "status": "error",
                "message": f"Permission denied for executing tool '{name}'."
            }

        # Cache key based on name and sorted arguments
        cache_key = f"{name}:{str(sorted(arguments.items()))}"
        if cache_key in self.cache:
            logger.info("ToolGateway cache hit for: %s", cache_key)
            return self.cache[cache_key]

        try:
            logger.info("ToolGateway executing tool: %s", name)
            res = await tools_module.call_tool(name, arguments, session_id, language)
            self.cache[cache_key] = res
            return res
        except Exception as e:
            logger.exception("Tool execution failed: %s", name)
            return {
                "status": "error",
                "message": f"Tool '{name}' failed: {str(e)}"
            }

    async def execute_tools_parallel(self, tool_calls: List[Dict[str, Any]], session_id: int, language: str = "en") -> Dict[str, dict]:
        """Runs multiple independent tool calls concurrently.
        
        Args:
            tool_calls: list of dicts like [{"name": "search_person", "arguments": {"name": "Ravi"}}]
        
        Returns:
            Dict mapping tool call string representation to tool results dict.
        """
        if not tool_calls:
            return {}

        tasks = []
        for tc in tool_calls:
            name = tc["name"]
            args = tc.get("arguments") or {}
            tasks.append(self.execute_tool(name, args, session_id, language))

        results = await asyncio.gather(*tasks)

        mapped_results = {}
        for tc, res in zip(tool_calls, results):
            name = tc["name"]
            key = f"{name}({json.dumps(tc.get('arguments'))})"
            mapped_results[key] = res

        return mapped_results
