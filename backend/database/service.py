"""
SHERLOCK — Stage A, Phase A4: DatabaseService.

Per the handover: "Agents should never perform SQL directly. Everything
goes through DatabaseService. Only DatabaseService knows SQL."

Important scoping note: the 11 existing agents were explicitly frozen for
Stage A (Golden Rule — no agent changes) and already work correctly via
direct SQLAlchemy queries against the compatibility-exported model names
(see models/__init__.py and models/compat.py), which is what actually
satisfies "every existing agent continues calling the same high-level
API" for them. Routing those 11 agents through this class as well would
mean editing their source files, which Phase A6/A7 explicitly scope as
"rewrite queries, keep public interfaces unchanged" — not "rewrite
agents." So: this class exists as the abstraction Phase A4 asks for, and
is the intended entry point for Phase A3 loaders and any new agent
(Asset Intelligence, Officer & Accountability, etc. — see
docs/AGENT_MAPPING.md Part 2), but wiring the 11 existing agents through
it is optional follow-up cleanup, not required for Stage A completion.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from datetime import datetime

from backend.database.models import (
    Person, Location, Crime, FIR, Accused, Victim, Witness, Officer,
    BankAccount, Transaction, Vehicle, Phone, Property, PersonCrimeLink,
    PersonRole,
    InvestigationSession, SessionAssignment, SessionActivity,
    InvestigationSessionStatus, InvestigationPriority,
)


class DatabaseService:
    """The only class in Stage A's new code that is allowed to know SQL,
    per the handover's Phase A4. Every method here is a thin, real query —
    no placeholders."""

    def __init__(self, session: Session):
        self.session = session

    # -- FIR -----------------------------------------------------------

    def get_fir(self, fir_id: int) -> FIR | None:
        return self.session.get(FIR, fir_id)

    def get_fir_by_number(self, fir_number: str) -> FIR | None:
        return self.session.query(FIR).filter_by(fir_number=fir_number).first()

    def get_case(self, fir_id: int) -> FIR | None:
        """Alias for get_fir — 'case' is the handover's own term for this
        in Phase A4's method list; FIR is the case record in this schema."""
        return self.get_fir(fir_id)

    def get_case_timeline(self, fir_id: int) -> list[dict]:
        """Ordered list of everything on record for this FIR: filing,
        investigation start/end, arrests, chargesheet — a real
        chronological reconstruction, not the crime-pattern timeline the
        Timeline Reconstruction Agent already does (that one stays
        untouched; this is case-process timeline, a different question)."""
        fir = self.get_fir(fir_id)
        if not fir:
            return []

        events = [{"date": fir.filed_date, "event": f"FIR {fir.fir_number} filed", "type": "fir_filed"}]
        for inv in fir.investigations:
            events.append({"date": inv.start_date, "event": f"Investigation opened by officer {inv.officer_id}", "type": "investigation_start"})
            if inv.end_date:
                events.append({"date": inv.end_date, "event": "Investigation closed", "type": "investigation_end"})
        for arrest in fir.arrests:
            events.append({"date": arrest.arrest_date, "event": f"Person {arrest.person_id} arrested ({arrest.status.value})", "type": "arrest"})
        for cs in fir.chargesheets:
            events.append({"date": cs.filed_date, "event": f"Chargesheet filed ({cs.status.value})", "type": "chargesheet"})

        return sorted(events, key=lambda e: e["date"])

    # -- Person / role entities -----------------------------------------

    def get_person(self, person_id: int) -> Person | None:
        return self.session.get(Person, person_id)

    def get_accused(self, accused_id: int) -> Accused | None:
        return self.session.get(Accused, accused_id)

    def get_victim(self, victim_id: int) -> Victim | None:
        return self.session.get(Victim, victim_id)

    def get_witness(self, witness_id: int) -> Witness | None:
        return self.session.get(Witness, witness_id)

    def get_officer(self, officer_id: int) -> Officer | None:
        return self.session.get(Officer, officer_id)

    def get_person_history(self, person_id: int) -> dict:
        """Every case-role appearance a person has across the whole
        database — accused, victim, witness records, in one place."""
        return {
            "person": self.get_person(person_id),
            "accused_in": self.session.query(Accused).filter_by(person_id=person_id).all(),
            "victim_in": self.session.query(Victim).filter_by(person_id=person_id).all(),
            "witness_in": self.session.query(Witness).filter_by(person_id=person_id).all(),
        }

    def get_repeat_offenders(self, min_crimes: int = 2) -> list[Person]:
        """Persons with >= min_crimes distinct Accused records — the same
        definition Network Analysis Agent uses via the graph, exposed here
        as a direct SQL path for anything that needs it without a graph
        service (e.g. Phase A3 loaders doing a sanity check after import)."""
        from sqlalchemy import func

        rows = (
            self.session.query(Accused.person_id, func.count(Accused.id).label("crime_count"))
            .group_by(Accused.person_id)
            .having(func.count(Accused.id) >= min_crimes)
            .all()
        )
        person_ids = [r.person_id for r in rows]
        if not person_ids:
            return []
        return self.session.query(Person).filter(Person.id.in_(person_ids)).all()

    # -- Financial --------------------------------------------------------

    def get_bank_accounts(self, owner_id: int | None = None, flagged_mule_only: bool = False) -> list[BankAccount]:
        query = self.session.query(BankAccount)
        if owner_id is not None:
            query = query.filter_by(owner_id=owner_id)
        if flagged_mule_only:
            query = query.filter_by(is_flagged_mule=True)
        return query.all()

    def get_transactions(self, account_id: int | None = None, suspicious_only: bool = False) -> list[Transaction]:
        query = self.session.query(Transaction)
        if account_id is not None:
            from sqlalchemy import or_
            query = query.filter(
                or_(Transaction.sender_account_id == account_id, Transaction.receiver_account_id == account_id)
            )
        if suspicious_only:
            query = query.filter_by(is_suspicious=True)
        return query.all()

    # -- Property -----------------------------------------------------------

    def get_property(self, property_id: int | None = None, fir_id: int | None = None) -> list[Property]:
        query = self.session.query(Property)
        if property_id is not None:
            single = self.session.get(Property, property_id)
            return [single] if single else []
        if fir_id is not None:
            query = query.filter_by(fir_id=fir_id)
        return query.all()

    # -- Investigation Sessions (Stage C1) ---------------------------------
    #
    # "Sherlock, open a new case" and friends. These methods are the only
    # place that writes InvestigationSession/SessionAssignment/SessionActivity
    # rows — mirrors this file's own rule ("agents never do SQL directly")
    # for the new lifecycle tables, and every state transition also appends
    # a SessionActivity row so the session has a real audit trail from day one.

    def _next_session_code(self) -> str:
        year = datetime.utcnow().year
        count = self.session.query(InvestigationSession).count() + 1
        return f"SESSION-{year}-{count:04d}"

    def _log_activity(self, session_row: InvestigationSession, event_type: str,
                       actor_officer_id: int | None = None, detail: str | None = None) -> None:
        self.session.add(SessionActivity(
            session_id=session_row.id,
            event_type=event_type,
            actor_officer_id=actor_officer_id,
            detail=detail,
        ))

    def open_case(self, title: str, fir_id: int | None = None,
                  opened_by_officer_id: int | None = None,
                  priority=None, notes: str | None = None) -> InvestigationSession:
        """'Sherlock, open a new case.' Creates the session and its first
        audit-trail entry in one transaction."""
        row = InvestigationSession(
            session_code=self._next_session_code(),
            title=title,
            fir_id=fir_id,
            status=InvestigationSessionStatus.OPEN,
            priority=priority or InvestigationPriority.MEDIUM,
            opened_by_officer_id=opened_by_officer_id,
            owner_officer_id=opened_by_officer_id,
            notes=notes,
        )
        self.session.add(row)
        self.session.flush()  # need row.id for the activity FK
        self._log_activity(row, "opened", opened_by_officer_id, detail=f"Session opened: {title}")
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_session(self, session_id: int) -> InvestigationSession | None:
        return self.session.get(InvestigationSession, session_id)

    def get_session_by_code(self, session_code: str) -> InvestigationSession | None:
        return self.session.query(InvestigationSession).filter_by(session_code=session_code).first()

    def list_sessions(self, status=None, owner_officer_id: int | None = None) -> list[InvestigationSession]:
        query = self.session.query(InvestigationSession)
        if status is not None:
            query = query.filter_by(status=status)
        if owner_officer_id is not None:
            query = query.filter_by(owner_officer_id=owner_officer_id)
        return query.order_by(InvestigationSession.updated_at.desc()).all()

    def close_case(self, session_id: int, actor_officer_id: int | None = None,
                    detail: str | None = None) -> InvestigationSession | None:
        row = self.get_session(session_id)
        if row is None:
            return None
        row.status = InvestigationSessionStatus.CLOSED
        row.closed_at = datetime.utcnow()
        self._log_activity(row, "closed", actor_officer_id, detail)
        self.session.commit()
        self.session.refresh(row)
        return row

    def reopen_case(self, session_id: int, actor_officer_id: int | None = None,
                     detail: str | None = None) -> InvestigationSession | None:
        row = self.get_session(session_id)
        if row is None:
            return None
        if row.status == InvestigationSessionStatus.ARCHIVED:
            raise ValueError("Cannot reopen an archived session — archiving is terminal. "
                              "Open a new session against the same FIR instead.")
        row.status = InvestigationSessionStatus.REOPENED
        row.reopened_at = datetime.utcnow()
        row.closed_at = None
        self._log_activity(row, "reopened", actor_officer_id, detail)
        self.session.commit()
        self.session.refresh(row)
        return row

    def archive_case(self, session_id: int, actor_officer_id: int | None = None,
                      detail: str | None = None) -> InvestigationSession | None:
        row = self.get_session(session_id)
        if row is None:
            return None
        row.status = InvestigationSessionStatus.ARCHIVED
        row.archived_at = datetime.utcnow()
        self._log_activity(row, "archived", actor_officer_id, detail)
        self.session.commit()
        self.session.refresh(row)
        return row

    def update_session_metadata(self, session_id: int, actor_officer_id: int | None = None,
                                 title: str | None = None, priority=None,
                                 notes: str | None = None) -> InvestigationSession | None:
        row = self.get_session(session_id)
        if row is None:
            return None
        changed = []
        if title is not None:
            row.title = title
            changed.append("title")
        if priority is not None:
            row.priority = priority
            changed.append("priority")
        if notes is not None:
            row.notes = notes
            changed.append("notes")
        if changed:
            self._log_activity(row, "metadata_changed", actor_officer_id, detail=f"Changed: {', '.join(changed)}")
        self.session.commit()
        self.session.refresh(row)
        return row

    def assign_investigator(self, session_id: int, officer_id: int, role: str = "investigator",
                             actor_officer_id: int | None = None) -> SessionAssignment | None:
        session_row = self.get_session(session_id)
        if session_row is None:
            return None
        assignment = SessionAssignment(session_id=session_id, officer_id=officer_id, role=role)
        self.session.add(assignment)
        self._log_activity(session_row, "assigned", actor_officer_id,
                            detail=f"Officer {officer_id} assigned as {role}")
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def unassign_investigator(self, session_id: int, officer_id: int,
                               actor_officer_id: int | None = None) -> bool:
        session_row = self.get_session(session_id)
        if session_row is None:
            return False
        assignment = (
            self.session.query(SessionAssignment)
            .filter_by(session_id=session_id, officer_id=officer_id, unassigned_at=None)
            .first()
        )
        if assignment is None:
            return False
        assignment.unassigned_at = datetime.utcnow()
        self._log_activity(session_row, "unassigned", actor_officer_id,
                            detail=f"Officer {officer_id} unassigned")
        self.session.commit()
        return True

    def get_session_activity(self, session_id: int) -> list[SessionActivity]:
        return (
            self.session.query(SessionActivity)
            .filter_by(session_id=session_id)
            .order_by(SessionActivity.created_at)
            .all()
        )

    # -- Stage C3 (Voice) read helpers ---------------------------------
    #
    # Small, real lookups the voice command router needs — kept here
    # rather than in the router module per this file's own rule that
    # DatabaseService is the only class allowed to know SQL.

    def find_officer_by_name(self, name_fragment: str) -> Officer | None:
        """Case-insensitive substring match against Officer.name — e.g.
        "Inspector Ravi" -> matches an Officer named "Insp. Ravi Kumar".
        Returns the first match; ambiguity (two officers named Ravi) is
        not disambiguated here, same honesty note as Stage C2's pronoun
        resolution."""
        return (
            self.session.query(Officer)
            .filter(Officer.name.ilike(f"%{name_fragment}%"))
            .first()
        )

    def find_vehicles_by_fir(self, fir_id: int):
        from backend.database.models import Vehicle
        return self.session.query(Vehicle).filter_by(used_in_fir_id=fir_id).all()
