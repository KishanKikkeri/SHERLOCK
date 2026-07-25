"""
SHERLOCK — Unified Graph Search (Priority 18-23).

Single entry point (`search_entities`) that lets an investigator type any
natural identifier — a name, alias, vehicle number, phone, bank account,
FIR number, crime number, weapon serial, org/gang name, address, location,
district, state, or crime type — and get back ranked candidate nodes,
without ever having to know or choose an internal entity type.

Design
------
Rather than force a single upfront "what kind of thing is this" decision
(which fails the moment an investigator's input is ambiguous — "Ramesh K"
could be a name fragment, and a poorly-OCR'd plate could look like a
word), every relevant table is searched on every query. Cheap,
regex-shaped identifiers (vehicle plates, phone numbers, FIR/crime
numbers, bank accounts) get a normalized-exact-match pass that scores
1.0 and reliably wins the ranking when the input actually looks like
that identifier — which is what gives the *appearance* of automatic
entity-type detection (Priority 19) without a brittle single-branch
classifier. Free-text input (names, orgs, locations) falls through to
substring + difflib fuzzy scoring across every text field.

Kept intentionally dependency-light (stdlib `difflib`, `re`) to match
the rest of this codebase's design (see entity_resolution/agent.py).
"""

import re
from difflib import SequenceMatcher

from backend.database.models import (
    Person, PersonAlias, Vehicle, Phone, BankAccount, Weapon, FIR, Crime,
    Organization, Location, PersonCrimeLink, PersonAssociation,
)
from backend.database.models.enums import CrimeType
from backend.graph.schema import node_key

FUZZY_MIN_SCORE = 0.45  # below this, a fuzzy candidate isn't worth surfacing at all
SUBSTRING_SCORE = 0.88  # query is a literal substring of the target (or vice versa)
EXACT_SCORE = 1.0

_ALNUM_RE = re.compile(r"[^a-z0-9]")
_VEHICLE_RE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{3,4}$")
_PHONE_RE = re.compile(r"^\d{10,13}$")
_FIR_RE = re.compile(r"^FIR[-\s]?\d{2,4}[-\s]?\d+$", re.IGNORECASE)
_DIGITS_RE = re.compile(r"^\d+$")


def _norm(s: str) -> str:
    """Lowercase and strip everything but letters/digits — makes 'KA 01 AB 1234',
    'ka01ab1234', and 'KA-01-AB-1234' compare equal, same for phone/account numbers
    typed with spaces or dashes."""
    return _ALNUM_RE.sub("", (s or "").lower())


def _text_score(query_norm: str, target: str) -> float:
    """Fuzzy score for free-text fields (names, addresses, org names).
    Preserves spaces (unlike _norm) since word order/spacing matters less
    than substring containment for this kind of matching."""
    target_norm = (target or "").strip().lower()
    q = query_norm
    if not target_norm or not q:
        return 0.0
    if q == target_norm:
        return EXACT_SCORE
    if q in target_norm or target_norm in q:
        # Reward closer length ratios so "Ramesh" scores higher against
        # "Ramesh Kumar" than a one-letter query would.
        ratio = len(q) / max(len(target_norm), len(q))
        return round(SUBSTRING_SCORE + 0.09 * ratio, 3)
    whole = SequenceMatcher(None, q, target_norm).ratio()
    # A typo'd single-word query ("Rmesh") gets buried by SequenceMatcher
    # against a full "ramesh kumar" (only ~half the target matches at
    # all) — compare against each word of the target too and keep the best.
    best_word = max(
        (SequenceMatcher(None, q, word).ratio() for word in target_norm.split() if word),
        default=0.0,
    )
    best = max(whole, best_word)
    # Below this, SequenceMatcher on short strings starts calling
    # genuinely different words "similar enough" ('Ramesh' vs 'Suresh'
    # scores ~0.67) — real single/double-character typos ('Rmesh',
    # 'Rames') consistently score well above this, so the floor filters
    # noise without losing the brief's own typo examples.
    return round(best, 3) if best >= 0.72 else 0.0


def _identifier_score(query_norm: str, target: str) -> float:
    """Fuzzy score for normalized identifiers (plates, phones, accounts,
    serials) — compares on the alnum-stripped form so formatting never
    matters, but does not reward substrings the way free text does,
    since 'KA01AB1234' partially matching a wrong plate is a false lead,
    not a helpful fuzzy hit."""
    target_norm = _norm(target)
    if not target_norm or not query_norm:
        return 0.0
    if query_norm == target_norm:
        return EXACT_SCORE
    if len(query_norm) >= 4 and (query_norm in target_norm or target_norm in query_norm):
        ratio = len(query_norm) / max(len(target_norm), len(query_norm))
        return round(SUBSTRING_SCORE - 0.15 + 0.15 * ratio, 3)  # partial plate/phone/account, below a full substring name hit
    ratio = SequenceMatcher(None, query_norm, target_norm).ratio()
    # A wrong-but-similar-length plate/phone/account is a dangerous false
    # lead, more so than a wrong name — keep the floor stricter here.
    return round(ratio, 3) if ratio >= 0.78 else 0.0


def _candidate(type_, label, id_, score, **extra):
    return {
        "type": type_,
        "label": label,
        "id": id_,
        "node_key": node_key(type_, id_),
        "score": min(score, 1.0),
        **({"meta": extra} if extra else {}),
    }


# ---------------------------------------------------------------------------
# Per-entity-type search
# ---------------------------------------------------------------------------

def _search_persons(session, q, q_norm, case_person_ids):
    # Full-scan + Python fuzzy scoring rather than SQL ILIKE alone: a
    # transposition typo ("Rmesh") isn't a literal substring of "Ramesh",
    # so ILIKE would silently drop it even though it should fuzzy-match
    # (Priority 22's own example list requires this).
    ql = q.lower()
    rows = session.query(Person).limit(_IDENTIFIER_SCAN_LIMIT).all()
    seen = {}
    out = []
    for p in rows:
        score = _text_score(ql, p.name)
        if score >= FUZZY_MIN_SCORE:
            seen[p.id] = score
            out.append(_candidate("Person", p.name, p.id, score))

    # Aliases — PersonAlias.alias_name
    alias_rows = session.query(PersonAlias).limit(_IDENTIFIER_SCAN_LIMIT).all()
    for a in alias_rows:
        score = _text_score(ql, a.alias_name)
        if score < FUZZY_MIN_SCORE:
            continue
        if a.person_id in seen and seen[a.person_id] >= score:
            continue
        person = a.person
        if not person:
            continue
        seen[a.person_id] = score
        out.append(_candidate("Person", person.name, person.id, score, matched_alias=a.alias_name))

    if case_person_ids:
        for c in out:
            if c["id"] in case_person_ids:
                c["score"] = min(c["score"] + 0.08, 1.0)
                c.setdefault("meta", {})["case_context_boost"] = True

    return out


# Cap on rows pulled per identifier table before Python-side normalized
# matching. SQL ILIKE can't match 'ka 01 ab 1234' against a stored
# 'KA01AB1234' — the space breaks substring matching — so identifiers are
# compared post-normalization in Python instead of in the query itself.
# A regional force's vehicle/phone/account/weapon/FIR tables are not
# expected to run past the tens of thousands of rows this cap covers; if
# that stops being true, replace with a normalized generated column + index.
_IDENTIFIER_SCAN_LIMIT = 20000


def _search_identifier_table(session, model, field, q_norm, type_label, label_fn):
    if not q_norm:
        return []
    rows = session.query(model).filter(field.isnot(None)).limit(_IDENTIFIER_SCAN_LIMIT).all()
    out = []
    for row in rows:
        value = getattr(row, field.key)
        score = _identifier_score(q_norm, value)
        if score >= FUZZY_MIN_SCORE:
            out.append(_candidate(type_label, label_fn(row), row.id, score))
    return out


def _search_vehicles(session, q, q_norm):
    return _search_identifier_table(
        session, Vehicle, Vehicle.registration_number, q_norm, "Vehicle",
        lambda v: v.registration_number,
    )


def _search_phones(session, q, q_norm):
    return _search_identifier_table(
        session, Phone, Phone.number, q_norm, "Phone",
        lambda p: p.number,
    )


def _search_bank_accounts(session, q, q_norm):
    return _search_identifier_table(
        session, BankAccount, BankAccount.account_number, q_norm, "BankAccount",
        lambda a: f"{a.account_number} ({a.bank})",
    )


def _search_weapons(session, q, q_norm):
    return _search_identifier_table(
        session, Weapon, Weapon.serial_number, q_norm, "Weapon",
        lambda w: w.serial_number or f"Weapon #{w.id}",
    )


def _search_firs(session, q, q_norm):
    return _search_identifier_table(
        session, FIR, FIR.fir_number, q_norm, "FIR",
        lambda f: f.fir_number,
    )


def _search_crimes(session, q, q_norm):
    """Bare crime/case numbers (e.g. 'Case 42', or a plain integer) resolve
    to the Crime row directly."""
    m = _DIGITS_RE.match(q.strip())
    if not m:
        return []
    crime_id = int(m.group(0))
    crime = session.query(Crime).filter(Crime.id == crime_id).first()
    if not crime:
        return []
    label = f"Crime #{crime.id} ({crime.type.value if hasattr(crime.type, 'value') else crime.type})"
    return [_candidate("Crime", label, crime.id, 0.6)]  # bare numbers are a weak, low-confidence signal


def _search_organizations(session, q, q_norm):
    ql = q.lower()
    rows = session.query(Organization).limit(_IDENTIFIER_SCAN_LIMIT).all()
    out = []
    for o in rows:
        score = max(_text_score(ql, o.name), _identifier_score(q_norm, o.registration_number or ""))
        if score >= FUZZY_MIN_SCORE:
            out.append(_candidate("Organization", o.name, o.id, score))
    return out


def _search_locations(session, q, q_norm):
    ql = q.lower()
    rows = session.query(Location).limit(_IDENTIFIER_SCAN_LIMIT).all()
    out = []
    for loc in rows:
        score = max(
            _text_score(ql, loc.name),
            _text_score(ql, loc.district),
            _text_score(ql, loc.state),
        )
        if score >= FUZZY_MIN_SCORE:
            out.append(_candidate("Location", f"{loc.name}, {loc.district}", loc.id, score))
    return out


def _search_crime_types(session, q, q_norm):
    """'Cyber Fraud' / 'burglary' / 'drug trafficking' -> matching Crime rows,
    grouped as a single pseudo-candidate per crime type with a count, since
    a crime type isn't itself a graph node — it's a filter over Crime nodes.
    Surfaced here mainly so the type is recognized and the investigator gets
    *something* back rather than zero results; selecting it is handled by
    the frontend as "filter graph to this crime type" rather than a center."""
    out = []
    ql = q.lower().strip()
    for ct in CrimeType:
        label = ct.value.replace("_", " ")
        score = _text_score(ql, label)
        if score >= FUZZY_MIN_SCORE:
            count = session.query(Crime).filter(Crime.type == ct).count()
            if count:
                out.append(_candidate(
                    "CrimeType", f"{label.title()} ({count} case{'s' if count != 1 else ''})",
                    ct.value, score, crime_type=ct.value,
                ))
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _pattern_hint(q: str):
    """Fast path: if the raw query unambiguously *looks like* one identifier
    shape, note it so we can boost that type's exact matches even higher —
    this is what makes 'KA01AB1234' outrank a coincidental fuzzy name hit."""
    stripped = q.strip().upper().replace(" ", "").replace("-", "")
    if _VEHICLE_RE.match(stripped):
        return "Vehicle"
    if _PHONE_RE.match(stripped):
        return "Phone"
    if _FIR_RE.match(q.strip()):
        return "FIR"
    return None


def search_entities(session, query: str, case_id: int | None = None, limit: int = 20):
    """Search every indexed identifier type for `query` and return ranked
    candidates. `case_id` (an Investigation/Crime id, when the investigator
    has a case open) boosts persons already connected to that case, per
    Priority 23.
    """
    q = (query or "").strip()
    if not q:
        return []
    q_norm = _norm(q)

    case_person_ids = None
    if case_id is not None:
        case_person_ids = {
            r.person_id for r in
            session.query(PersonCrimeLink.person_id).filter(PersonCrimeLink.crime_id == case_id).all()
        }

    candidates = []
    candidates += _search_persons(session, q, q_norm, case_person_ids)
    candidates += _search_vehicles(session, q, q_norm)
    candidates += _search_phones(session, q, q_norm)
    candidates += _search_bank_accounts(session, q, q_norm)
    candidates += _search_weapons(session, q, q_norm)
    candidates += _search_firs(session, q, q_norm)
    candidates += _search_crimes(session, q, q_norm)
    candidates += _search_organizations(session, q, q_norm)
    candidates += _search_locations(session, q, q_norm)
    candidates += _search_crime_types(session, q, q_norm)

    hint = _pattern_hint(q)
    if hint:
        for c in candidates:
            if c["type"] == hint and c["score"] >= SUBSTRING_SCORE:
                c["score"] = EXACT_SCORE

    # Frequently-connected tiebreak (Priority 23): among near-tied Person
    # candidates, prefer the one with more associations/case links — cheap
    # single-purpose count, not a full graph-degree computation.
    person_ids = [c["id"] for c in candidates if c["type"] == "Person"]
    connection_counts = {}
    if person_ids:
        assoc_rows = session.query(PersonAssociation.person_a_id).filter(
            PersonAssociation.person_a_id.in_(person_ids)
        ).all()
        for (pid,) in assoc_rows:
            connection_counts[pid] = connection_counts.get(pid, 0) + 1
        link_rows = session.query(PersonCrimeLink.person_id).filter(
            PersonCrimeLink.person_id.in_(person_ids)
        ).all()
        for (pid,) in link_rows:
            connection_counts[pid] = connection_counts.get(pid, 0) + 1
    for c in candidates:
        if c["type"] == "Person":
            c["meta"] = {**c.get("meta", {}), "connections": connection_counts.get(c["id"], 0)}

    candidates = [c for c in candidates if c["score"] >= FUZZY_MIN_SCORE]

    def sort_key(c):
        connections = c.get("meta", {}).get("connections", 0) if c["type"] == "Person" else 0
        return (-c["score"], -connections, c["type"], c["label"])

    candidates.sort(key=sort_key)

    # Dedupe exact (type, id) repeats (e.g. a person matched by both name and alias)
    dedup = {}
    for c in candidates:
        key = (c["type"], c["id"])
        if key not in dedup or c["score"] > dedup[key]["score"]:
            dedup[key] = c

    return list(dedup.values())[:limit]
