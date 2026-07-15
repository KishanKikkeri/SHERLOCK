"""
SHERLOCK — Stage C2: ConversationMemoryService.

A working, honest slice of Stage C2's "multi-turn conversation" goal:
persists each turn of a session's conversation (`ConversationTurn`, Stage
A/B-safe, additive table) and resolves the small set of follow-up
patterns the Stage C2 brief's own example uses —

    Show suspects -> Tell me about Ravi -> Expand his network ->
    Freeze that account

i.e. "his"/"her"/"their" -> last person mentioned, "that account" -> last
bank account mentioned, "the case"/"this case" -> the session's FIR.

What this is NOT: a general-purpose coreference resolver or an LLM-backed
dialogue manager. Real named-entity coreference ("expand Ravi Kumar's
cousin's network") and multi-entity disambiguation ("which of the two
Ravis") are out of scope for this sprint and would need an LLM call or a
proper NLP pipeline — flagged here rather than faked.
"""

from __future__ import annotations

import json
import re

from backend.database.models import ConversationTurn, Person


# Very small, explicit pattern set — deliberately not "clever" regex golf,
# so it's obvious exactly what this does and doesn't catch.
_PERSON_PRONOUNS = re.compile(r"\b(his|her|him|their|they|he|she)\b", re.IGNORECASE)
_ACCOUNT_REF = re.compile(r"\b(that account|the account|this account)\b", re.IGNORECASE)
_CASE_REF = re.compile(r"\b(the case|this case|that case)\b", re.IGNORECASE)

# Matches every specialist agent's `source_entities` convention, e.g.
# "person_123", "fir_456", "account_78" — see AgentFinding.source_entities
# in backend/agents/base/finding.py and every agent's own construction
# calls (grep confirms "<type>_<id>" is used uniformly across all ~20
# specialist agents, not just one).
_ENTITY_REF = re.compile(r"^(person|fir|account)_(\d+)$")


class ConversationMemoryService:
    """Reads/writes ConversationTurn rows for one InvestigationSession."""

    def __init__(self, session):
        self.session = session  # SQLAlchemy session (matches DatabaseService's own naming)

    def get_history(self, session_id: int) -> list[ConversationTurn]:
        return (
            self.session.query(ConversationTurn)
            .filter_by(session_id=session_id)
            .order_by(ConversationTurn.turn_index)
            .all()
        )

    def get_last_turn(self, session_id: int) -> ConversationTurn | None:
        return (
            self.session.query(ConversationTurn)
            .filter_by(session_id=session_id)
            .order_by(ConversationTurn.turn_index.desc())
            .first()
        )

    def get_all_findings(self, session_id: int) -> list[dict]:
        """Every finding produced across every turn of this session,
        de-duplicated by (agent_name, finding_type, tuple(source_entities))
        so re-asking the same thing twice doesn't double-count evidence.
        Used by Stage C5's board intelligence — the board should reflect
        everything surfaced in the investigation so far, not just the
        most recent turn."""
        seen = set()
        all_findings = []
        for turn in self.get_history(session_id):
            if not turn.findings_json:
                continue
            for f in json.loads(turn.findings_json):
                key = (f.get("agent_name"), f.get("finding_type"), tuple(f.get("source_entities") or []))
                if key in seen:
                    continue
                seen.add(key)
                all_findings.append(f)
        return all_findings

    def resolve_query(self, session_id: int, raw_query: str) -> str:
        """Best-effort substitution of pronouns/refs with the last known
        entity name, so the query handed to the orchestrator is
        self-contained (e.g. "expand his network" ->
        "expand Ravi Kumar's network"). Returns raw_query unchanged if
        there's no prior turn or nothing to substitute against."""
        last_turn = self.get_last_turn(session_id)
        if last_turn is None:
            return raw_query

        resolved = raw_query

        if last_turn.last_person_name and _PERSON_PRONOUNS.search(resolved):
            resolved = _PERSON_PRONOUNS.sub(last_turn.last_person_name, resolved)

        if last_turn.last_account_id and _ACCOUNT_REF.search(resolved):
            resolved = _ACCOUNT_REF.sub(f"account #{last_turn.last_account_id}", resolved)

        if last_turn.last_fir_id and _CASE_REF.search(resolved):
            resolved = _CASE_REF.sub(f"FIR #{last_turn.last_fir_id}", resolved)

        return resolved

    def record_turn(self, session_id: int, raw_query: str, resolved_query: str,
                     final_state: dict) -> ConversationTurn:
        """Persist this turn, extracting new entity-reference pointers from
        the finished investigation state so the *next* turn can resolve
        against them. Reads `source_entities` (every specialist agent's
        real "person_123" / "fir_456" / "account_78" convention — see
        AgentFinding), taking the *last* match of each kind across all of
        this turn's findings as the most likely referent for a follow-up
        pronoun. Falls back to the previous turn's reference when this
        turn didn't mention a new one, so "expand his network" still
        resolves two turns after "tell me about Ravi", not just
        immediately after."""
        last_turn = self.get_last_turn(session_id)
        next_index = 0 if last_turn is None else last_turn.turn_index + 1

        # BUGFIX (Stage C0): `final_state` as passed in by
        # stream_investigation is LangGraph's *last node's diff* (its
        # `.stream()` yields per-node updates, not the accumulated full
        # state), so `final_state["findings"]` is empty by the time
        # chief_synthesis runs. The fully compiled findings list — the
        # same one source_entities extraction needs — lives in
        # `final_state["final_report"]["findings"]` instead; verified
        # against a live run (see Stage C0 sprint report).
        report = (final_state or {}).get("final_report") or {}
        findings = report.get("findings") or (final_state or {}).get("findings") or []
        person_id = self._last_ref(findings, "person")
        fir_id = self._last_ref(findings, "fir")
        account_id = self._last_ref(findings, "account")

        last_person_id = person_id if person_id is not None else (last_turn.last_person_id if last_turn else None)
        last_person_name = self._person_name(person_id) if person_id is not None else \
            (last_turn.last_person_name if last_turn else None)
        last_fir_id = fir_id if fir_id is not None else (last_turn.last_fir_id if last_turn else None)
        last_account_id = account_id if account_id is not None else (last_turn.last_account_id if last_turn else None)

        response_summary = report.get("summary") or report.get("narrative") if isinstance(report, dict) else None

        turn = ConversationTurn(
            session_id=session_id,
            turn_index=next_index,
            raw_query=raw_query,
            resolved_query=resolved_query if resolved_query != raw_query else None,
            last_person_id=last_person_id,
            last_person_name=last_person_name,
            last_fir_id=last_fir_id,
            last_account_id=last_account_id,
            response_summary=response_summary,
            findings_json=json.dumps(findings) if findings else None,
        )
        self.session.add(turn)
        self.session.commit()
        self.session.refresh(turn)
        return turn

    # -- extraction helpers -------------------------------------------------

    @staticmethod
    def _last_ref(findings: list, kind: str) -> int | None:
        """Last `source_entities` match of the given kind ("person",
        "fir", "account") across every finding this turn, in agent
        execution order — later agents in the pipeline run on a narrower,
        more-specific scope (see orchestrator/graph.py's topology), so
        "last mentioned" is a reasonable proxy for "most relevant"."""
        match_id = None
        for finding in findings:
            for ref in finding.get("source_entities") or []:
                m = _ENTITY_REF.match(ref)
                if m and m.group(1) == kind:
                    match_id = int(m.group(2))
        return match_id

    def _person_name(self, person_id: int | None) -> str | None:
        if person_id is None:
            return None
        person = self.session.get(Person, person_id)
        return person.name if person else None
