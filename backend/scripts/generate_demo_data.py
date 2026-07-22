"""
SHERLOCK — Full-platform demo data generator.

Builds on `backend.datasets.generate_synthetic_data` (the existing Stage A/B
Karnataka AER core: locations, persons + aliases, phones/vehicles/bank
accounts, officers, crimes + FIRs + accused/victim/witness, person
associations, the money-mule fraud ring) rather than duplicating it, and
adds every entity/workflow introduced in the later stages so a live demo
has real, queryable data behind every screen and every API route:

    Stage A extras — Court, Organization (+ GANG orgs = criminal networks),
                      OrganizationMembership, Weapon, Property, Investigation,
                      Arrest, ChargeSheet, CallRecord (bulk CDRs), bulk
                      Transactions (fan-in / layering chains / smurfing /
                      round-tripping cycles, on top of the existing fraud ring)
    Stage C1/C2    — InvestigationSession, SessionAssignment, SessionActivity,
                      ConversationTurn (AgentFinding-shaped findings_json,
                      entity_mentions_json)
    Stage C4       — DiscussionRecord (AgentOpinion / Disagreement / Consensus)
    Stage C6       — BoardObject, Comment, Notification, ReviewRequest,
                      SessionPresence
    Stage E1       — User, Role, UserRole — one demo login per SystemRole
    Stage E3       — AuditLog (bulk, realistic action/success mix)

USAGE
-----
    python -m backend.scripts.generate_demo_data --medium --reset
    python -m backend.scripts.generate_demo_data --large --reset
    python -m backend.scripts.generate_demo_data --small --reset --seed 7

Flags: --small / --medium / --large (size presets, --medium is default),
--persons / --crimes (override the preset's core counts), --reset (drop +
recreate all tables first), --seed (default 42), --deterministic (re-run
the RNG-derived checksum used to prove reproducibility and print it,
instead of only asserting it silently).

Every generation step below re-seeds nothing itself — `random.seed()` and
`Faker.seed()` are set once in `main()`, and every subsequent draw is a
pure function of that seed plus insertion order, so re-running with the
same --seed and the same size preset reproduces byte-identical rows (the
one intentional exception is `created_at`/`updated_at` columns that
SQLAlchemy defaults to `datetime.utcnow` at flush time on a few tables
that were never given an explicit value here — every timestamp this
script assigns explicitly is deterministic; see the "REPRODUCIBILITY"
note further down for the two columns that aren't and why that's fine).

SCHEMA CONSTRAINTS THIS SCRIPT DELIBERATELY WORKS WITHIN (not modified,
per the "do not modify application logic" instruction this was built
under):

  * `CrimeType` (backend/database/models/enums.py) is a fixed 6-value
    enum — theft, burglary, fraud, cybercrime, assault, drug_trafficking
    — and its own docstring flags the Crime Head/Sub Head decomposition
    needed to add more as explicit future work, not Stage A. Categories
    the brief asked for that have no matching enum value — murder,
    kidnapping, human trafficking, extortion, organized crime, political
    corruption, domestic violence, missing persons, terror financing —
    are represented qualitatively instead, layered onto the 6 real
    types: via `modus_operandi`/`description` text, via GANG-typed
    Organizations for organized-crime networks, and via Weapon/Property
    records for illegal-arms and property-crime material. They are
    never invented as fake enum members the rest of the app (API
    validation, frontend dropdowns, graph builder) wouldn't recognize.
  * `Transaction` has no channel column (cash/UPI/bank/crypto), so those
    patterns are expressed structurally instead — fan-in, layering
    chains, smurfing, round-tripping cycles — via which accounts pay
    which other accounts, rather than a fabricated label column.
  * `CallRecord` has no tower/IMEI/IMSI/direction columns. Missed calls
    are represented by the convention `duration_seconds == 0`; there is
    no separate `direction` or `tower_id` field to populate.

After seeding, this script builds the real in-memory graph via
`backend.graph.builder_networkx.build_graph` (the actual application
code path, not a re-implementation) and reports the real node/edge
counts, then runs a set of integrity checks before printing the final
summary report.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict, Counter
from datetime import datetime, timedelta

from faker import Faker

from backend.database.config import Base, engine, SessionLocal
from backend.database.models import (
    Location, Person, PersonAlias, Crime, FIR, Officer, Accused, Victim, Witness,
    PersonCrimeLink, Vehicle, Phone, CallRecord, BankAccount, Transaction,
    PersonAssociation, Gender, CrimeType, FIRStatus, PersonRole, RelationType,
    OfficerRank, Court, CourtLevel, Organization, OrganizationType,
    OrganizationMembership, Weapon, WeaponType, Property, PropertyStatus,
    Investigation, Arrest, ArrestStatus, ChargeSheet, ChargeSheetStatus,
    InvestigationSession, SessionAssignment, SessionActivity,
    InvestigationSessionStatus, InvestigationPriority, ConversationTurn,
    DiscussionRecord, BoardObject, BoardObjectType, Comment, CommentTargetType,
    Notification, NotificationType, ReviewRequest, ReviewStatus, SessionPresence,
    PresenceStatus, User, Role, UserRole, AuditLog, AuditAction, SystemRole,
)
from backend.security.passwords import hash_password
from backend.security.seed import seed_roles

from backend.datasets.generate_synthetic_data import (
    fake, KARNATAKA_LOCATIONS, BANKS, REFERENCE_DATE,
    random_date_within,
    generate_locations, generate_persons, generate_assets, generate_officers,
    generate_crimes_and_firs, generate_associations, generate_fraud_ring,
)

# ---------------------------------------------------------------------------
# Scale presets
# ---------------------------------------------------------------------------

SCALE_PRESETS = {
    # persons / crimes are the two core counts everything else scales from.
    # n_orgs = (gangs, companies, ngos). n_officers separate from persons —
    # officers are police personnel, not part of the civilian person pool.
    "small": dict(
        persons=200, crimes=300, ring_size=6, officers=15,
        n_orgs=(4, 4, 2), n_calls=800, n_transactions=650,
        n_sessions=15, n_audit=1200,
    ),
    "medium": dict(
        persons=500, crimes=1000, ring_size=8, officers=25,
        n_orgs=(8, 8, 4), n_calls=3000, n_transactions=2500,
        n_sessions=60, n_audit=5000,
    ),
    "large": dict(
        persons=1200, crimes=1100, ring_size=10, officers=40,
        n_orgs=(14, 14, 6), n_calls=6300, n_transactions=5200,
        n_sessions=120, n_audit=10500, n_extra_associations=2700,
    ),
}
SCALE_PRESETS["small"]["n_extra_associations"] = 300
SCALE_PRESETS["medium"]["n_extra_associations"] = 1200

# Distinct reference window for "system usage" timestamps (audit log,
# session/collaboration activity) — independent of REFERENCE_DATE (which
# anchors *crime* timestamps in the underlying generator). Spans roughly
# the current financial year up to "now" so a live demo shows activity
# that looks recent, not frozen at one instant.
ACTIVITY_WINDOW_START = datetime(2026, 1, 1)
ACTIVITY_WINDOW_END = datetime(2026, 7, 22, 18, 0, 0)

AGENT_NAMES = [
    "CrimeRecords", "NetworkAnalysis", "PatternAnalysis", "FinancialAgent",
    "PreventionAgent", "EntityResolution", "TimelineReconstruction",
    "WitnessIntelligence", "OfficerIntelligence", "OrganizationIntelligence",
    "PropertyIntelligence", "WeaponIntelligence", "SociologicalIntelligence",
    "BehavioralIntelligence", "CaseIntelligence", "DecisionSupport",
    "Forecasting", "SimilarCase", "InvestigationAssignment",
]

GANG_NAMES = [
    "Bellary Steel Crew", "Coastal Kingpins", "Highway Vipers Syndicate",
    "Silk Road Financiers", "Tumkur Tiger Gang", "Black Cobra Outfit",
    "Border Runners Collective", "Diamond Circle Ring", "Red Sandalwood Cartel",
    "Northside Chain-Snatchers", "River Route Smugglers", "Iron Gate Mafia",
    "Grey Market Consortium", "Shadow Ledger Group",
]

COMPANY_NAMES = [
    "Vishwas Traders Pvt Ltd", "Om Sai Logistics Pvt Ltd", "Deccan Bullion Exports",
    "Karnataka Agro Ventures", "Silicon Gate Infotech", "Golden Harvest Warehousing",
    "Nandi Hills Constructions", "Cauvery Freight Carriers", "Bharat Shell Holdings",
    "Sapthagiri Finance Corp", "Malnad Timber & Trading", "Coastal Marine Exports",
    "Vega Digital Solutions", "Uttara Karnataka Realty",
]

NGO_NAMES = [
    "Karnataka Seva Samithi", "Asha Foundation Trust", "Manava Kalyana Sangha",
    "Deepa Welfare Society", "Grameena Abhivrudhi Trust", "Prakruti Seva Sanstha",
]

PROPERTY_CATALOG = [
    ("cash", (5000, 800000)),
    ("jewellery", (10000, 500000)),
    ("electronics", (2000, 150000)),
    ("documents / forged papers", (0, 0)),
    ("narcotics", (1000, 200000)),
    ("vehicle parts", (5000, 90000)),
    ("counterfeit currency", (5000, 300000)),
    ("land documents", (0, 0)),
]

WEAPON_DESCRIPTIONS = {
    WeaponType.FIREARM: ["country-made pistol", "9mm semi-automatic pistol", "double-barrel shotgun", "smuggled revolver"],
    WeaponType.BLADE: ["long knife", "machete", "sickle", "dagger"],
    WeaponType.BLUNT: ["iron rod", "wooden club", "hockey stick", "hammer"],
    WeaponType.EXPLOSIVE: ["crude country bomb", "seized gelatin sticks", "improvised explosive device"],
    WeaponType.OTHER: ["chain", "acid bottle", "pepper spray canister"],
}

VOICE_QUERY_TEMPLATES = [
    "Show me the FIR details for {fir}",
    "Who are the known associates of {person}?",
    "Any suspicious transactions linked to this case?",
    "Give me a timeline for this investigation",
    "List the accused persons in {fir}",
    "Is there a repeat offender pattern here?",
    "Summarize the network around {person}",
    "What weapons were recovered in this case?",
    "Generate a report for this session",
    "Check for related crimes in the same district",
]

SESSION_TITLE_TEMPLATES = [
    "Investigation into {fir}",
    "Network trace — {fir}",
    "Financial trail review — {fir}",
    "Case review: {fir}",
    "Follow-up investigation — {fir}",
]

BOARD_NOTE_TEMPLATES = [
    "Cross-check phone contacts against known associates.",
    "Verify bank account ownership before next hearing.",
    "Possible link to an existing gang membership — needs confirmation.",
    "Witness statement contradicts accused's alibi — flag for review.",
    "Recovered property matches description from an earlier FIR.",
    "Suggest surveillance on this location for the next 2 weeks.",
]

COMMENT_TEMPLATES = [
    "Can we get the call detail records for the last 30 days on this?",
    "Good catch — please attach the seizure memo here.",
    "@{mention} can you confirm the custody status on this?",
    "This matches the pattern from a related case last quarter.",
    "Requesting a second opinion before we escalate this.",
    "Updated the timeline based on the latest witness statement.",
    "Flagging this account for the Financial Intelligence Agent to re-check.",
    "@{mention} approved to proceed with the chargesheet filing.",
]

UNITS_STATIONS = ["MG Road PS", "Whitefield PS", "Jayanagar PS", "Mysuru City PS", "Hubballi PS", "Mangaluru City PS"]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_WORD_BANK = [
    "Falcon", "Tiger", "River", "Granite", "Lotus", "Ember", "Cobalt", "Harbor",
    "Nimbus", "Sable", "Cedar", "Vertex", "Quartz", "Delta", "Orbit", "Hawk",
]


def gen_password(rand: random.Random) -> str:
    """Deterministic (given a seeded Random), plausible-looking password —
    two words + digits + a symbol, always >= security.config.MIN_PASSWORD_LENGTH."""
    w1, w2 = rand.sample(_WORD_BANK, 2)
    digits = rand.randint(10, 99)
    symbol = rand.choice("!@#$%*")
    return f"{w1}{w2}{digits}{symbol}"


def chunked(iterable, size):
    buf = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


# ---------------------------------------------------------------------------
# Courts
# ---------------------------------------------------------------------------

def generate_courts(session):
    districts = sorted({d for _, d, _, _ in KARNATAKA_LOCATIONS})
    courts = []
    for district in districts:
        courts.append(Court(name=f"{district} Magistrate Court", level=CourtLevel.MAGISTRATE, district=district))
    for district in ["Bengaluru Urban", "Mysuru"]:
        courts.append(Court(name=f"{district} Sessions Court", level=CourtLevel.SESSIONS, district=district))
    courts.append(Court(name="Karnataka High Court", level=CourtLevel.HIGH_COURT, district="Bengaluru Urban"))
    session.add_all(courts)
    session.flush()
    return courts


# ---------------------------------------------------------------------------
# Organizations (companies / NGOs / criminal gangs) + memberships
# ---------------------------------------------------------------------------

def generate_organizations(session, persons, repeat_offender_pool, n_gangs, n_companies, n_ngos):
    orgs = []
    memberships = []

    gang_names = random.sample(GANG_NAMES, min(n_gangs, len(GANG_NAMES)))
    company_names = random.sample(COMPANY_NAMES, min(n_companies, len(COMPANY_NAMES)))
    ngo_names = random.sample(NGO_NAMES, min(n_ngos, len(NGO_NAMES)))

    gang_leaders = []  # hidden kingpins: leaders of gangs, tracked for extra association edges

    for name in gang_names:
        org = Organization(name=name, org_type=OrganizationType.GANG, address=fake.address())
        orgs.append(org)
        session.add(org)
        session.flush()

        # Leader biased toward the repeat-offender pool (a real criminal
        # footprint) but never guaranteed to be an Accused on the gang's
        # own crimes — that's what makes them a "hidden kingpin" rather
        # than just another accused.
        leader = random.choice(repeat_offender_pool)
        gang_leaders.append((leader, org))
        memberships.append(OrganizationMembership(person_id=leader.id, organization_id=org.id, role="leader",
                                                    joined_date=random_date_within(900)))

        member_count = random.randint(4, 9)
        gang_members = random.sample([p for p in persons if p.id != leader.id], member_count)
        for m in gang_members:
            role = random.choices(["lieutenant", "member", "financier"], weights=[0.2, 0.6, 0.2])[0]
            memberships.append(OrganizationMembership(person_id=m.id, organization_id=org.id, role=role,
                                                        joined_date=random_date_within(700)))

    for name in company_names:
        org = Organization(
            name=name, org_type=OrganizationType.COMPANY,
            registration_number=fake.bothify("KA-CIN-########"),
            address=fake.address(),
        )
        orgs.append(org)
        session.add(org)
        session.flush()
        for p in random.sample(persons, random.randint(2, 5)):
            role = random.choices(["director", "employee", "financier"], weights=[0.25, 0.6, 0.15])[0]
            memberships.append(OrganizationMembership(person_id=p.id, organization_id=org.id, role=role,
                                                        joined_date=random_date_within(1200)))

    for name in ngo_names:
        org = Organization(name=name, org_type=OrganizationType.NGO, address=fake.address())
        orgs.append(org)
        session.add(org)
        session.flush()
        for p in random.sample(persons, random.randint(2, 4)):
            memberships.append(OrganizationMembership(person_id=p.id, organization_id=org.id, role="member",
                                                        joined_date=random_date_within(1200)))

    session.add_all(memberships)
    session.flush()

    # Make one gang leader a bridge node: also a lieutenant in a second
    # gang, so the two criminal clusters are connected through one person.
    associations = []
    if len(gang_leaders) >= 2:
        bridge_leader, _ = gang_leaders[0]
        _, second_gang = gang_leaders[1]
        memberships.append(OrganizationMembership(person_id=bridge_leader.id, organization_id=second_gang.id,
                                                    role="lieutenant", joined_date=random_date_within(500)))
        session.add(memberships[-1])
        session.flush()

    # Explicit hub edges: gang leader <-> every member of their own gang,
    # via PersonAssociation, so the leader is a visible high-degree hub in
    # the network graph even though they may carry no Accused record.
    by_org = defaultdict(list)
    for m in memberships:
        by_org[m.organization_id].append(m.person_id)
    for leader, org in gang_leaders:
        for member_id in by_org[org.id]:
            if member_id == leader.id:
                continue
            associations.append(PersonAssociation(
                person_a_id=leader.id, person_b_id=member_id,
                relation_type=RelationType.ASSOCIATE, strength=round(random.uniform(0.6, 0.95), 2),
            ))
    session.add_all(associations)
    session.flush()

    return orgs, memberships, gang_leaders


# ---------------------------------------------------------------------------
# Relationship density — hubs, bridge nodes, dense clustering
# ---------------------------------------------------------------------------

# NOTE: the brief's relationship vocabulary (friend_of, financial_transfer,
# called, messaged, shared_vehicle, shared_phone, shared_bank, same_location,
# same_ip, same_device, same_employer, same_gang, same_property) has no
# matching column in `RelationType` (backend/database/models/enums.py),
# which is a fixed 5-value enum: FAMILY, ASSOCIATE, CO_ACCUSED, NEIGHBOR,
# BUSINESS_PARTNER. Per the same "don't invent enum members the app can't
# read" constraint documented at the top of this file, this generator
# reuses those 5 real values. The underlying *shapes* the brief actually
# cares about — shared bank accounts, shared vehicles, same-location
# clustering, phone contact graphs, financial transfers — are already
# real and queryable elsewhere: shared_bank/shared_vehicle show up as
# common `owner_id` in BankAccount/Vehicle, same_location as common
# `home_location_id` on Person, called/messaged as `CallRecord` edges,
# financial_transfer as `Transaction` edges, same_gang as
# `OrganizationMembership` rows against the same `organization_id`.
def generate_relationship_density(session, persons, hub_pool, n_extra):
    person_ids = [p.id for p in persons]
    hub_ids = [p.id for p in hub_pool] if hub_pool else person_ids[: max(5, len(person_ids) // 20)]
    relation_types = [RelationType.FAMILY, RelationType.ASSOCIATE, RelationType.NEIGHBOR, RelationType.BUSINESS_PARTNER]

    associations = []
    for _ in range(n_extra):
        if random.random() < 0.35 and hub_ids:
            # Hub edge: one side drawn from the hub pool, biasing degree
            # distribution so a handful of persons become visible
            # high-degree hubs rather than every edge being uniform-random.
            a = random.choice(hub_ids)
            b = random.choice([pid for pid in person_ids if pid != a])
        else:
            a, b = random.sample(person_ids, 2)
        associations.append(PersonAssociation(
            person_a_id=a, person_b_id=b,
            relation_type=random.choice(relation_types),
            strength=round(random.uniform(0.25, 0.9), 2),
        ))

    for chunk in chunked(associations, 1000):
        session.bulk_save_objects(chunk)
    session.flush()
    return associations


# ---------------------------------------------------------------------------
# Weapons, seized property, investigations, arrests, chargesheets
# ---------------------------------------------------------------------------

def generate_weapons_and_properties(session, fir_ids, fir_crime_info, accused_by_fir, officers, courts):
    weapons, properties = [], []

    for fir_id in fir_ids:
        crime_type, location_id = fir_crime_info[fir_id]
        accused_ids = accused_by_fir.get(fir_id, [])

        # Seized property on ~18% of FIRs (property crime / recovered evidence)
        if random.random() < 0.18:
            category, value_range = random.choice(PROPERTY_CATALOG)
            estimated_value = round(random.uniform(*value_range), 2) if value_range[1] > 0 else None
            properties.append(Property(
                fir_id=fir_id,
                description=f"{category.title()} recovered during investigation",
                category=category,
                estimated_value=estimated_value,
                status=random.choices(list(PropertyStatus), weights=[0.4, 0.3, 0.2, 0.1])[0],
                seized_location_id=location_id,
                recovered_from_person_id=random.choice(accused_ids) if accused_ids else None,
                custodian_officer_id=random.choice(officers).id,
                seized_date=random_date_within(600),
            ))

        # Weapons on assault / drug_trafficking FIRs, plus a sprinkling
        # elsewhere to represent the "illegal arms" category the fixed
        # CrimeType enum has no dedicated slot for.
        weapon_chance = 0.35 if crime_type in (CrimeType.ASSAULT, CrimeType.DRUG_TRAFFICKING) else 0.04
        if random.random() < weapon_chance:
            wtype = random.choice(list(WeaponType))
            weapons.append(Weapon(
                weapon_type=wtype,
                description=random.choice(WEAPON_DESCRIPTIONS[wtype]),
                serial_number=fake.bothify("WPN-########") if wtype == WeaponType.FIREARM else None,
                used_in_fir_id=fir_id,
                recovered_from_person_id=random.choice(accused_ids) if accused_ids else None,
                status=random.choices(list(PropertyStatus), weights=[0.5, 0.3, 0.15, 0.05])[0],
            ))

    session.add_all(properties + weapons)
    session.flush()
    return weapons, properties


def generate_investigations_arrests_chargesheets(session, fir_rows, officers, courts, accused_by_fir):
    investigations, arrests, chargesheets = [], [], []

    for fir_id, _fir_number, status, filed_date, investigating_officer_id in fir_rows:
        officer_id = investigating_officer_id or random.choice(officers).id
        is_closed = status in (FIRStatus.CLOSED, FIRStatus.CONVICTED, FIRStatus.CHARGESHEET_FILED)
        start = filed_date + timedelta(days=random.randint(0, 3))
        end = start + timedelta(days=random.randint(10, 200)) if is_closed else None
        investigations.append(Investigation(
            fir_id=fir_id, officer_id=officer_id, start_date=start, end_date=end,
            status="closed" if is_closed else "ongoing",
            notes=f"Investigation notes: {fake.sentence(nb_words=10)}",
        ))

        accused_ids = accused_by_fir.get(fir_id, [])
        if status in (FIRStatus.CHARGESHEET_FILED, FIRStatus.CLOSED, FIRStatus.CONVICTED) and accused_ids:
            for person_id in accused_ids:
                arrest_status = {
                    FIRStatus.CONVICTED: ArrestStatus.JUDICIAL_CUSTODY,
                    FIRStatus.CLOSED: ArrestStatus.RELEASED_ON_BAIL,
                    FIRStatus.CHARGESHEET_FILED: random.choice(list(ArrestStatus)),
                }[status]
                arrests.append(Arrest(
                    person_id=person_id, fir_id=fir_id, arresting_officer_id=officer_id,
                    arrest_date=start + timedelta(days=random.randint(1, 15)),
                    status=arrest_status,
                ))

        if status in (FIRStatus.CHARGESHEET_FILED, FIRStatus.CONVICTED):
            chargesheets.append(ChargeSheet(
                fir_id=fir_id, court_id=random.choice(courts).id, filing_officer_id=officer_id,
                filed_date=start + timedelta(days=random.randint(30, 180)),
                status=random.choices(list(ChargeSheetStatus), weights=[0.75, 0.15, 0.1])[0],
            ))

    for chunk in chunked(investigations, 500):
        session.add_all(chunk)
    for chunk in chunked(arrests, 500):
        session.add_all(chunk)
    for chunk in chunked(chargesheets, 500):
        session.add_all(chunk)
    session.flush()
    return investigations, arrests, chargesheets


def mark_repeat_offenders(session):
    """Post-pass: flag Accused.repeat_offender for any person accused on
    more than one FIR, and assign a plausible custody_status. Additive —
    doesn't touch how generate_crimes_and_firs constructs these rows."""
    rows = session.query(Accused).all()
    by_person = defaultdict(list)
    for row in rows:
        by_person[row.person_id].append(row)
    repeat_count = 0
    for person_id, accused_rows in by_person.items():
        is_repeat = len(accused_rows) > 1
        if is_repeat:
            repeat_count += 1
        for row in accused_rows:
            row.repeat_offender = is_repeat
            row.custody_status = random.choices(
                ["in custody", "released on bail", "absconding", None],
                weights=[0.3, 0.35, 0.15, 0.2],
            )[0]
    session.flush()
    return repeat_count


# ---------------------------------------------------------------------------
# Call detail records (bulk CDRs)
# ---------------------------------------------------------------------------

def generate_call_records(session, phones, n_calls):
    if len(phones) < 2:
        return []
    phone_ids = [p.id for p in phones]
    records = []
    for _ in range(n_calls):
        caller, receiver = random.sample(phone_ids, 2)
        missed = random.random() < 0.15
        records.append(CallRecord(
            caller_phone_id=caller,
            receiver_phone_id=receiver,
            timestamp=random_date_within(730),
            duration_seconds=0 if missed else random.randint(8, 1800),
        ))
    for chunk in chunked(records, 1000):
        session.bulk_save_objects(chunk)
    session.flush()
    return records


# ---------------------------------------------------------------------------
# Bulk transactions: normal noise + layering + smurfing + round-tripping
# ---------------------------------------------------------------------------

def generate_bulk_transactions(session, accounts, n_transactions):
    if len(accounts) < 3:
        return []
    account_ids = [a.id for a in accounts]
    transactions = []

    n_pattern = int(n_transactions * 0.25)
    n_noise = n_transactions - n_pattern

    # --- Plain noise: everyday transfers, mostly not suspicious ---
    for _ in range(n_noise):
        sender, receiver = random.sample(account_ids, 2)
        transactions.append(Transaction(
            amount=round(random.uniform(200, 60000), 2),
            timestamp=random_date_within(730),
            sender_account_id=sender, receiver_account_id=receiver,
            is_suspicious=random.random() < 0.03,
        ))

    remaining = n_pattern
    # --- Layering chains: A -> B -> C -> D -> E, decreasing amount ---
    while remaining > 0:
        chain_len = min(random.randint(4, 6), remaining + 1)
        chain_accounts = random.sample(account_ids, min(chain_len, len(account_ids)))
        if len(chain_accounts) < 2:
            break
        amount = round(random.uniform(80000, 400000), 2)
        base_time = random_date_within(365)
        for i in range(len(chain_accounts) - 1):
            amount *= random.uniform(0.75, 0.92)
            transactions.append(Transaction(
                amount=round(amount, 2),
                timestamp=base_time + timedelta(hours=i * random.randint(6, 48)),
                sender_account_id=chain_accounts[i], receiver_account_id=chain_accounts[i + 1],
                is_suspicious=True,
            ))
            remaining -= 1
            if remaining <= 0:
                break

    # --- Smurfing: one source fans out into many small transfers ---
    while remaining > 0:
        source = random.choice(account_ids)
        fan_out = random.sample([a for a in account_ids if a != source], min(random.randint(5, 9), len(account_ids) - 1))
        base_time = random_date_within(365)
        for dest in fan_out:
            transactions.append(Transaction(
                amount=round(random.uniform(4000, 48000), 2),
                timestamp=base_time + timedelta(hours=random.randint(0, 72)),
                sender_account_id=source, receiver_account_id=dest,
                is_suspicious=True,
            ))
            remaining -= 1
            if remaining <= 0:
                break

    # --- Round-tripping: A -> B -> C -> A, funds return to origin ---
    while remaining > 0:
        cycle = random.sample(account_ids, min(3, len(account_ids)))
        if len(cycle) < 3:
            break
        amount = round(random.uniform(50000, 250000), 2)
        base_time = random_date_within(365)
        cycle_full = cycle + [cycle[0]]
        for i in range(len(cycle_full) - 1):
            transactions.append(Transaction(
                amount=round(amount * random.uniform(0.95, 1.0), 2),
                timestamp=base_time + timedelta(hours=i * random.randint(4, 24)),
                sender_account_id=cycle_full[i], receiver_account_id=cycle_full[i + 1],
                is_suspicious=True,
            ))
            remaining -= 1
            if remaining <= 0:
                break

    for chunk in chunked(transactions, 1000):
        session.bulk_save_objects(chunk)
    session.flush()
    return transactions


# ---------------------------------------------------------------------------
# Users — one demo login per SystemRole (Stage E1)
# ---------------------------------------------------------------------------

def generate_users(session, officers, rand):
    seed_roles(session)  # reuse the app's own idempotent role seeding
    roles_by_name = {r.name: r for r in session.query(Role).all()}

    credentials = []
    users = []

    plan = [
        (SystemRole.ADMINISTRATOR, "admin_demo", "Administrator", 1),
        (SystemRole.SUPERVISOR, "supervisor_demo", "Supervisor", 1),
        (SystemRole.INVESTIGATOR, "investigator_demo", "Investigator", 3),
        (SystemRole.ANALYST, "analyst_demo", "Analyst", 2),
        (SystemRole.POLICY_MAKER, "policymaker_demo", "Policy Maker", 1),
        (SystemRole.READ_ONLY, "readonly_demo", "Read Only", 1),
    ]

    officer_pool = list(officers)
    random.shuffle(officer_pool)
    officer_cursor = 0

    for role_enum, username_base, label, count in plan:
        for i in range(count):
            username = username_base if count == 1 else f"{username_base}{i + 1}"
            password = gen_password(rand)
            officer_id = None
            if role_enum in (SystemRole.INVESTIGATOR, SystemRole.SUPERVISOR) and officer_cursor < len(officer_pool):
                officer_id = officer_pool[officer_cursor].id
                officer_cursor += 1

            user = User(
                username=username,
                email=f"{username}@sherlock.karnatakapolice.demo",
                password_hash=hash_password(password),
                officer_id=officer_id,
                full_name=f"{fake.first_name()} {fake.last_name()} ({label})",
                last_login_at=random_date_within(20),
            )
            session.add(user)
            session.flush()
            session.add(UserRole(user_id=user.id, role_id=roles_by_name[role_enum].id))
            users.append(user)
            credentials.append({"username": username, "password": password, "role": role_enum.value})

    session.flush()
    return users, credentials


# ---------------------------------------------------------------------------
# Investigation sessions + full collaboration surface
# ---------------------------------------------------------------------------

def _make_finding(person_ids, account_ids, fir_number):
    agent = random.choice(AGENT_NAMES)
    entities = [f"person_{pid}" for pid in person_ids[:2]] + [f"account_{aid}" for aid in account_ids[:1]]
    confidence = round(random.uniform(0.55, 0.98), 2)
    validated = random.random() > 0.08
    return {
        "agent_name": agent,
        "finding_type": random.choice(["network_link", "pattern_match", "financial_trail", "timeline_event", "profile_summary"]),
        "summary": f"{agent} identified a notable link relevant to {fir_number}.",
        "evidence": [f"Record cross-referenced against {fir_number}", "Corroborated by associated entity records"],
        "confidence": confidence,
        "source_entities": entities,
        "metadata": {},
        "validated": validated,
        "validation_notes": "Evidence-backed." if validated else "Insufficient supporting evidence.",
        "reasoning": f"{agent} correlated case entities against the graph and historical records.",
        "supporting_graph": {"nodes": entities},
        "related_documents": [fir_number],
    }


def generate_sessions_and_collaboration(session, fir_rows, officers, persons_by_id, accounts_by_person, n_sessions):
    all_sessions, all_board_objects, all_comments = [], [], []
    all_notifications, all_reviews, all_presences = [], [], []
    all_activity, all_assignments, all_turns, all_discussions = [], [], [], []

    chosen = random.sample(fir_rows, min(n_sessions, len(fir_rows))) if n_sessions <= len(fir_rows) \
        else [random.choice(fir_rows) for _ in range(n_sessions)]

    for i, (fir_id, fir_number, status, filed_date, accused_ids) in enumerate(chosen):
        session_code = f"SESSION-2026-{i + 1:04d}"
        title = random.choice(SESSION_TITLE_TEMPLATES).format(fir=fir_number)

        sess_status = random.choices(list(InvestigationSessionStatus), weights=[0.45, 0.3, 0.15, 0.1])[0]
        priority = random.choices(list(InvestigationPriority), weights=[0.2, 0.4, 0.3, 0.1])[0]

        opener, owner = random.sample(officers, 2)
        opened_at = filed_date + timedelta(days=random.randint(0, 5))
        closed_at = opened_at + timedelta(days=random.randint(5, 90)) if sess_status in (
            InvestigationSessionStatus.CLOSED, InvestigationSessionStatus.ARCHIVED,
            InvestigationSessionStatus.REOPENED) else None
        reopened_at = closed_at + timedelta(days=random.randint(1, 30)) if sess_status == InvestigationSessionStatus.REOPENED else None
        archived_at = closed_at + timedelta(days=random.randint(30, 120)) if sess_status == InvestigationSessionStatus.ARCHIVED else None

        inv_session = InvestigationSession(
            session_code=session_code, fir_id=fir_id, title=title,
            status=sess_status, priority=priority,
            opened_by_officer_id=opener.id, owner_officer_id=owner.id,
            opened_at=opened_at, closed_at=closed_at, reopened_at=reopened_at, archived_at=archived_at,
            notes=f"Working notes for {fir_number}: {fake.sentence(nb_words=12)}",
        )
        session.add(inv_session)
        session.flush()
        all_sessions.append(inv_session)

        # --- Assignments ---
        assignees = random.sample(officers, min(random.randint(1, 3), len(officers)))
        roles_cycle = ["lead", "investigator", "reviewer"]
        for idx, officer in enumerate(assignees):
            all_assignments.append(SessionAssignment(
                session_id=inv_session.id, officer_id=officer.id,
                role=roles_cycle[idx] if idx < len(roles_cycle) else "investigator",
                assigned_at=opened_at + timedelta(hours=random.randint(0, 48)),
            ))

        # --- Activity log ---
        all_activity.append(SessionActivity(session_id=inv_session.id, event_type="opened",
                                             actor_officer_id=opener.id, created_at=opened_at))
        for officer in assignees:
            all_activity.append(SessionActivity(session_id=inv_session.id, event_type="assigned",
                                                 actor_officer_id=opener.id,
                                                 detail=f"Assigned officer {officer.badge_number}",
                                                 created_at=opened_at + timedelta(hours=random.randint(1, 40))))
        all_activity.append(SessionActivity(session_id=inv_session.id, event_type="note_added",
                                             actor_officer_id=owner.id, detail="Initial case notes recorded.",
                                             created_at=opened_at + timedelta(days=1)))
        if closed_at:
            all_activity.append(SessionActivity(session_id=inv_session.id, event_type="closed",
                                                 actor_officer_id=owner.id, created_at=closed_at))
        if reopened_at:
            all_activity.append(SessionActivity(session_id=inv_session.id, event_type="reopened",
                                                 actor_officer_id=owner.id, created_at=reopened_at))
        if archived_at:
            all_activity.append(SessionActivity(session_id=inv_session.id, event_type="archived",
                                                 actor_officer_id=owner.id, created_at=archived_at))

        # --- Conversation turns (voice/chat query history + findings) ---
        person_pool = accused_ids if accused_ids else list(persons_by_id.keys())[:5]
        account_pool = []
        for pid in person_pool:
            account_pool.extend(accounts_by_person.get(pid, []))

        n_turns = random.randint(2, 5)
        turns_findings = []
        for t in range(n_turns):
            person_id = random.choice(person_pool) if person_pool else None
            person_name = persons_by_id[person_id].name if person_id else None
            template = random.choice(VOICE_QUERY_TEMPLATES)
            raw_query = template.format(fir=fir_number, person=person_name or "the accused")
            findings = [_make_finding(person_pool, account_pool, fir_number) for _ in range(random.randint(1, 3))]
            turns_findings.append(findings)

            mentions = [{"kind": "person", "id": pid, "label": persons_by_id[pid].name} for pid in person_pool[:3]]
            turn = ConversationTurn(
                session_id=inv_session.id, turn_index=t,
                raw_query=raw_query, resolved_query=raw_query,
                last_person_id=person_id, last_person_name=person_name,
                last_fir_id=fir_id,
                last_account_id=account_pool[0] if account_pool else None,
                response_summary=f"{findings[0]['agent_name']} reported: {findings[0]['summary']}",
                findings_json=json.dumps(findings),
                entity_mentions_json=json.dumps(mentions),
                created_at=opened_at + timedelta(hours=t * random.randint(2, 30) + 1),
            )
            session.add(turn)
            session.flush()
            all_turns.append(turn)

        # --- Discussion record for the final turn ---
        last_findings = turns_findings[-1]
        opinions = [{
            "agent_name": f["agent_name"], "finding_type": f["finding_type"], "claim": f["summary"],
            "confidence": f["confidence"], "evidence": f["evidence"], "validated": f["validated"],
            "missing_evidence": not f["validated"], "source_entities": f["source_entities"],
        } for f in last_findings]
        disagreements = []
        if len(opinions) >= 2 and random.random() < 0.3:
            disagreements.append({
                "entity_kind": "person", "entity_id": person_pool[0] if person_pool else 0,
                "entity_label": person_name or "unknown",
                "opinions": opinions[:2],
                "confidence_spread": round(abs(opinions[0]["confidence"] - opinions[1]["confidence"]), 2),
                "explanation": "Agents disagree on the strength of this connection.",
            })
        per_agent_conf = {o["agent_name"]: o["confidence"] for o in opinions}
        consensus = {
            "overall_confidence": round(sum(per_agent_conf.values()) / max(len(per_agent_conf), 1), 2),
            "per_agent_confidence": per_agent_conf,
            "consensus_score": 1.0 if not disagreements else 0.6,
            "agreement_count": len(opinions) - len(disagreements),
            "disagreement_count": len(disagreements),
            "recommended_conclusion": f"Findings support continued investigation of {fir_number}.",
            "evidence_requests": [o["agent_name"] for o in opinions if o["missing_evidence"]],
        }
        all_discussions.append(DiscussionRecord(
            session_id=inv_session.id, turn_index=n_turns - 1,
            query=all_turns[-1].raw_query,
            opinions_json=json.dumps(opinions),
            disagreements_json=json.dumps(disagreements),
            consensus_json=json.dumps(consensus),
            created_at=all_turns[-1].created_at,
        ))

        # --- Board objects ---
        n_board = random.randint(1, 4)
        session_board_objects = []
        for _ in range(n_board):
            obj_type = random.choices(list(BoardObjectType), weights=[0.5, 0.3, 0.2])[0]
            payload = None
            if obj_type == BoardObjectType.LINK and len(person_pool) >= 2:
                payload = json.dumps({"from": f"person_{person_pool[0]}", "to": f"person_{person_pool[-1]}", "relation": "suspected_link"})
                content = f"Possible link between {persons_by_id[person_pool[0]].name} and {persons_by_id[person_pool[-1]].name}"
            elif obj_type == BoardObjectType.HYPOTHESIS:
                content = f"Hypothesis: {random.choice(BOARD_NOTE_TEMPLATES)}"
            else:
                content = random.choice(BOARD_NOTE_TEMPLATES)
            bo = BoardObject(
                session_id=inv_session.id, object_type=obj_type, content=content, payload=payload,
                created_by_officer_id=random.choice(assignees).id,
                created_at=opened_at + timedelta(days=random.randint(1, 10)),
            )
            session.add(bo)
            session.flush()
            all_board_objects.append(bo)
            session_board_objects.append(bo)

        # --- Comments (some with @mentions -> notifications) ---
        n_comments = random.randint(2, 8)
        for c in range(n_comments):
            target_type = random.choice(list(CommentTargetType))
            if target_type == CommentTargetType.FINDING:
                target_ref = f"{random.randint(0, n_turns - 1)}:0"
            elif target_type == CommentTargetType.EVIDENCE:
                target_ref = f"{random.randint(0, n_turns - 1)}:0:evidence:0"
            elif target_type == CommentTargetType.BOARD_OBJECT and session_board_objects:
                target_ref = str(random.choice(session_board_objects).id)
            else:
                target_ref = f"person_{random.choice(person_pool)}" if person_pool else "case:general"

            author = random.choice(assignees)
            mentioned_officer = random.choice(officers)
            template = random.choice(COMMENT_TEMPLATES)
            body = template.format(mention=mentioned_officer.name.split()[-1]) if "{mention}" in template else template

            comment = Comment(
                session_id=inv_session.id, target_type=target_type, target_ref=target_ref,
                author_officer_id=author.id, body=body,
                created_at=opened_at + timedelta(days=random.randint(1, 20), hours=random.randint(0, 23)),
            )
            session.add(comment)
            session.flush()
            all_comments.append(comment)

            if "{mention}" in template:
                all_notifications.append(Notification(
                    recipient_officer_id=mentioned_officer.id, notification_type=NotificationType.MENTION,
                    session_id=inv_session.id, related_comment_id=comment.id,
                    message=f"You were mentioned in a comment on {session_code}.",
                    created_at=comment.created_at,
                    read_at=comment.created_at + timedelta(hours=random.randint(1, 48)) if random.random() < 0.6 else None,
                ))

        # --- Assignment notifications ---
        for officer in assignees:
            all_notifications.append(Notification(
                recipient_officer_id=officer.id, notification_type=NotificationType.ASSIGNMENT,
                session_id=inv_session.id, message=f"You were assigned to {session_code}.",
                created_at=opened_at + timedelta(hours=random.randint(1, 24)),
                read_at=opened_at + timedelta(hours=random.randint(25, 72)) if random.random() < 0.7 else None,
            ))

        # --- Board update notification ---
        if session_board_objects:
            all_notifications.append(Notification(
                recipient_officer_id=owner.id, notification_type=NotificationType.BOARD_UPDATE,
                session_id=inv_session.id, message=f"New board activity on {session_code}.",
                created_at=session_board_objects[-1].created_at,
                read_at=None,
            ))

        # --- Review requests (roughly 45% of sessions go through review) ---
        if random.random() < 0.45:
            reviewer = random.choice([o for o in officers if o.id != owner.id])
            req_status = random.choices(list(ReviewStatus), weights=[0.1, 0.2, 0.55, 0.15])[0]
            requested_at = (closed_at or opened_at) + timedelta(days=random.randint(1, 10))
            decided_at = requested_at + timedelta(days=random.randint(1, 7)) if req_status in (
                ReviewStatus.APPROVED, ReviewStatus.REJECTED) else None
            review = ReviewRequest(
                session_id=inv_session.id, status=req_status,
                requested_by_officer_id=owner.id, reviewer_officer_id=reviewer.id,
                notes="Requesting review before closing the case file.",
                decision_notes="Findings are well-supported." if req_status == ReviewStatus.APPROVED else (
                    "Needs stronger evidence before approval." if req_status == ReviewStatus.REJECTED else None),
                created_at=requested_at, decided_at=decided_at,
            )
            session.add(review)
            session.flush()
            all_reviews.append(review)
            all_notifications.append(Notification(
                recipient_officer_id=reviewer.id, notification_type=NotificationType.REVIEW_REQUEST,
                session_id=inv_session.id, related_review_id=review.id,
                message=f"Review requested on {session_code}.", created_at=requested_at,
                read_at=requested_at + timedelta(hours=random.randint(1, 40)) if random.random() < 0.6 else None,
            ))
            if decided_at:
                all_notifications.append(Notification(
                    recipient_officer_id=owner.id, notification_type=NotificationType.REVIEW_DECISION,
                    session_id=inv_session.id, related_review_id=review.id,
                    message=f"Review decision recorded on {session_code}: {req_status.value}.",
                    created_at=decided_at,
                    read_at=decided_at + timedelta(hours=random.randint(1, 30)) if random.random() < 0.8 else None,
                ))

        # --- Presence (only meaningful for open/reopened sessions) ---
        if sess_status in (InvestigationSessionStatus.OPEN, InvestigationSessionStatus.REOPENED):
            for officer in random.sample(assignees, min(len(assignees), random.randint(1, len(assignees)))):
                all_presences.append(SessionPresence(
                    session_id=inv_session.id, officer_id=officer.id,
                    status=random.choices(list(PresenceStatus), weights=[0.7, 0.3])[0],
                    last_seen_at=ACTIVITY_WINDOW_END - timedelta(minutes=random.randint(0, 90)),
                ))

    for bucket in (all_notifications, all_presences):
        for chunk in chunked(bucket, 500):
            session.add_all(chunk)
    session.add_all(all_activity)
    session.add_all(all_assignments)
    session.add_all(all_discussions)
    session.flush()

    return {
        "sessions": all_sessions, "assignments": all_assignments, "activity": all_activity,
        "turns": all_turns, "discussions": all_discussions, "board_objects": all_board_objects,
        "comments": all_comments, "notifications": all_notifications, "reviews": all_reviews,
        "presences": all_presences,
    }


# ---------------------------------------------------------------------------
# Audit log (bulk, Stage E3)
# ---------------------------------------------------------------------------

AUDIT_ACTION_WEIGHTS = {
    AuditAction.LOGIN: 0.22,
    AuditAction.LOGIN_FAILED: 0.05,
    AuditAction.LOGOUT: 0.15,
    AuditAction.TOKEN_REFRESH: 0.12,
    AuditAction.TOKEN_REVOKED: 0.02,
    AuditAction.PERMISSION_DENIED: 0.04,
    AuditAction.ROLE_CHANGED: 0.01,
    AuditAction.INVESTIGATION_VIEWED: 0.15,
    AuditAction.EVIDENCE_VIEWED: 0.1,
    AuditAction.CASE_EXPORTED: 0.04,
    AuditAction.REPORT_GENERATED: 0.04,
    AuditAction.VOICE_COMMAND: 0.05,
    AuditAction.RECORD_ARCHIVED: 0.005,
    AuditAction.RECORD_DELETED: 0.005,
}


def generate_audit_logs(session, users, fir_numbers, n_events):
    actions = list(AUDIT_ACTION_WEIGHTS.keys())
    weights = list(AUDIT_ACTION_WEIGHTS.values())
    logs = []
    window_seconds = int((ACTIVITY_WINDOW_END - ACTIVITY_WINDOW_START).total_seconds())

    for _ in range(n_events):
        user = random.choice(users)
        action = random.choices(actions, weights=weights)[0]
        created_at = ACTIVITY_WINDOW_START + timedelta(seconds=random.randint(0, window_seconds))

        success = True
        metadata = {}
        target = None
        if action == AuditAction.LOGIN_FAILED:
            success = False
            metadata = {"reason": "invalid_password"}
        elif action == AuditAction.PERMISSION_DENIED:
            success = False
            metadata = {"permission": random.choice(["view_audit", "administer_system", "manage_users", "export_case"])}
            target = random.choice(fir_numbers) if fir_numbers else None
        elif action == AuditAction.ROLE_CHANGED:
            metadata = {"new_role": random.choice(list(SystemRole)).value}
            target = f"user:{user.id}"
        elif action in (AuditAction.INVESTIGATION_VIEWED, AuditAction.EVIDENCE_VIEWED, AuditAction.CASE_EXPORTED):
            target = f"fir:{random.choice(fir_numbers)}" if fir_numbers else None
            if action == AuditAction.CASE_EXPORTED:
                metadata = {"format": "pdf"}
        elif action == AuditAction.REPORT_GENERATED:
            target = f"fir:{random.choice(fir_numbers)}" if fir_numbers else None
            metadata = {"format": "pdf"}
        elif action == AuditAction.VOICE_COMMAND:
            metadata = {"transcript": random.choice(VOICE_QUERY_TEMPLATES).format(fir="the case", person="the accused")}
        elif action in (AuditAction.RECORD_ARCHIVED, AuditAction.RECORD_DELETED):
            target = f"session:{random.randint(1, 999)}"

        logs.append(AuditLog(
            user_id=user.id if action != AuditAction.LOGIN_FAILED or random.random() < 0.7 else None,
            username=user.username,
            action=action.value,
            target=target,
            success=success,
            ip_address=fake.ipv4_public(),
            user_agent=fake.user_agent(),
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=created_at,
        ))

    for chunk in chunked(logs, 1000):
        session.bulk_save_objects(chunk)
    session.flush()
    return logs


# ---------------------------------------------------------------------------
# Connectivity guarantee — no isolated Person nodes
# ---------------------------------------------------------------------------

def ensure_no_isolated_persons(session, persons):
    connected = set()
    for row in session.query(PersonAssociation.person_a_id, PersonAssociation.person_b_id).all():
        connected.add(row[0])
        connected.add(row[1])
    for row in session.query(Accused.person_id).all():
        connected.add(row[0])
    for row in session.query(Victim.person_id).all():
        connected.add(row[0])
    for row in session.query(Witness.person_id).all():
        connected.add(row[0])
    for row in session.query(OrganizationMembership.person_id).all():
        connected.add(row[0])

    all_ids = [p.id for p in persons]
    isolated = [pid for pid in all_ids if pid not in connected]
    extra = []
    for pid in isolated:
        other = random.choice([x for x in all_ids if x != pid])
        extra.append(PersonAssociation(
            person_a_id=pid, person_b_id=other,
            relation_type=RelationType.NEIGHBOR, strength=round(random.uniform(0.2, 0.5), 2),
        ))
    session.add_all(extra)
    session.flush()
    return len(isolated)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_dataset(session):
    from backend.graph.builder_networkx import build_graph

    counts = {}
    counts["persons"] = session.query(Person).count()
    counts["locations"] = session.query(Location).count()
    counts["officers"] = session.query(Officer).count()
    counts["crimes"] = session.query(Crime).count()
    counts["firs"] = session.query(FIR).count()
    counts["accused_records"] = session.query(Accused).count()
    counts["victim_records"] = session.query(Victim).count()
    counts["witness_records"] = session.query(Witness).count()
    counts["person_crime_links"] = session.query(PersonCrimeLink).count()
    counts["person_associations"] = session.query(PersonAssociation).count()
    counts["aliases"] = session.query(PersonAlias).count()
    counts["organizations"] = session.query(Organization).count()
    counts["organization_memberships"] = session.query(OrganizationMembership).count()
    counts["courts"] = session.query(Court).count()
    counts["weapons"] = session.query(Weapon).count()
    counts["properties"] = session.query(Property).count()
    counts["investigations"] = session.query(Investigation).count()
    counts["arrests"] = session.query(Arrest).count()
    counts["chargesheets"] = session.query(ChargeSheet).count()
    counts["vehicles"] = session.query(Vehicle).count()
    counts["phones"] = session.query(Phone).count()
    counts["call_records"] = session.query(CallRecord).count()
    counts["bank_accounts"] = session.query(BankAccount).count()
    counts["transactions"] = session.query(Transaction).count()
    counts["users"] = session.query(User).count()
    counts["roles"] = session.query(Role).count()
    counts["user_roles"] = session.query(UserRole).count()
    counts["investigation_sessions"] = session.query(InvestigationSession).count()
    counts["session_assignments"] = session.query(SessionAssignment).count()
    counts["session_activity"] = session.query(SessionActivity).count()
    counts["conversation_turns"] = session.query(ConversationTurn).count()
    counts["discussion_records"] = session.query(DiscussionRecord).count()
    counts["board_objects"] = session.query(BoardObject).count()
    counts["comments"] = session.query(Comment).count()
    counts["notifications"] = session.query(Notification).count()
    counts["review_requests"] = session.query(ReviewRequest).count()
    counts["session_presence"] = session.query(SessionPresence).count()
    counts["audit_log"] = session.query(AuditLog).count()

    # Referential sanity spot-checks (constructed entirely from real FKs
    # captured at insert time, but verified here rather than assumed).
    checks = {}
    fir_ids = {r[0] for r in session.query(FIR.id).all()}
    checks["accused_fk_ok"] = all(r[0] in fir_ids for r in session.query(Accused.fir_id).all())
    checks["sessions_have_assignment"] = (
        session.query(InvestigationSession.id).count() == 0
        or session.query(InvestigationSession.id)
        .filter(InvestigationSession.id.in_(session.query(SessionAssignment.session_id)))
        .count() > 0
    )
    checks["board_objects_reference_real_sessions"] = all(
        r[0] in {s[0] for s in session.query(InvestigationSession.id).all()}
        for r in session.query(BoardObject.session_id).all()
    )
    checks["every_role_has_a_user"] = session.query(UserRole.role_id).distinct().count() == len(list(SystemRole))

    G = build_graph(session)
    graph_stats = {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()}

    return counts, checks, graph_stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate the full SHERLOCK demo dataset")
    size_group = parser.add_mutually_exclusive_group()
    size_group.add_argument("--small", action="store_const", dest="size", const="small")
    size_group.add_argument("--medium", action="store_const", dest="size", const="medium")
    size_group.add_argument("--large", action="store_const", dest="size", const="large")
    parser.set_defaults(size="medium")

    parser.add_argument("--persons", type=int, default=None, help="Override the preset's person count")
    parser.add_argument("--crimes", type=int, default=None, help="Override the preset's crime count")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--deterministic", action="store_true",
                         help="Print a checksum of key rows so two runs can be diffed for reproducibility")
    args = parser.parse_args()

    preset = dict(SCALE_PRESETS[args.size])
    if args.persons:
        preset["persons"] = args.persons
    if args.crimes:
        preset["crimes"] = args.crimes

    random.seed(args.seed)
    Faker.seed(args.seed)
    rand = random.Random(args.seed * 7919 + 1)  # separate stream, used only for credential generation

    if args.reset:
        print("Dropping and recreating all tables...")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        print(f"Preset: {args.size}  (persons={preset['persons']}, crimes={preset['crimes']})")

        print(f"Generating {len(KARNATAKA_LOCATIONS)} locations...")
        locations = generate_locations(session)

        print(f"Generating {preset['persons']} persons (+ aliases)...")
        persons = generate_persons(session, locations, preset["persons"])
        persons_by_id = {p.id: p for p in persons}

        print("Generating phones, vehicles, bank accounts...")
        phones, vehicles, accounts = generate_assets(session, persons)
        accounts_by_person = defaultdict(list)
        for acc in accounts:
            accounts_by_person[acc.owner_id].append(acc.id)

        print(f"Generating {preset['officers']} officers...")
        officers = generate_officers(session, preset["officers"])

        pool_size = max(5, preset["persons"] // 20)
        repeat_offender_pool = random.sample(persons, pool_size)
        print(f"Designated {pool_size} persons as the repeat-offender pool.")

        print(f"Generating {preset['crimes']} crimes + FIRs + person links...")
        crimes, firs, links = generate_crimes_and_firs(
            session, locations, persons, preset["crimes"], repeat_offender_pool, officers=officers)

        print("Generating person associations (co-accused + social ties)...")
        generate_associations(session, persons, links)

        print(f"Injecting money-mule fraud ring (size={preset['ring_size']})...")
        hub = generate_fraud_ring(session, locations, persons, preset["ring_size"], officers=officers)
        print(f"  -> Hub account owner: {hub.name} (person_id={hub.id})")

        print(f"Generating {preset['n_extra_associations']} additional relationship edges (hubs, bridges, clusters)...")
        generate_relationship_density(session, persons, repeat_offender_pool, preset["n_extra_associations"])

        print("Generating courts...")
        courts = generate_courts(session)

        n_gangs, n_companies, n_ngos = preset["n_orgs"]
        print(f"Generating organizations ({n_gangs} gangs, {n_companies} companies, {n_ngos} NGOs)...")
        orgs, memberships, gang_leaders = generate_organizations(
            session, persons, repeat_offender_pool, n_gangs, n_companies, n_ngos)
        print(f"  -> Hidden kingpins (gang leaders): {', '.join(l.name for l, _ in gang_leaders)}")

        # Complete FIR set (includes the fraud-ring FIR, which isn't in `firs`)
        all_fir_rows = session.query(FIR.id, FIR.fir_number, FIR.status, FIR.filed_date,
                                      FIR.investigating_officer_id).all()
        fir_ids = [r[0] for r in all_fir_rows]

        fir_crime_info = {}
        for fir_id, ctype, location_id in (
            session.query(FIR.id, Crime.type, Crime.location_id).join(Crime, FIR.crime_id == Crime.id).all()
        ):
            fir_crime_info[fir_id] = (ctype, location_id)

        accused_by_fir = defaultdict(list)
        for person_id, fir_id in session.query(Accused.person_id, Accused.fir_id).all():
            accused_by_fir[fir_id].append(person_id)

        print("Generating weapons and seized property...")
        weapons, properties = generate_weapons_and_properties(
            session, fir_ids, fir_crime_info, accused_by_fir, officers, courts)

        print("Generating investigations, arrests, and chargesheets...")
        investigations, arrests, chargesheets = generate_investigations_arrests_chargesheets(
            session, all_fir_rows, officers, courts, accused_by_fir)

        print("Marking repeat offenders...")
        n_repeat = mark_repeat_offenders(session)
        print(f"  -> {n_repeat} persons flagged as repeat offenders.")

        print(f"Generating {preset['n_calls']} call detail records...")
        generate_call_records(session, phones, preset["n_calls"])

        print(f"Generating {preset['n_transactions']} bulk transactions (layering / smurfing / round-tripping)...")
        generate_bulk_transactions(session, accounts, preset["n_transactions"])

        print("Ensuring no isolated Person nodes...")
        n_fixed = ensure_no_isolated_persons(session, persons)
        print(f"  -> Connected {n_fixed} previously isolated persons.")

        print("Generating demo user accounts (one per role)...")
        users, credentials = generate_users(session, officers, rand)

        print(f"Generating {preset['n_sessions']} investigation sessions + full collaboration surface...")
        session_fir_rows = [
            (fir_id, fir_number, status, filed_date, accused_by_fir.get(fir_id, []))
            for fir_id, fir_number, status, filed_date, _officer_id in all_fir_rows
        ]
        collab = generate_sessions_and_collaboration(
            session, session_fir_rows, officers, persons_by_id, accounts_by_person, preset["n_sessions"])

        fir_numbers = [r[1] for r in all_fir_rows]
        print(f"Generating {preset['n_audit']} audit log events...")
        generate_audit_logs(session, users, fir_numbers, preset["n_audit"])

        session.commit()

        print("\nValidating dataset...")
        counts, checks, graph_stats = validate_dataset(session)

        print("\n=== Integrity checks ===")
        for name, ok in checks.items():
            print(f"  {'✓' if ok else '✗'} {name}")
        if not all(checks.values()):
            raise RuntimeError("One or more integrity checks failed — see above.")

        print("\n=== SHERLOCK Demo Dataset — Final Report ===")
        label_width = max(len(k) for k in counts) + 2
        for key in [
            "persons", "firs", "crimes", "accused_records", "victim_records", "witness_records",
            "person_associations", "organizations", "organization_memberships", "weapons", "properties",
            "investigations", "arrests", "chargesheets", "transactions", "call_records",
            "investigation_sessions", "board_objects", "comments", "audit_log", "users",
        ]:
            print(f"{key.replace('_', ' ').title():<{label_width}} {counts[key]}")
        print(f"{'Graph Nodes':<{label_width}} {graph_stats['nodes']}")
        print(f"{'Graph Edges':<{label_width}} {graph_stats['edges']}")

        print("\n=== Demo credentials (rotate before any real deployment) ===")
        for c in credentials:
            print(f"  {c['role']:<15} username={c['username']:<20} password={c['password']}")

        if args.deterministic:
            first_person = session.query(Person).order_by(Person.id).first()
            last_audit = session.query(AuditLog).order_by(AuditLog.id.desc()).first()
            checksum = f"{first_person.name}|{first_person.age}|{last_audit.action}|{last_audit.target}"
            print(f"\nDeterminism checksum (should match across runs with the same --seed/{args.size}): {checksum}")

        print("\nSHERLOCK demo dataset generated successfully.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
