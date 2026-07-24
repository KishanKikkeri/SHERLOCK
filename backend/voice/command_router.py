"""
SHERLOCK — Stage C3: Voice Command Router.

The browser-side voice layer (`frontend/src/hooks/useVoice.ts`,
`lib/voice-commands.ts`) already exists and is complete for what it
covers: wake-word detection, push-to-talk, TTS, and a small board-UI
command vocabulary (add sticky, zoom, pan, present...). That part is not
touched here.

What's missing — and what this module adds — is the *investigation-level*
voice workflow the Stage C3 brief's own example calls for:

    Sherlock -> Open burglary investigation -> Assign Inspector Ravi ->
    Show all witnesses -> Who owns this vehicle? -> Open evidence board ->
    Generate report -> Read report aloud -> Close case

None of those are board-UI actions — they're session lifecycle (C1),
investigation queries (existing WS pipeline), and board intelligence
(C5). This router is the one place that takes the transcribed text
(after the browser's wake-word/STT already turned speech into a string)
and decides which of those subsystems handles it, then returns a short,
speakable response for the browser to read back via `useVoice`'s
existing `speak()`.

Deliberately simple keyword/phrase matching, same philosophy as
`voice-commands.ts` on the frontend: a small, fixed vocabulary, no LLM
round-trip for classification. Anything that doesn't match a known
lifecycle/board pattern falls through to the investigation pipeline as
a free-text query — that's the right default, since "show all witnesses"
is not meaningfully different from typing the same words.
"""

from __future__ import annotations

import re

from backend.api.investigation_stream import run_investigation_once
from backend.database.service import DatabaseService
from backend.graph.service import get_graph_service
from backend.intelligence.board_intelligence import BoardIntelligenceService
from backend.intelligence.executive_summary import build_executive_report
from backend.memory.conversation_memory import ConversationMemoryService

# Compact narrative for TTS — the Chief's full narrative can run long;
# voice responses should be a sentence or two, not a report readout,
# except when the user explicitly asks to "read the report aloud".
_SPOKEN_TRUNCATE = 400


def _truncate(text: str, limit: int = _SPOKEN_TRUNCATE) -> str:
    if not text or len(text) <= limit:
        return text
    cut = text[:limit].rsplit(". ", 1)[0]
    return (cut or text[:limit]) + "."


class VoiceCommandResult:
    def __init__(self, intent: str, spoken_response: str, data: dict | None = None,
                 session_id: int | None = None):
        self.intent = intent
        self.spoken_response = spoken_response
        self.data = data or {}
        self.session_id = session_id

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "spoken_response": self.spoken_response,
            "session_id": self.session_id,
            "data": self.data,
        }


_OPEN_CASE = re.compile(r"^\s*open\s+(?:a\s+|the\s+|new\s+)*(.+?)\s*(?:investigation|case)?\s*$", re.IGNORECASE)
_CLOSE_CASE = re.compile(r"\bclose\s+(?:the\s+|this\s+)?(?:case|investigation)\b", re.IGNORECASE)
_REOPEN_CASE = re.compile(r"\breopen\s+(?:the\s+|this\s+)?(?:case|investigation)\b", re.IGNORECASE)
_ARCHIVE_CASE = re.compile(r"\barchive\s+(?:the\s+|this\s+)?(?:case|investigation)\b", re.IGNORECASE)
_ASSIGN = re.compile(
    r"\bassign\s+(?:inspector|officer|constable|si|asi|psi|ci)?\s*([a-z][a-z .]*)$",
    re.IGNORECASE,
)
_OPEN_BOARD = re.compile(r"\b(?:open|show)\s+(?:the\s+)?(?:evidence\s+)?board\b", re.IGNORECASE)
_GENERATE_REPORT = re.compile(r"\bgenerate\s+(?:a\s+|the\s+)?report\b", re.IGNORECASE)
_READ_REPORT = re.compile(r"\bread\s+(?:the\s+|that\s+)?report(?:\s+aloud)?\b", re.IGNORECASE)
_VEHICLE_OWNER = re.compile(r"\bwho\s+owns\s+(?:this|that|the)\s+vehicle\b", re.IGNORECASE)
_FREEZE_ACCOUNT = re.compile(r"\bfreeze\s+(?:that|this|the)\s+account\b", re.IGNORECASE)


class VoiceCommandRouter:
    """One instance per request — takes a DB session, executes the
    matched intent, and returns a VoiceCommandResult. Session-lifecycle
    intents (open/close/reopen/archive/assign) require `session_id`
    except `open_case`, which creates one."""

    def __init__(self, db_session):
        self.session = db_session
        self.svc = DatabaseService(db_session)

    async def route(self, transcript: str, session_id: int | None = None) -> VoiceCommandResult:
        text = transcript.strip()
        if not text:
            return VoiceCommandResult("empty", "I didn't catch that — try again.", session_id=session_id)

        if _CLOSE_CASE.search(text):
            return self._close_case(session_id)
        if _REOPEN_CASE.search(text):
            return self._reopen_case(session_id)
        if _ARCHIVE_CASE.search(text):
            return self._archive_case(session_id)

        m = _ASSIGN.search(text)
        if m:
            return self._assign(session_id, m.group(1).strip())

        if _OPEN_BOARD.search(text):
            return await self._open_board(session_id)

        if _READ_REPORT.search(text):
            return self._read_report(session_id)
        if _GENERATE_REPORT.search(text):
            return await self._generate_report(session_id, text)

        if _VEHICLE_OWNER.search(text):
            return self._vehicle_owner(session_id)

        if _FREEZE_ACCOUNT.search(text):
            return VoiceCommandResult(
                "freeze_account",
                "Freezing accounts isn't wired up yet — that needs a real banking-side "
                "action, not just a database flag. I can flag the account for review instead, "
                "or you can raise it through Decision Support's recommended actions.",
                session_id=session_id,
            )

        m = _OPEN_CASE.match(text)
        if m and session_id is None:
            # Only treat "open ___" as case-creation when there's no active
            # session yet — "open burglary investigation" mid-session
            # (session_id already set) more likely means "investigate
            # burglary", handled by the free-text fallback below.
            return self._open_case(m.group(1).strip() or "Untitled investigation")

        # Fallback: free-text investigation query (e.g. "show all witnesses",
        # "who is Ravi Kumar", "tell me about the burglary case") — this is
        # the majority of real voice input and is exactly what the existing
        # investigation pipeline (with Stage C2 conversation memory, if
        # session_id is set) already handles.
        return await self._investigate(session_id, text)

    # -- intents -------------------------------------------------------

    def _open_case(self, title: str) -> VoiceCommandResult:
        row = self.svc.open_case(title=title.capitalize())
        return VoiceCommandResult(
            "open_case",
            f"Opened {row.session_code}: {row.title}. What would you like to look at first?",
            data={"session_code": row.session_code, "title": row.title},
            session_id=row.id,
        )

    def _close_case(self, session_id: int | None) -> VoiceCommandResult:
        if session_id is None:
            return VoiceCommandResult("close_case", "There's no open case to close.", session_id=None)
        row = self.svc.close_case(session_id, detail="Closed via voice command.")
        if row is None:
            return VoiceCommandResult("close_case", "I couldn't find that case.", session_id=session_id)
        return VoiceCommandResult("close_case", f"{row.session_code} closed.", session_id=session_id)

    def _reopen_case(self, session_id: int | None) -> VoiceCommandResult:
        if session_id is None:
            return VoiceCommandResult("reopen_case", "There's no case to reopen.", session_id=None)
        try:
            row = self.svc.reopen_case(session_id, detail="Reopened via voice command.")
        except ValueError as e:
            return VoiceCommandResult("reopen_case", str(e), session_id=session_id)
        if row is None:
            return VoiceCommandResult("reopen_case", "I couldn't find that case.", session_id=session_id)
        return VoiceCommandResult("reopen_case", f"{row.session_code} reopened.", session_id=session_id)

    def _archive_case(self, session_id: int | None) -> VoiceCommandResult:
        if session_id is None:
            return VoiceCommandResult("archive_case", "There's no case to archive.", session_id=None)
        row = self.svc.archive_case(session_id, detail="Archived via voice command.")
        if row is None:
            return VoiceCommandResult("archive_case", "I couldn't find that case.", session_id=session_id)
        return VoiceCommandResult("archive_case", f"{row.session_code} archived.", session_id=session_id)

    def _assign(self, session_id: int | None, name_fragment: str) -> VoiceCommandResult:
        if session_id is None:
            return VoiceCommandResult("assign", "Open a case first, then I can assign an investigator to it.",
                                       session_id=None)
        officer = self.svc.find_officer_by_name(name_fragment)
        if officer is None:
            return VoiceCommandResult("assign", f"I couldn't find an officer matching '{name_fragment}'.",
                                       session_id=session_id)
        assignment = self.svc.assign_investigator(session_id, officer.id, role="investigator")
        if assignment is None:
            return VoiceCommandResult("assign", "I couldn't find that case.", session_id=session_id)
        return VoiceCommandResult(
            "assign", f"{officer.name} assigned to the case.",
            data={"officer_id": officer.id, "officer_name": officer.name},
            session_id=session_id,
        )

    async def _open_board(self, session_id: int | None) -> VoiceCommandResult:
        if session_id is None:
            return VoiceCommandResult("open_board", "Open a case first, then I can pull up its board.",
                                       session_id=None)
        graph_service = get_graph_service(backend="networkx", session=self.session)
        board = BoardIntelligenceService(self.session, graph_service).build(session_id)
        n_links = len(board["suggested_links"])
        n_hidden = len(board["hidden_connections"])
        n_gaps = len(board["missing_evidence"])
        spoken = (
            f"Board ready. {board['evidence_summary']['finding_count']} findings so far, "
            f"{n_links} suggested link{'s' if n_links != 1 else ''}"
            + (f", {n_hidden} hidden connection{'s' if n_hidden != 1 else ''}" if n_hidden else "")
            + (f", {n_gaps} evidence gap{'s' if n_gaps != 1 else ''} flagged" if n_gaps else "")
            + "."
        )
        return VoiceCommandResult("open_board", spoken, data=board, session_id=session_id)

    def _read_report(self, session_id: int | None) -> VoiceCommandResult:
        if session_id is None:
            return VoiceCommandResult("read_report", "There's no report yet — open a case and ask me something first.",
                                       session_id=None)
        memory = ConversationMemoryService(self.session)
        last_turn = memory.get_last_turn(session_id)
        if last_turn is None or not last_turn.response_summary:
            return VoiceCommandResult("read_report", "There's no report yet for this case.", session_id=session_id)
        return VoiceCommandResult("read_report", last_turn.response_summary, session_id=session_id)

    async def _generate_report(self, session_id: int | None, text: str) -> VoiceCommandResult:
        query = "Generate a full investigation summary report for this case."
        report = await run_investigation_once(query, session_id=session_id)
        narrative = report.get("narrative") or "Report generated."
        return VoiceCommandResult(
            "generate_report", _truncate(narrative),
            data={"final_report": report}, session_id=session_id,
        )

    def _vehicle_owner(self, session_id: int | None) -> VoiceCommandResult:
        if session_id is None:
            return VoiceCommandResult("vehicle_owner", "I don't have a case open to check vehicles against.",
                                       session_id=None)
        memory = ConversationMemoryService(self.session)
        last_turn = memory.get_last_turn(session_id)
        fir_id = last_turn.last_fir_id if last_turn else None
        if fir_id is None:
            return VoiceCommandResult(
                "vehicle_owner",
                "I'm not sure which vehicle you mean — ask about a specific case first.",
                session_id=session_id,
            )
        vehicles = self.svc.find_vehicles_by_fir(fir_id)
        if not vehicles:
            return VoiceCommandResult("vehicle_owner", "No vehicle is on record for this case.",
                                       session_id=session_id)
        owners = []
        for v in vehicles:
            owner = self.svc.get_person(v.owner_id)
            if owner:
                owners.append(f"{v.registration_number} is registered to {owner.name}")
        spoken = "; ".join(owners) if owners else "I found a vehicle but couldn't resolve its owner."
        return VoiceCommandResult("vehicle_owner", spoken, session_id=session_id)

    async def _investigate(self, session_id: int | None, text: str) -> VoiceCommandResult:
        report = await run_investigation_once(text, session_id=session_id)
        narrative = report.get("narrative") or "I didn't find anything on that."
        executive_report = build_executive_report(report)
        return VoiceCommandResult(
            "investigate", _truncate(narrative),
            # `final_report` is kept verbatim (all validated + rejected
            # findings, full narrative) for a "Show Agent Trace" view.
            # `executive_report` is the structured, ranked, counted
            # summary the Analytics cards render by default — see
            # backend/intelligence/executive_summary.py.
            data={"final_report": report, "executive_report": executive_report},
            session_id=session_id,
        )
