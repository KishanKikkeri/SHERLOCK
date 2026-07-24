"""
SHERLOCK — Stage G1: modus operandi profiling.

Two genuinely different kinds of signal here, kept honestly separate:

  1. Structured MO — weapon usage, vehicle usage, financial method —
     read directly off real foreign keys (Weapon.used_in_fir_id,
     Vehicle.used_in_fir_id, Transaction/BankAccount). No inference.

  2. Free-text MO — `Crime.modus_operandi` / `Crime.description` are
     free-text fields with no fixed vocabulary. The brief asks for
     "entry method / escape method / free-text MO clustering"; this repo
     has no NLP/ML dependency installed (see backend/requirements.txt)
     and its own stated policy is "no LLM-generated" output here, so
     rather than either fabricating categories or reaching for a new
     heavy dependency, this does deterministic keyword-bucket matching
     against a small, stated vocabulary (`_KEYWORD_BUCKETS` below) plus
     a plain word-frequency count. That is real signal extraction, but
     it is keyword matching, not semantic clustering — labeled as such
     in the output rather than oversold as NLP.
"""

from __future__ import annotations

import re
from collections import Counter

from backend.database.models import Transaction, Vehicle, Weapon

# Small, stated vocabulary — not exhaustive, not learned. Add terms here
# as the dataset's actual MO text vocabulary is reviewed; see
# backend/datasets/generate_synthetic_data.py for what it currently
# generates into Crime.modus_operandi/description.
_KEYWORD_BUCKETS: dict[str, list[str]] = {
    "entry_method": ["window", "lock breaking", "break-in", "forced entry", "servant-assisted", "door"],
    "escape_method": ["vehicle theft", "courier", "on foot", "fled", "motorcycle", "car"],
    "timing": ["night-time", "night", "day", "early morning", "dawn"],
    "communication": ["phishing", "otp", "sim swap", "online shopping", "phone", "call", "sms", "email"],
    "financial_deception": ["fake investment", "loan fraud", "identity theft", "document forgery"],
    "target_approach": ["chain snatching", "pickpocketing", "shop lifting", "domestic dispute", "armed assault"],
}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "was", "were",
    "with", "by", "for", "from", "his", "her", "their", "is", "are", "it", "as",
}


def compute_modus_operandi(session, person_id: int, history: dict) -> dict:
    firs = history["_firs"]
    fir_ids = [f.id for f in firs]
    crimes = history["_crimes"]

    weapons = session.query(Weapon).filter(Weapon.used_in_fir_id.in_(fir_ids)).all() if fir_ids else []
    vehicles = session.query(Vehicle).filter(Vehicle.used_in_fir_id.in_(fir_ids)).all() if fir_ids else []

    financial_method = _financial_method(session, person_id)
    text_signals = _text_signals(crimes)
    location_preference = _location_preference(crimes)

    return {
        "weapon_usage": sorted({w.weapon_type.value for w in weapons}),
        "vehicle_usage": sorted({v.vehicle_type for v in vehicles}),
        "financial_method": financial_method,
        "crime_sequence": [c.type.value for c in sorted(crimes, key=lambda c: c.timestamp)],
        "location_preference": location_preference,
        **text_signals,
        "because": (
            f"Derived from {len(weapons)} weapon record(s), {len(vehicles)} vehicle-use record(s), "
            f"and free-text MO/description on {len(crimes)} offence(s)."
        ),
    }


def _financial_method(session, person_id: int) -> str | None:
    from backend.database.models import BankAccount

    account_ids = [a.id for a in session.query(BankAccount).filter_by(owner_id=person_id).all()]
    if not account_ids:
        return None
    suspicious = (
        session.query(Transaction)
        .filter(
            Transaction.is_suspicious.is_(True),
            (Transaction.sender_account_id.in_(account_ids)) | (Transaction.receiver_account_id.in_(account_ids)),
        )
        .count()
    )
    if suspicious > 0:
        return f"bank_transfer (suspicious transaction(s) on record: {suspicious})"
    if account_ids:
        return "bank_transfer"
    return None


def _text_signals(crimes) -> dict:
    combined_text = " ".join(
        (c.modus_operandi or "") + " " + (c.description or "") for c in crimes
    ).lower()

    bucket_matches: dict[str, list[str]] = {}
    for bucket, keywords in _KEYWORD_BUCKETS.items():
        matched = sorted({kw for kw in keywords if kw in combined_text})
        if matched:
            bucket_matches[bucket] = matched

    words = re.findall(r"[a-z]{3,}", combined_text)
    word_freq = Counter(w for w in words if w not in _STOPWORDS)
    repeat_keywords = [w for w, count in word_freq.most_common(8) if count >= 1]

    return {
        "mo_keyword_buckets": bucket_matches,
        "mo_repeat_keywords": repeat_keywords,
        "mo_clustering_method": "deterministic keyword matching over Crime.modus_operandi/description "
                                 "text — not semantic/ML clustering (see module docstring).",
    }


def _location_preference(crimes) -> dict | None:
    districts = Counter(c.location.district for c in crimes if c.location)
    if not districts:
        return None
    top_district, count = districts.most_common(1)[0]
    return {"most_common_district": top_district, "occurrences": count, "district_spread": dict(districts)}
