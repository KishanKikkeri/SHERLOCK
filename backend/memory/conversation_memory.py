"""
SHERLOCK — Stage C2: ConversationMemoryService.

Sprint 1 shipped a working, honest slice of Stage C2: persistence
(`ConversationTurn`) plus the small set of follow-up patterns the brief's
own example uses ("tell me about Ravi" -> "expand his network" ->
"freeze that account"). This sprint (Sprint 2) closes out the six
"Remaining C2 work" items from the handover, as an honest, working slice
of each rather than a full NLU system:

1. Multi-entity disambiguation  -> `resolve_turn()` + `entity_mentions_json`
2. Clarification questions       -> `resolve_turn()` + `pending_clarification_json`
3. Conversation summarization    -> `maybe_summarize()`
4. Context expiration            -> `resolve_turn()` reset-phrase handling
5. Better reference resolution   -> extended pattern set below
6. Conversation timeline API     -> backend/api/conversation.py (new endpoints)

What this still is NOT, honestly: a general-purpose coreference resolver
or an LLM-backed dialogue manager. All pattern matching below is regex
over a fixed, documented set of phrases — not a language model deciding
what "that" refers to. Two limitations flagged rather than faked:

  - "their phones" / "the recovered vehicle": no specialist agent emits
    `phone_<id>` or `vehicle_<id>` in `source_entities` (grep confirms
    only person/fir/account/crime/location/officer/organization/property/
    weapon are used — see AGENT_MAPPING.md). Resolving these would need
    an agent change, which the Golden Rules forbid without a real bug.
    These phrases are matched (so the system can say "I don't have
    enough context for that yet" instead of silently mis-resolving)
    but not substituted.
  - Multi-entity disambiguation only fires for entities the *previous*
    turn's findings actually named more than one of. It cannot
    disambiguate "the two Ravis" if only one Ravi's findings ever
    reached this session — there's nothing to disambiguate against.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

from backend.database.models import (
    ConversationTurn, InvestigationSession, Person, FIR, BankAccount,
    Organization, Property, Weapon,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern set — deliberately not "clever" regex golf, so it's obvious
# exactly what this does and doesn't catch (same philosophy as Sprint 1).
# ---------------------------------------------------------------------------

_PERSON_PRONOUNS = re.compile(r"\b(his|her|him|their|they|he|she)\b", re.IGNORECASE)
_ACCOUNT_REF = re.compile(r"\b(that account|the account|this account)\b", re.IGNORECASE)
_CASE_REF = re.compile(r"\b(the case|this case|that case)\b", re.IGNORECASE)

# Sprint 2 additions — same "explicit phrase, not general NLU" philosophy.
_ORG_REF = re.compile(r"\b(that organization|the organization|this organization|that company|the company)\b", re.IGNORECASE)
_PROPERTY_REF = re.compile(r"\b(that property|the property|the recovered property|the seized item[s]?)\b", re.IGNORECASE)
_WEAPON_REF = re.compile(r"\b(that weapon|the weapon|the recovered weapon)\b", re.IGNORECASE)

# Recognized-but-unsupported (see module docstring). Matched so callers can
# say something honest instead of silently failing to resolve.
_UNSUPPORTED_REF = re.compile(
    r"\b(their phone[s]?|his phone|her phone|the recovered vehicle|that vehicle|the vehicle|"
    r"those witnesses|the witnesses|the previous fir)\b",
    re.IGNORECASE,
)

# Ordinal person references: "the second accused", "the first suspect" —
# resolved against this turn's *ordered* entity_mentions of kind "person",
# not left unsupported, since person ordinals are common in practice and
# the data (entity_mentions_json order) already exists to answer them.
_ORDINAL_WORDS = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
_ORDINAL_PERSON_REF = re.compile(
    r"\bthe (first|second|third|fourth|fifth) (accused|suspect|person|witness)\b", re.IGNORECASE
)

# See resolve_turn's disambiguation step for why this cap exists.
MAX_CLARIFICATION_OPTIONS = 6

_RESET_PATTERNS = re.compile(    r"\b(forget (the )?(previous|last) topic|forget (that|this)|"
    r"start (a )?new investigation|new investigation|start over|reset the conversation)\b",
    re.IGNORECASE,
)

# Matches every specialist agent's `source_entities` convention, e.g.
# "person_123", "fir_456", "account_78" — see AgentFinding.source_entities
# in backend/agents/base/finding.py and every agent's own construction
# calls. Sprint 2 extends the kind set to everything agents actually emit
# (grep confirms: person, fir, account, crime, location, officer,
# organization, property, weapon — crime/location/officer are excluded
# below because no C2 reference phrase targets them yet).
_ENTITY_REF = re.compile(r"^(person|fir|account|organization|property|weapon)_(\d+)$")

_KIND_MODEL = {
    "person": Person, "fir": FIR, "account": BankAccount,
    "organization": Organization, "property": Property, "weapon": Weapon,
}


def _label_for(session, kind: str, entity_id: int) -> str:
    model = _KIND_MODEL.get(kind)
    if model is None:
        return f"{kind} #{entity_id}"
    row = session.get(model, entity_id)
    if row is None:
        return f"{kind} #{entity_id}"
    if kind == "person":
        return row.name
    if kind == "fir":
        return row.fir_number
    if kind == "account":
        return f"{row.bank} account {row.account_number}"
    if kind == "organization":
        return row.name
    if kind in ("property", "weapon"):
        return row.description or f"{kind} #{entity_id}"
    return f"{kind} #{entity_id}"


@dataclass
class ClarificationOption:
    id: int
    kind: str
    label: str


@dataclass
class ResolveResult:
    """Result of resolving one raw query against session history.

    Exactly one of these is true of a "live" result:
      - `needs_clarification` is True: don't run the investigation
        pipeline yet; ask `clarification_question` and wait for the
        person to pick one of `clarification_options`.
      - otherwise: `resolved_query` is ready to hand to the orchestrator
        (identical to the raw query if nothing needed resolving).
    `topic_reset` is independent of the above — it just means this turn's
    resolution deliberately ignored everything before it.
    """
    resolved_query: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    clarification_options: list[ClarificationOption] = field(default_factory=list)
    clarification_reference: str | None = None   # the ambiguous phrase itself, e.g. "him"
    topic_reset: bool = False
    reset_phrase: str | None = None
    unsupported_reference: str | None = None      # set (not blocking) if an unsupported phrase was seen


class ConversationMemoryService:
    """Reads/writes ConversationTurn rows for one InvestigationSession."""

    def __init__(self, session):
        self.session = session  # SQLAlchemy session (matches DatabaseService's own naming)

    # -- reads ---------------------------------------------------------------

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
        Used by Stage C5's board intelligence."""
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

    # -- Sprint 2: resolution (disambiguation / clarification / reset) -------

    def resolve_turn(self, session_id: int, raw_query: str) -> ResolveResult:
        """The real entry point going forward — supersedes `resolve_query`
        (kept below, unchanged, for anything still calling it directly).
        Handles reset phrases and clarification answers first, then
        multi-entity disambiguation, then falls back to Sprint 1's
        single-best-guess substitution."""

        # 1. Topic reset takes priority over everything else — an explicit
        # "forget the previous topic" should never be swallowed by a
        # pending clarification or treated as an answer to one.
        reset_match = _RESET_PATTERNS.search(raw_query)
        if reset_match:
            remainder = _RESET_PATTERNS.sub("", raw_query).strip(" ,.")
            return ResolveResult(
                resolved_query=remainder,
                topic_reset=True,
                reset_phrase=reset_match.group(0),
            )

        last_turn = self.get_last_turn(session_id)
        if last_turn is None:
            return ResolveResult(resolved_query=raw_query)

        # 2. Is this turn answering a pending clarification question?
        if last_turn.pending_clarification_json:
            pending = json.loads(last_turn.pending_clarification_json)
            chosen = self._match_clarification_answer(raw_query, pending.get("options", []))
            if chosen is not None:
                origin_query = pending.get("origin_query", raw_query)
                reference = pending.get("reference", "")
                resolved = origin_query
                if reference:
                    resolved = re.sub(re.escape(reference), chosen["label"], origin_query,
                                       flags=re.IGNORECASE)
                return ResolveResult(resolved_query=resolved)
            # Didn't match any offered option — fall through and treat this
            # as a fresh query rather than getting stuck re-asking forever.

        # 3. Ordinal person references ("the second accused") — resolved
        # against *this* turn's own last-turn entity_mentions, no
        # ambiguity check needed since the ordinal itself disambiguates.
        ordinal_match = _ORDINAL_PERSON_REF.search(raw_query)
        if ordinal_match and last_turn.entity_mentions_json:
            idx = _ORDINAL_WORDS[ordinal_match.group(1).lower()]
            persons = [m for m in json.loads(last_turn.entity_mentions_json) if m["kind"] == "person"]
            if idx < len(persons):
                resolved = _ORDINAL_PERSON_REF.sub(persons[idx]["label"], raw_query)
                return ResolveResult(resolved_query=resolved)

        # 4. Multi-entity disambiguation for plain pronouns/refs.
        #
        # Capped at MAX_CLARIFICATION_OPTIONS: a broad query ("show repeat
        # offenders in Mysuru") can legitimately surface dozens of distinct
        # people across agents — that's a *list*, not the "Show Ravi and
        # Manoj -> tell me about him" ambiguity the brief describes.
        # Asking "which of 41 people?" isn't a usable clarification, so
        # past the cap this falls through to Sprint 1's single-best-guess
        # (most-recently-mentioned) instead of blocking on a question
        # nobody can answer productively.
        if last_turn.entity_mentions_json:
            mentions = json.loads(last_turn.entity_mentions_json)
            for pattern, kind in ((_PERSON_PRONOUNS, "person"), (_ACCOUNT_REF, "account"),
                                   (_ORG_REF, "organization"), (_PROPERTY_REF, "property"),
                                   (_WEAPON_REF, "weapon")):
                m = pattern.search(raw_query)
                if not m:
                    continue
                distinct = {(x["kind"], x["id"]): x for x in mentions if x["kind"] == kind}
                if 1 < len(distinct) <= MAX_CLARIFICATION_OPTIONS:
                    options = [ClarificationOption(id=x["id"], kind=x["kind"], label=x["label"])
                               for x in distinct.values()]
                    return ResolveResult(
                        resolved_query=raw_query,
                        needs_clarification=True,
                        clarification_question=f"Which {kind}?",
                        clarification_options=options,
                        clarification_reference=m.group(0),
                    )

        # 5. Unsupported-but-recognized references — don't silently ignore.
        unsupported = _UNSUPPORTED_REF.search(raw_query)

        # 6. Fall back to Sprint 1's single-best-guess substitution.
        resolved = self.resolve_query(session_id, raw_query)
        return ResolveResult(resolved_query=resolved,
                              unsupported_reference=unsupported.group(0) if unsupported else None)

    @staticmethod
    def _match_clarification_answer(raw_query: str, options: list[dict]) -> dict | None:
        """Best-effort match of a clarification reply against the options
        that were offered: an ordinal ("the first one", "second"), the
        option's full label appearing in the reply, or the reply being a
        (multi-word-safe) fragment of the label — e.g. replying "Advik"
        to an offered "Advik Maharaj"."""
        q = raw_query.strip().lower()
        for word, idx in _ORDINAL_WORDS.items():
            if word in q and idx < len(options):
                return options[idx]
        for opt in options:
            label = opt["label"].lower()
            if label in q or q in label:
                return opt
        return None

    # -- Sprint 1: single-best-guess resolution (unchanged) -------------------

    def resolve_query(self, session_id: int, raw_query: str) -> str:
        """Best-effort substitution of pronouns/refs with the last known
        entity name, so the query handed to the orchestrator is
        self-contained (e.g. "expand his network" ->
        "expand Ravi Kumar's network"). Returns raw_query unchanged if
        there's no prior turn or nothing to substitute against.

        Kept as its own method (rather than folded into `resolve_turn`)
        because `board_intelligence.py` and any future direct caller that
        just wants "give me your best guess, no clarification flow" can
        still call this exactly as before."""
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

        # Sprint 2: same pattern, extended kinds, via entity_mentions_json
        # (generic — no dedicated last_organization_id/last_property_id/
        # last_weapon_id columns; see the model's own note on why three
        # dedicated columns was already a judgment call, not a rule).
        if last_turn.entity_mentions_json:
            mentions = json.loads(last_turn.entity_mentions_json)
            for pattern, kind in ((_ORG_REF, "organization"), (_PROPERTY_REF, "property"),
                                   (_WEAPON_REF, "weapon")):
                if not pattern.search(resolved):
                    continue
                same_kind = [m for m in mentions if m["kind"] == kind]
                if len(same_kind) == 1:
                    resolved = pattern.sub(same_kind[-1]["label"], resolved)

        return resolved

    # -- writes ----------------------------------------------------------------

    def record_turn(self, session_id: int, raw_query: str, resolved_query: str,
                     final_state: dict | None = None,
                     pending_clarification: ResolveResult | None = None,
                     topic_reset_phrase: str | None = None) -> ConversationTurn:
        """Persist this turn. `final_state` is omitted (None) for a
        clarification-question turn, since the pipeline never ran.
        `pending_clarification` (Sprint 2) carries the question/options to
        store so the *next* turn can check `resolve_turn` against it."""
        last_turn = self.get_last_turn(session_id)
        next_index = 0 if last_turn is None else last_turn.turn_index + 1

        # BUGFIX (Stage C0): `final_state` as passed in by
        # stream_investigation is LangGraph's *last node's diff*, so the
        # fully compiled findings list lives in
        # `final_state["final_report"]["findings"]`, not `final_state["findings"]`.
        report = (final_state or {}).get("final_report") or {}
        findings = report.get("findings") or (final_state or {}).get("findings") or []

        person_id = self._last_ref(findings, "person")
        fir_id = self._last_ref(findings, "fir")
        account_id = self._last_ref(findings, "account")

        # Sprint 2: topic_reset clears carry-forward — this turn's pointers
        # start from whatever *this* turn's own findings introduce, not
        # from before the reset boundary. A turn with no findings after a
        # reset (e.g. the reset phrase alone) legitimately has no pointers.
        carry_forward = last_turn if not topic_reset_phrase else None

        last_person_id = person_id if person_id is not None else (carry_forward.last_person_id if carry_forward else None)
        last_person_name = self._person_name(person_id) if person_id is not None else \
            (carry_forward.last_person_name if carry_forward else None)
        last_fir_id = fir_id if fir_id is not None else (carry_forward.last_fir_id if carry_forward else None)
        last_account_id = account_id if account_id is not None else (carry_forward.last_account_id if carry_forward else None)

        response_summary = report.get("summary") or report.get("narrative") if isinstance(report, dict) else None

        entity_mentions = self._extract_all_mentions(findings) if findings else \
            (json.loads(carry_forward.entity_mentions_json) if carry_forward and carry_forward.entity_mentions_json else None)

        pending_json = None
        if pending_clarification is not None and pending_clarification.needs_clarification:
            pending_json = json.dumps({
                "question": pending_clarification.clarification_question,
                "reference": pending_clarification.clarification_reference,
                "origin_query": raw_query,
                "options": [
                    {"id": o.id, "kind": o.kind, "label": o.label}
                    for o in pending_clarification.clarification_options
                ],
            })

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
            entity_mentions_json=json.dumps(entity_mentions) if entity_mentions else None,
            pending_clarification_json=pending_json,
            topic_reset=topic_reset_phrase,
        )
        self.session.add(turn)
        self.session.commit()
        self.session.refresh(turn)

        self.maybe_summarize(session_id)

        return turn

    # -- extraction helpers -------------------------------------------------

    @staticmethod
    def _last_ref(findings: list, kind: str) -> int | None:
        """Last `source_entities` match of the given kind across every
        finding this turn, in agent execution order."""
        match_id = None
        for finding in findings:
            for ref in finding.get("source_entities") or []:
                m = _ENTITY_REF.match(ref)
                if m and m.group(1) == kind:
                    match_id = int(m.group(2))
        return match_id

    def _extract_all_mentions(self, findings: list) -> list[dict]:
        """Every distinct (kind, id) mentioned this turn, in first-seen
        order, with a resolved display label — the superset Sprint 1's
        `_last_ref` narrows down to "just the last one"."""
        seen = {}
        for finding in findings:
            for ref in finding.get("source_entities") or []:
                m = _ENTITY_REF.match(ref)
                if not m:
                    continue
                kind, entity_id = m.group(1), int(m.group(2))
                key = (kind, entity_id)
                if key in seen:
                    continue
                seen[key] = {"kind": kind, "id": entity_id, "label": _label_for(self.session, kind, entity_id)}
        return list(seen.values())

    def _person_name(self, person_id: int | None) -> str | None:
        if person_id is None:
            return None
        person = self.session.get(Person, person_id)
        return person.name if person else None

    # -- Sprint 2, item 3: conversation summarization -------------------------

    def maybe_summarize(self, session_id: int, threshold: int = 8, keep_recent: int = 3) -> None:
        """If this session has grown past `threshold` turns, fold every
        turn older than the most recent `keep_recent` into
        `InvestigationSession.context_summary`, a rolling compressed
        summary. Database history (`ConversationTurn` rows) is never
        deleted or altered — this only maintains a compressed *view* for
        prompt-context use. Uses Claude if ANTHROPIC_API_KEY is set (same
        graceful-degrade pattern as ChiefAgent._generate_narrative);
        otherwise a deterministic bullet list of raw queries + summaries.

        This does not (yet) feed into ChiefAgent's own synthesis prompt —
        doing that would mean touching chief/agent.py, which the Golden
        Rules reserve for bug fixes only. It's exposed here and via the
        conversation-timeline API for a future sprint to wire in without
        needing a new mechanism."""
        turns = self.get_history(session_id)
        if len(turns) <= threshold:
            return

        session_row = self.session.get(InvestigationSession, session_id)
        if session_row is None:
            return

        already_through = session_row.context_summary_through_turn
        fold_range = turns[:-keep_recent] if keep_recent else turns
        fold_range = [t for t in fold_range if already_through is None or t.turn_index > already_through]
        if not fold_range:
            return

        new_summary = self._summarize_turns(fold_range, session_row.context_summary)
        session_row.context_summary = new_summary
        session_row.context_summary_through_turn = fold_range[-1].turn_index
        self.session.commit()

    def _summarize_turns(self, turns: list[ConversationTurn], prior_summary: str | None) -> str:
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                return self._summarize_turns_llm(turns, prior_summary)
            except Exception:
                logger.warning("LLM conversation summarization failed, falling back to template", exc_info=True)
        return self._summarize_turns_template(turns, prior_summary)

    def _summarize_turns_template(self, turns: list[ConversationTurn], prior_summary: str | None) -> str:
        lines = [prior_summary] if prior_summary else []
        for t in turns:
            bullet = f"- Turn {t.turn_index}: asked \"{t.raw_query}\""
            if t.response_summary:
                bullet += f" -> {t.response_summary[:160]}"
            lines.append(bullet)
        return "\n".join(l for l in lines if l)

    def _summarize_turns_llm(self, turns: list[ConversationTurn], prior_summary: str | None) -> str:
        from anthropic import Anthropic

        client = Anthropic()
        transcript = "\n".join(
            f"Turn {t.turn_index} — asked: {t.raw_query}"
            + (f" | answered: {t.response_summary[:300]}" if t.response_summary else "")
            for t in turns
        )
        prior = f"Prior summary so far:\n{prior_summary}\n\n" if prior_summary else ""
        prompt = (
            "You are compressing an investigator's conversation history with "
            "SHERLOCK, a crime intelligence system, so older turns take less "
            "space in future prompts. Summarize the turns below into a short "
            "list of the concrete entities, findings, and open threads "
            "raised — not a narrative. Merge with the prior summary if given. "
            "Do not invent facts not present in the turns.\n\n"
            f"{prior}Turns to fold in:\n{transcript}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
