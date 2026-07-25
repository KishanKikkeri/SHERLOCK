"""
SHERLOCK — Chief Investigation Officer (Phase 5).

The only agent allowed to plan. Two responsibilities, two graph nodes:

  - `plan_node`     (entry point): interpret the query, decide which
                     specialist agents are needed, extract filters
                     (crime type / district / festival season / etc.)
  - `synthesis_node` (final node): read `validated_findings` and produce
                     the final investigation report.

The Chief never calls `graph_service` or touches the database — it only
reads/writes `SherlockState`.

If ANTHROPIC_API_KEY is set, synthesis uses Claude to write a natural-
language narrative on top of the structured findings. Without it, a
deterministic template is used — the pipeline works fully either way.

Priority 27/29/33 (Project-wide Language Awareness): the narrative is
the primary piece of free-text SHERLOCK generates in reply to an
investigator's question, so it's the highest-value place to generate
*directly* in the active language rather than writing English and
translating afterward. `synthesis_node` reads `state["language"]`
(threaded end-to-end from the API layer via `SherlockState`, see
backend/orchestrator/state.py) and passes it down to
`_generate_narrative`. The LLM path uses `language_directive()` to ask
Claude to answer natively in that language; the template fallback (no
ANTHROPIC_API_KEY) is passed through `localize_template_fallback()` so
even the deterministic path honors the active language instead of
silently reverting to English. Either way, `final_report["narrative_language"]`
records what language the narrative actually came back in, so
downstream localization (`_localize_report` in
backend/api/investigation_stream.py) knows not to translate it again.
"""

import logging
import os

from backend.agents.base.query_parser import extract_filters, plan_agents
from backend.language.prompting import language_directive, localize_template_fallback

logger = logging.getLogger(__name__)


class ChiefAgent:
    name = "Chief"

    # -----------------------------------------------------------------
    # Node 1: Investigation planning (entry point)
    # -----------------------------------------------------------------
    def plan_node(self, state: dict) -> dict:
        query = state["query"]
        filters = extract_filters(query)
        plan = plan_agents(filters)

        return {
            "investigation_plan": plan,
            "active_agents": plan["agents"],
            "audit_trail": [{
                "agent": self.name,
                "status": "done",
                "message": (
                    f"Investigation plan created. Agents: {', '.join(plan['agents'])}. "
                    f"Filters: {filters}"
                ),
            }],
        }

    # -----------------------------------------------------------------
    # Node 2: Final synthesis
    # -----------------------------------------------------------------
    def synthesis_node(self, state: dict) -> dict:
        query = state["query"]
        validated = state.get("validated_findings", [])
        accepted = [f for f in validated if f.get("validated")]
        rejected = [f for f in validated if not f.get("validated")]
        language = state.get("language") or "en"

        narrative = self._generate_narrative(query, accepted, language)

        report = {
            "query": query,
            "narrative": narrative,
            "narrative_language": language,
            "findings": accepted,
            "rejected_findings": rejected,
            "agents_consulted": state.get("active_agents", []),
        }

        return {
            "final_report": report,
            "audit_trail": [{
                "agent": self.name,
                "status": "done",
                "message": f"Final report generated from {len(accepted)} validated finding(s) "
                           f"({len(rejected)} rejected by Evidence Validation).",
            }],
        }

    # -----------------------------------------------------------------
    # Narrative generation: Claude if available, deterministic fallback otherwise
    # -----------------------------------------------------------------
    def _generate_narrative(self, query: str, accepted_findings: list, language: str = "en") -> str:
        if not accepted_findings:
            message = ("No validated findings were available to answer this query. "
                       "This may mean the relevant data wasn't found, or all findings "
                       "were rejected for insufficient evidence.")
            return localize_template_fallback(message, language)

        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                return self._generate_narrative_llm(query, accepted_findings, language)
            except Exception:
                logger.warning("LLM narrative generation failed, falling back to template", exc_info=True)
                template = self._generate_narrative_template(query, accepted_findings) + \
                    "\n\n(Note: AI-written narrative was unavailable for this report; " \
                    "the summary above was generated from structured findings directly.)"
                return localize_template_fallback(template, language)

        return localize_template_fallback(self._generate_narrative_template(query, accepted_findings), language)

    def _generate_narrative_template(self, query: str, accepted_findings: list) -> str:
        lines = [f"Investigation summary for: \"{query}\"", ""]
        for f in accepted_findings:
            conf_pct = round(f.get("confidence", 0) * 100)
            lines.append(f"- [{f['agent_name']}] {f['summary']} (confidence: {conf_pct}%)")
        return "\n".join(lines)

    def _generate_narrative_llm(self, query: str, accepted_findings: list, language: str = "en") -> str:
        from anthropic import Anthropic

        client = Anthropic()
        findings_text = "\n".join(
            f"- [{f['agent_name']}] {f['summary']} "
            f"(confidence {f.get('confidence', 0):.0%}, evidence: {', '.join(f.get('evidence', []))})"
            for f in accepted_findings
        )
        prompt = (
            "You are the Chief Investigation Officer of SHERLOCK, an AI crime "
            "intelligence platform. Write a short (3-5 sentence), professional "
            "investigation briefing that synthesizes the findings below into a "
            "coherent answer to the investigator's query. Be factual and cite "
            "the confidence levels where relevant. Do not invent any facts not "
            "present in the findings."
            + language_directive(language) +
            f"\n\nQuery: {query}\n\nFindings:\n{findings_text}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
