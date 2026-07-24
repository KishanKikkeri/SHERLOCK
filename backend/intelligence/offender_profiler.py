"""
SHERLOCK — Stage G1: build_offender_profile().

The one entry point `backend/api/offender_profile.py` calls. Assembles
criminal_history / behavior_profiler / modus_profiler / network_profile /
risk_engine / investigation_priority / profile_summary into the exact
shape Requirement 5 specifies:

    identity, aliases, criminal_history, behavior_profile,
    modus_operandi, risk_profile, network_profile, recommendations

`graph_service` is accepted as a parameter (not constructed here) so a
caller that already built one for a request (e.g. an existing
investigation session) can pass it in and avoid rebuilding the in-memory
NetworkX graph twice — `backend/api/offender_profile.py` builds one per
request when the caller doesn't supply one.
"""

from __future__ import annotations

from backend.database.models import Person, PersonAlias
from backend.intelligence import behavior_profiler, criminal_history, investigation_priority
from backend.intelligence import modus_profiler, network_profile, profile_summary, risk_engine


class PersonNotFoundError(Exception):
    pass


def build_offender_profile(session, person_id: int, graph_service=None) -> dict:
    person = session.get(Person, person_id)
    if person is None:
        raise PersonNotFoundError(f"No person with id={person_id}")

    if graph_service is None:
        from backend.graph.service import get_graph_service
        graph_service = get_graph_service(backend="networkx", session=session)

    history = criminal_history.compute_criminal_history(session, person_id)
    behavior = behavior_profiler.compute_behavior_profile(session, person_id, history)
    modus = modus_profiler.compute_modus_operandi(session, person_id, history)
    network = network_profile.compute_network_profile(session, person_id, graph_service)
    risk = risk_engine.compute_risk_profile(history, behavior, network)
    priority = investigation_priority.classify_priority(history, risk, network)
    recommendations = profile_summary.generate_recommendations(history, behavior, modus, network, risk, priority)

    aliases = [a.alias_name for a in session.query(PersonAlias).filter_by(person_id=person_id).all()]

    # Strip the private "_firs"/"_crimes"/"_accused_records" ORM-object
    # carriers other modules used internally — they're SQLAlchemy rows,
    # not JSON-serializable, and were only ever meant to be passed
    # between these functions in-process.
    public_history = {k: v for k, v in history.items() if not k.startswith("_")}

    return {
        "identity": {
            "person_id": person.id,
            "name": person.name,
            "gender": person.gender.value,
            "age": person.age,
            "occupation": person.occupation,
            "home_location": (
                {"district": person.home_location.district, "state": person.home_location.state}
                if person.home_location else None
            ),
        },
        "aliases": aliases,
        "criminal_history": public_history,
        "behavior_profile": behavior,
        "modus_operandi": modus,
        "risk_profile": risk,
        "investigation_priority": priority,
        "network_profile": network,
        "recommendations": recommendations,
    }
