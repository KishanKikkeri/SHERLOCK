"""
SHERLOCK — BaseAgent (Phase 5, stabilized).

Every specialist agent extends this. `run(state)` does the actual work and
returns a list of `AgentFinding`s (possibly empty). `to_node()` wraps that
into a LangGraph node function that:

  1. Checks whether this agent is in `state["active_agents"]` (per the
     Chief's investigation plan) — if not, logs a "skipped" activity entry
     and does nothing else. The Chief and Evidence Validation agents always
     run regardless of the plan.
  2. Calls `run(state)` inside a try/except — if the agent raises, the
     failure is logged server-side and isolated to that one node's audit
     entry (status "failed") rather than propagating up and aborting the
     entire investigation. Every other agent's findings gathered so far
     are preserved; only this one agent's contribution is missing.
  3. Converts findings to dicts and logs a "done" activity entry
     summarizing what was found, for the investigation activity feed.

This is what makes the "Chief decides which agents fire" dynamic routing
work without complex conditional graph edges — the topology is static and
simple (per the Phase 5 brief), but each node's actual work is plan-driven.
"""

import logging
from abc import ABC, abstractmethod

from backend.agents.base.finding import AgentFinding

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    name: str = "BaseAgent"
    always_runs: bool = False  # Chief + Evidence Validation override this to True

    @abstractmethod
    def run(self, state: dict):
        """Do the work.

        Return either:
          - list[AgentFinding], or
          - (list[AgentFinding], dict) where the dict contains additional
            state updates (e.g. {"graph_context": {...}}) to merge into
            SherlockState. Use this — not in-place mutation of `state` —
            to pass data to downstream agents, since LangGraph state
            updates are based on each node's *return value*.
        """

    def to_node(self):
        def node(state: dict) -> dict:
            active = state.get("active_agents", [])
            if not self.always_runs and self.name not in active:
                return {
                    "audit_trail": [{
                        "agent": self.name,
                        "status": "skipped",
                        "message": f"{self.name} not required for this query (not in plan).",
                    }]
                }

            try:
                result = self.run(state) or []
            except Exception as e:
                logger.exception("Agent %s raised during run() — isolating failure, investigation continues", self.name)
                return {
                    "audit_trail": [{
                        "agent": self.name,
                        "status": "failed",
                        "message": f"{self.name} encountered an unexpected error and was skipped: {e}",
                    }]
                }

            if isinstance(result, tuple):
                findings, extra = result
            else:
                findings, extra = result, {}

            if findings:
                summary = "; ".join(f.summary for f in findings)
                message = f"{self.name} reported: {summary}"
            else:
                message = f"{self.name} ran but produced no findings."

            update = {
                "findings": [f.to_dict() for f in findings],
                "audit_trail": [{
                    "agent": self.name,
                    "status": "done",
                    "message": message,
                }],
            }
            update.update(extra)
            return update

        return node
