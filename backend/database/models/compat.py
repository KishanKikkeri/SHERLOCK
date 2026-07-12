"""
SHERLOCK — Stage A, Phase A7: Compatibility layer.

This is the single most important file for the "no agent changes" Golden
Rule. It is NOT part of the Karnataka Police AER — the AER expresses a
person's role in a case via three separate tables (Accused, Victim,
Witness; see accused.py/victim.py/witness.py), not a generic role column.

But four places in the existing codebase import and query the legacy
`PersonCrimeLink` model directly with the old (person_id, crime_id, role,
raw_name_used) shape:

    - backend/agents/crime_records/agent.py
    - backend/agents/entity_resolution/agent.py
    - backend/graph/builder_neo4j.py, builder_networkx.py
    - backend/datasets/generate_synthetic_data.py, inspect_data.py

Per the handover's Golden Rule ("every existing agent should continue
calling the same high-level APIs... the interface does NOT change") and
Phase A7 ("Everything below should continue working... internal
implementation changes, public API remains stable"), rewriting those four
call sites was explicitly out of scope for Stage A. So instead:

`person_crime_links` stays a real physical table with its old shape, but
it is now a *derived* projection, auto-populated by SQLAlchemy `after_insert`
events on Accused/Victim/Witness (see the bottom of each of those files).
Nothing should ever INSERT into PersonCrimeLink directly — it has no
loader of its own (Phase A3 loaders write Accused/Victim/Witness; this
table fills itself in as a side effect).

`crime_id` is resolved from `fir.crime_id` at sync time, since the AER
tables key off `fir_id`, not `crime_id` directly (see accused.py's
docstring for why: a person is accused *in a FIR*, and a FIR maps 1:1 to
a Crime).

`PersonAlias` is unchanged from the legacy schema — it was already
SQL-only, not part of the graph, and not touched by the AER (see
docs/DATABASE_ANALYSIS/02_TABLE_CATALOG.md).
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, select, table, column
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import PersonRole


class PersonAlias(Base):
    __tablename__ = "person_aliases"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    alias_name = Column(String, nullable=False)

    person = relationship("Person", back_populates="aliases")

    def __repr__(self):
        return f"<PersonAlias {self.alias_name} -> person {self.person_id}>"


class PersonCrimeLink(Base):
    """COMPATIBILITY TABLE — see module docstring. Auto-populated only;
    never written to directly."""

    __tablename__ = "person_crime_links"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    crime_id = Column(Integer, ForeignKey("crimes.id"), nullable=False, index=True)
    role = Column(Enum(PersonRole), nullable=False)
    raw_name_used = Column(String, nullable=False)

    # Traceability back to the real AER row this was derived from —
    # not used by any existing agent, purely for auditability.
    source_table = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)

    person = relationship("Person", back_populates="crime_links")
    crime = relationship("Crime", back_populates="person_links")

    def __repr__(self):
        return f"<PersonCrimeLink person={self.person_id} crime={self.crime_id} role={self.role}>"


# A lightweight Core (non-ORM) handle on the `firs` table, used only to
# resolve fir_id -> crime_id inside the event listener below, where we
# have a raw Connection, not a Session.
_firs_core = table("firs", column("id"), column("crime_id"))
_link_core = table(
    "person_crime_links",
    column("person_id"), column("crime_id"),
    column("role", Enum(PersonRole)),  # explicit type so Core serializes
    column("raw_name_used"), column("source_table"), column("source_id"),  # identically to the ORM column above
)


def sync_person_crime_link(connection, target, role: PersonRole, source_table: str):
    """Called from the `after_insert` event on Accused/Victim/Witness.

    `target` is the newly-inserted Accused/Victim/Witness ORM instance —
    duck-typed here (all three share person_id, fir_id, raw_name_used, id).
    """
    crime_id = connection.execute(
        select(_firs_core.c.crime_id).where(_firs_core.c.id == target.fir_id)
    ).scalar_one()

    connection.execute(
        _link_core.insert().values(
            person_id=target.person_id,
            crime_id=crime_id,
            role=role,
            raw_name_used=target.raw_name_used,
            source_table=source_table,
            source_id=target.id,
        )
    )
