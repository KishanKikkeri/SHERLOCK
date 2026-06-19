"""
SHERLOCK — Synthetic dataset generator (Phase 3).

Generates a realistic-but-fake Karnataka crime dataset with several
patterns DELIBERATELY injected so the analysis agents have something
real to find:

  1. Entity Resolution material — ~30% of persons get 2-3 name variants
     (e.g. "Ravi Kumar" / "R Kumar" / "R. Kumar" / "Ravi K"), and crime
     records reference persons using these variants rather than the
     canonical name.

  2. Repeat offenders — a pool of ~5% of persons is over-weighted as the
     "accused" in burglary/theft crimes, so the Behavioral Profiling /
     Pattern agents can surface them as repeat offenders.

  3. Festival-season burglary spike — burglary crimes in Mysuru are
     biased toward Sep-Nov (Dasara/Diwali season), at roughly +40% over
     baseline, for the Pattern & Forecasting agents to detect.

  4. Money-mule fraud ring — a small cluster of persons + bank accounts
     forms a fan-in transaction pattern into a "hub" account, flagged as
     suspicious, tied to a fraud FIR, for the Financial Intelligence Agent.

Usage:
    python -m backend.datasets.generate_synthetic_data \
        --persons 500 --crimes 1000 --reset

Scale up to --persons 5000 --crimes 10000 once the pipeline is validated;
defaults are smaller so iteration during development stays fast.
"""

import argparse
import random
from datetime import datetime, timedelta

from faker import Faker

from backend.database.config import Base, engine, SessionLocal
from backend.database.models import (
    Location,
    Person,
    PersonAlias,
    Crime,
    FIR,
    PersonCrimeLink,
    Vehicle,
    Phone,
    BankAccount,
    Transaction,
    PersonAssociation,
    Gender,
    CrimeType,
    FIRStatus,
    PersonRole,
    RelationType,
)

fake = Faker("en_IN")

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

KARNATAKA_LOCATIONS = [
    # name, district, lat, lon
    ("Mysuru City", "Mysuru", 12.2958, 76.6394),
    ("Bengaluru Central", "Bengaluru Urban", 12.9716, 77.5946),
    ("Hubballi", "Dharwad", 15.3647, 75.1240),
    ("Mangaluru", "Dakshina Kannada", 12.9141, 74.8560),
    ("Belagavi", "Belagavi", 15.8497, 74.4977),
    ("Tumakuru", "Tumakuru", 13.3409, 77.1010),
    ("Davanagere", "Davanagere", 14.4644, 75.9932),
    ("Ballari", "Ballari", 15.1394, 76.9214),
]

CRIME_TYPE_WEIGHTS = {
    CrimeType.THEFT: 0.25,
    CrimeType.BURGLARY: 0.25,
    CrimeType.FRAUD: 0.15,
    CrimeType.CYBERCRIME: 0.15,
    CrimeType.ASSAULT: 0.12,
    CrimeType.DRUG_TRAFFICKING: 0.08,
}

MODUS_OPERANDI = {
    CrimeType.THEFT: ["pickpocketing", "chain snatching", "shop lifting", "vehicle theft"],
    CrimeType.BURGLARY: ["house break-in via window", "lock breaking", "night-time break-in", "servant-assisted entry"],
    CrimeType.FRAUD: ["fake investment scheme", "loan fraud", "identity theft", "document forgery"],
    CrimeType.CYBERCRIME: ["phishing", "OTP fraud", "online shopping scam", "SIM swap fraud"],
    CrimeType.ASSAULT: ["physical altercation", "armed assault", "domestic dispute"],
    CrimeType.DRUG_TRAFFICKING: ["small-quantity peddling", "courier transport", "cultivation"],
}

OCCUPATIONS = [
    "Shopkeeper", "Driver", "Software Engineer", "Farmer", "Student",
    "Teacher", "Electrician", "Auto Mechanic", "Clerk", "Unemployed",
    "Vendor", "Plumber", "Accountant", "Security Guard",
]

BANKS = ["State Bank of India", "Canara Bank", "HDFC Bank", "ICICI Bank", "Karnataka Bank", "Union Bank of India"]

REFERENCE_DATE = datetime(2026, 6, 1)
TWO_YEARS = 730

FESTIVAL_MONTHS = {9, 10, 11}  # Sep-Nov: Dasara / Diwali season


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_date_within(days_back, months_filter=None):
    """Return a random datetime within `days_back` days of REFERENCE_DATE,
    optionally restricted to a set of allowed months (1-12)."""
    if months_filter:
        for _ in range(50):  # retry until a matching month is hit
            d = REFERENCE_DATE - timedelta(days=random.randint(0, days_back))
            if d.month in months_filter:
                return d
        # fallback: force into a festival month of a random year offset
        year_offset = random.choice([0, 1, 2])
        month = random.choice(list(months_filter))
        day = random.randint(1, 28)
        return datetime(REFERENCE_DATE.year - year_offset, month, day)
    return REFERENCE_DATE - timedelta(days=random.randint(0, days_back))


def name_variants(full_name):
    """Generate 2-3 plausible name variants for entity resolution scenarios."""
    parts = full_name.split()
    if len(parts) < 2:
        return [full_name]
    first, last = parts[0], parts[-1]
    variants = {
        f"{first[0]} {last}",        # "R Kumar"
        f"{first[0]}. {last}",       # "R. Kumar"
        f"{first} {last[0]}",        # "Ravi K"
    }
    return list(variants)


# ---------------------------------------------------------------------------
# Generation steps
# ---------------------------------------------------------------------------

def generate_locations(session):
    locations = []
    for name, district, lat, lon in KARNATAKA_LOCATIONS:
        loc = Location(name=name, district=district, state="Karnataka", latitude=lat, longitude=lon)
        locations.append(loc)
    session.add_all(locations)
    session.flush()
    return locations


def generate_persons(session, locations, n_persons, alias_fraction=0.3):
    persons = []
    for _ in range(n_persons):
        gender = random.choice([Gender.MALE, Gender.FEMALE])
        name = fake.name_male() if gender == Gender.MALE else fake.name_female()
        person = Person(
            name=name,
            gender=gender,
            age=random.randint(18, 70),
            occupation=random.choice(OCCUPATIONS),
            home_location=random.choice(locations),
        )
        persons.append(person)
    session.add_all(persons)
    session.flush()

    # Aliases for a subset of persons (entity resolution material)
    aliases = []
    for person in persons:
        if random.random() < alias_fraction:
            for variant in name_variants(person.name):
                aliases.append(PersonAlias(person_id=person.id, alias_name=variant))
    session.add_all(aliases)
    session.flush()

    return persons


def generate_assets(session, persons, mule_fraction=0.0, flagged_mule_set=None):
    """Phones, vehicles, and bank accounts for each person."""
    flagged_mule_set = flagged_mule_set or set()
    phones, vehicles, accounts = [], [], []

    for person in persons:
        # Most people have exactly one phone
        if random.random() < 0.9:
            phones.append(Phone(number=fake.unique.numerify("9#########"), owner_id=person.id))

        # ~40% own a vehicle
        if random.random() < 0.4:
            plate = f"KA{random.randint(1, 60):02d} {fake.unique.bothify('??####').upper()}"
            vehicles.append(Vehicle(
                registration_number=plate,
                owner_id=person.id,
                vehicle_type=random.choice(["two-wheeler", "car", "auto-rickshaw"]),
            ))

        # ~70% have a bank account
        if random.random() < 0.7:
            accounts.append(BankAccount(
                bank=random.choice(BANKS),
                account_number=fake.unique.numerify("############"),
                owner_id=person.id,
                is_flagged_mule=person.id in flagged_mule_set,
            ))

    session.add_all(phones + vehicles + accounts)
    session.flush()
    return phones, vehicles, accounts


def generate_crimes_and_firs(session, locations, persons, n_crimes, repeat_offender_pool):
    crimes, firs, links = [], [], []
    crime_types = list(CRIME_TYPE_WEIGHTS.keys())
    crime_weights = list(CRIME_TYPE_WEIGHTS.values())

    mysuru = next(l for l in locations if l.district == "Mysuru")

    for i in range(n_crimes):
        ctype = random.choices(crime_types, weights=crime_weights, k=1)[0]

        # --- Festival-season burglary spike in Mysuru ---
        if ctype == CrimeType.BURGLARY and random.random() < 0.5:
            location = mysuru
            timestamp = random_date_within(TWO_YEARS, months_filter=FESTIVAL_MONTHS)
        else:
            location = random.choice(locations)
            timestamp = random_date_within(TWO_YEARS)

        crime = Crime(
            type=ctype,
            timestamp=timestamp,
            location=location,
            modus_operandi=random.choice(MODUS_OPERANDI[ctype]),
            description=f"{ctype.value.replace('_', ' ').title()} reported in {location.district}.",
        )
        crimes.append(crime)
        session.add(crime)
        session.flush()  # need crime.id for FIR + links

        fir = FIR(
            crime_id=crime.id,
            fir_number=f"FIR-{location.district[:3].upper()}-{REFERENCE_DATE.year}-{crime.id:05d}",
            status=random.choices(
                list(FIRStatus),
                weights=[0.25, 0.35, 0.2, 0.1, 0.1],
                k=1,
            )[0],
            investigating_officer=f"{random.choice(['SI', 'CI', 'PSI'])} {fake.last_name_male()}",
            filed_date=timestamp + timedelta(days=random.randint(0, 3)),
        )
        firs.append(fir)
        session.add(fir)

        # --- Accused: bias toward repeat-offender pool for theft/burglary ---
        n_accused = 1 if random.random() < 0.7 else 2
        if ctype in (CrimeType.THEFT, CrimeType.BURGLARY) and random.random() < 0.6:
            accused_pool_choices = random.sample(repeat_offender_pool, k=min(n_accused, len(repeat_offender_pool)))
        else:
            accused_pool_choices = random.sample(persons, k=n_accused)

        for accused in accused_pool_choices:
            raw_name = _pick_raw_name(session, accused)
            links.append(PersonCrimeLink(
                person_id=accused.id, crime_id=crime.id,
                role=PersonRole.ACCUSED, raw_name_used=raw_name,
            ))

        # --- Victim (skip for drug trafficking, which is victimless) ---
        if ctype != CrimeType.DRUG_TRAFFICKING:
            victim = random.choice(persons)
            raw_name = _pick_raw_name(session, victim)
            links.append(PersonCrimeLink(
                person_id=victim.id, crime_id=crime.id,
                role=PersonRole.VICTIM, raw_name_used=raw_name,
            ))

        # --- Occasional witness ---
        if random.random() < 0.3:
            witness = random.choice(persons)
            raw_name = _pick_raw_name(session, witness)
            links.append(PersonCrimeLink(
                person_id=witness.id, crime_id=crime.id,
                role=PersonRole.WITNESS, raw_name_used=raw_name,
            ))

    session.add_all(links)
    session.flush()
    return crimes, firs, links


_alias_cache = {}


def _pick_raw_name(session, person):
    """Return either the canonical name or a known alias for this person,
    simulating how the same individual gets recorded slightly differently
    across FIRs."""
    if person.id not in _alias_cache:
        _alias_cache[person.id] = [a.alias_name for a in person.aliases]
    aliases = _alias_cache[person.id]
    if aliases and random.random() < 0.5:
        return random.choice(aliases)
    return person.name


def generate_associations(session, persons, links):
    """Build PersonAssociation edges: co-accused pairings + a sprinkling of
    family/neighbor/business ties to give the network graph texture."""
    associations = []

    # Co-accused: persons who appear together as ACCUSED on the same crime
    by_crime = {}
    for link in links:
        if link.role == PersonRole.ACCUSED:
            by_crime.setdefault(link.crime_id, []).append(link.person_id)

    for accused_ids in by_crime.values():
        if len(accused_ids) > 1:
            for i in range(len(accused_ids)):
                for j in range(i + 1, len(accused_ids)):
                    associations.append(PersonAssociation(
                        person_a_id=accused_ids[i], person_b_id=accused_ids[j],
                        relation_type=RelationType.CO_ACCUSED, strength=0.9,
                    ))

    # Random social ties (family / neighbor / business) — sparse
    n_random_edges = max(20, len(persons) // 20)
    for _ in range(n_random_edges):
        a, b = random.sample(persons, 2)
        associations.append(PersonAssociation(
            person_a_id=a.id, person_b_id=b.id,
            relation_type=random.choice([RelationType.FAMILY, RelationType.NEIGHBOR, RelationType.BUSINESS_PARTNER, RelationType.ASSOCIATE]),
            strength=round(random.uniform(0.3, 0.8), 2),
        ))

    session.add_all(associations)
    session.flush()
    return associations


def generate_fraud_ring(session, locations, persons, ring_size=8):
    """
    Inject a money-mule fraud ring:
      - `ring_size` persons each get a flagged bank account.
      - All accounts funnel transactions into one "hub" account.
      - Ring members are linked via ASSOCIATE edges.
      - A single fraud Crime/FIR ties the hub account's owner to the ring.

    Returns the hub Person for reference/logging.
    """
    ring_members = random.sample(persons, ring_size)
    hub_person = ring_members[0]
    mule_persons = ring_members[1:]

    # Give every ring member a flagged bank account
    accounts = []
    for person in ring_members:
        accounts.append(BankAccount(
            bank=random.choice(BANKS),
            account_number=fake.unique.numerify("############"),
            owner_id=person.id,
            is_flagged_mule=True,
        ))
    session.add_all(accounts)
    session.flush()

    hub_account = accounts[0]
    mule_accounts = accounts[1:]

    # Fan-in transactions: each mule sends several small/medium transfers to the hub
    transactions = []
    for mule_acc in mule_accounts:
        for _ in range(random.randint(3, 6)):
            transactions.append(Transaction(
                amount=round(random.uniform(5000, 45000), 2),
                timestamp=random_date_within(180),
                sender_account_id=mule_acc.id,
                receiver_account_id=hub_account.id,
                is_suspicious=True,
            ))
    session.add_all(transactions)

    # Associate the ring members with each other and with the hub
    associations = []
    for mule in mule_persons:
        associations.append(PersonAssociation(
            person_a_id=hub_person.id, person_b_id=mule.id,
            relation_type=RelationType.ASSOCIATE, strength=0.85,
        ))
    session.add_all(associations)

    # Tie it to a fraud crime/FIR
    location = random.choice(locations)
    crime = Crime(
        type=CrimeType.FRAUD,
        timestamp=random_date_within(180),
        location=location,
        modus_operandi="money mule network / fan-in fund transfers",
        description="Large-scale financial fraud involving multiple mule accounts funneling funds to a central account.",
    )
    session.add(crime)
    session.flush()

    fir = FIR(
        crime_id=crime.id,
        fir_number=f"FIR-{location.district[:3].upper()}-{REFERENCE_DATE.year}-{crime.id:05d}",
        status=FIRStatus.UNDER_INVESTIGATION,
        investigating_officer=f"CI {fake.last_name_male()}",
        filed_date=crime.timestamp + timedelta(days=1),
    )
    session.add(fir)

    link = PersonCrimeLink(
        person_id=hub_person.id, crime_id=crime.id,
        role=PersonRole.ACCUSED, raw_name_used=hub_person.name,
    )
    session.add(link)
    session.flush()

    return hub_person


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate SHERLOCK synthetic dataset")
    parser.add_argument("--persons", type=int, default=500, help="Number of persons to generate")
    parser.add_argument("--crimes", type=int, default=1000, help="Number of crimes to generate")
    parser.add_argument("--ring-size", type=int, default=8, help="Size of the injected money-mule ring")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)
    Faker.seed(args.seed)

    if args.reset:
        print("Dropping and recreating all tables...")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        print(f"Generating {len(KARNATAKA_LOCATIONS)} locations...")
        locations = generate_locations(session)

        print(f"Generating {args.persons} persons (+ aliases)...")
        persons = generate_persons(session, locations, args.persons)

        print("Generating phones, vehicles, bank accounts...")
        generate_assets(session, persons)

        # Repeat offender pool: ~5% of persons
        pool_size = max(5, args.persons // 20)
        repeat_offender_pool = random.sample(persons, pool_size)
        print(f"Designated {pool_size} persons as the repeat-offender pool.")

        print(f"Generating {args.crimes} crimes + FIRs + person links...")
        crimes, firs, links = generate_crimes_and_firs(session, locations, persons, args.crimes, repeat_offender_pool)

        print("Generating person associations (co-accused + social ties)...")
        generate_associations(session, persons, links)

        print(f"Injecting money-mule fraud ring (size={args.ring_size})...")
        hub = generate_fraud_ring(session, locations, persons, args.ring_size)
        print(f"  -> Hub account owner: {hub.name} (person_id={hub.id})")

        session.commit()
        print("\nDone. Summary:")
        print(f"  Locations:    {len(locations)}")
        print(f"  Persons:      {len(persons)}")
        print(f"  Crimes:       {len(crimes)}")
        print(f"  FIRs:         {len(firs)}")
        print(f"  Person links: {len(links)}")
        print(f"  Repeat-offender pool size: {pool_size}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
