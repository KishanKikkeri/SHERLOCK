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

from backend.database.models import (
    Person, Location, Crime, FIR, Accused, Victim, Witness, Officer,
    BankAccount, Transaction, Vehicle, Phone, Property, PersonCrimeLink,
    PersonRole,
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
