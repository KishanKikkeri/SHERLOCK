"""
SHERLOCK — Stage E4: Data Protection.

Field-level masking of sensitive values (phone numbers, bank account
numbers, precise location coordinates) — never a change to the stored
database value itself, per the brief's "Implement field-level
serializers instead of changing database values." Every function here
takes a raw value and a `Visibility` level and returns a *display*
value; nothing here ever writes to the DB.

Visibility is derived from the caller's role (see `visibility_for`),
not decided ad hoc per route: this is the same "declarative, not
scattered" principle Sprint E2 applied to permissions and Sprint E3
applied to audit writes.

No `national_id`-equivalent field exists anywhere in SHERLOCK's current
AER schema (checked: Person, Victim, Witness, Accused, Organization all
lack one) and none is added here — adding a new PII column purely to
have something to mask would be schema growth outside this sprint's
"wrap, don't rewrite" mandate. `mask_national_id` is still provided,
ready for the day such a field exists, and is unit-tested on its own.
"""

import enum


class Visibility(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"
    MASKED = "masked"


# Role -> visibility tier for sensitive PII fields specifically. Deliberately
# separate from Sprint E2's ROLE_PERMISSIONS map: "can you view this case
# at all" (view_case) and "how much of this specific phone number do you
# get to see" are different questions, and collapsing them would force
# every future PII-visibility decision through the coarser RBAC vocabulary.
_FULL_VISIBILITY_ROLES = {"administrator", "supervisor", "investigator"}
_PARTIAL_VISIBILITY_ROLES = {"analyst"}
# Everything else (policy_maker, read_only, and any unrecognized role) -> MASKED.


def visibility_for(ctx) -> Visibility:
    """`ctx` is a backend.security.dependencies.AuthContext. When auth is
    disabled (`ctx.is_system`), visibility is FULL — same "everything
    works exactly like today" guarantee as every other Stage E feature."""
    if getattr(ctx, "is_system", False):
        return Visibility.FULL
    roles = set(getattr(ctx, "roles", []) or [])
    if roles & _FULL_VISIBILITY_ROLES:
        return Visibility.FULL
    if roles & _PARTIAL_VISIBILITY_ROLES:
        return Visibility.PARTIAL
    return Visibility.MASKED


def _mask_middle(value: str, keep_start: int, keep_end: int, fill: str = "*") -> str:
    if value is None:
        return value
    value = str(value)
    if len(value) <= keep_start + keep_end:
        return fill * len(value)
    return value[:keep_start] + fill * (len(value) - keep_start - keep_end) + value[-keep_end:]


def mask_phone_number(value: str | None, visibility: Visibility) -> str | None:
    if value is None:
        return None
    if visibility == Visibility.FULL:
        return value
    if visibility == Visibility.PARTIAL:
        return _mask_middle(value, keep_start=2, keep_end=2)
    return "*" * len(str(value))


def mask_account_number(value: str | None, visibility: Visibility) -> str | None:
    if value is None:
        return None
    if visibility == Visibility.FULL:
        return value
    if visibility == Visibility.PARTIAL:
        return _mask_middle(value, keep_start=0, keep_end=4)
    return "*" * len(str(value))


def mask_national_id(value: str | None, visibility: Visibility) -> str | None:
    """See module docstring — no field to attach this to exists yet in
    the current schema; provided for forward compatibility."""
    if value is None:
        return None
    if visibility == Visibility.FULL:
        return value
    if visibility == Visibility.PARTIAL:
        return _mask_middle(value, keep_start=0, keep_end=4)
    return "*" * len(str(value))


def mask_coordinate(value: float | None, visibility: Visibility) -> float | None:
    """Precise lat/lng is the closest equivalent to a street address in
    the current Location schema (name/district/state/lat/lng — see
    backend/database/models/location.py). FULL keeps full precision;
    PARTIAL rounds to ~11km precision (1 decimal place), which still
    supports district-level geographic reasoning without pinpointing a
    residence; MASKED withholds the coordinate entirely."""
    if value is None:
        return None
    if visibility == Visibility.FULL:
        return value
    if visibility == Visibility.PARTIAL:
        return round(value, 1)
    return None


def mask_graph_node_data(node_type: str, data: dict, visibility: Visibility) -> dict:
    """Applies the appropriate mask(s) to a single graph node's `data`
    dict (as returned by GET /graph/{person_id}), based on which
    sensitive keys are actually present — never mutates the input."""
    if visibility == Visibility.FULL:
        return data

    masked = dict(data)
    if "number" in masked and node_type == "Phone":
        masked["number"] = mask_phone_number(masked["number"], visibility)
    if "account_number" in masked and node_type == "BankAccount":
        masked["account_number"] = mask_account_number(masked["account_number"], visibility)
    if node_type == "Location":
        if "latitude" in masked:
            masked["latitude"] = mask_coordinate(masked["latitude"], visibility)
        if "longitude" in masked:
            masked["longitude"] = mask_coordinate(masked["longitude"], visibility)
    return masked
