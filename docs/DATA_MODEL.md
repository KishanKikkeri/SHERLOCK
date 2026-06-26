# SHERLOCK — Data Model

## Entity Overview

SHERLOCK's data model mirrors the real-world entities present in Indian police records (FIRs, accused records, location data) extended with financial entities for money-trail analysis.

```
Person ──── PersonAlias        (name resolution material)
  │
  ├── PersonCrimeLink ─── Crime ─── FIR
  │        (role: accused/victim/witness)    │
  │                                         └── Location
  ├── Phone
  ├── Vehicle
  ├── BankAccount ─── Transaction ─── BankAccount
  │
  └── PersonAssociation ─── Person
```

---

## Core Entities

### Person

The canonical identity of any individual in the system.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | Canonical identifier |
| `name` | String | Canonical / preferred full name |
| `gender` | Enum(male/female/other) | Gender |
| `age` | Integer | Age at time of record creation |
| `occupation` | String | Occupation |
| `home_location_id` | FK → Location | Home district |

**Design note:** `name` is the canonical form. All name variants (aliases, abbreviations) are in `PersonAlias`. Crime links reference a person's `id` but record `raw_name_used` — the name as it literally appeared on the FIR — which may be an alias. This structure supports the Entity Resolution Agent.

---

### PersonAlias

Ground-truth name variants for a canonical Person.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `person_id` | FK → Person | Canonical person |
| `alias_name` | String | e.g. "R Kumar", "R. Kumar", "Ravi K" |

**Design note:** This table is NOT visible to the Entity Resolution Agent. It is used to (a) seed `PersonCrimeLink.raw_name_used` with realistic variants and (b) score resolution accuracy against ground truth.

---

### Location

A named place within Karnataka.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `name` | String | e.g. "Mysuru City" |
| `district` | String | e.g. "Mysuru" |
| `state` | String | Default: "Karnataka" |
| `latitude` | Float | WGS84 latitude |
| `longitude` | Float | WGS84 longitude |

---

### Crime

A single criminal incident.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `type` | Enum | theft / burglary / fraud / cybercrime / assault / drug_trafficking |
| `timestamp` | DateTime | Date and time of incident |
| `location_id` | FK → Location | Where it occurred |
| `modus_operandi` | String | Method used (e.g. "house break-in via window") |
| `description` | Text | Free text description |

---

### FIR

First Information Report — the official police record for a crime.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `crime_id` | FK → Crime (unique) | One FIR per crime |
| `fir_number` | String (unique) | e.g. "FIR-MYS-2026-00042" |
| `status` | Enum | open / under_investigation / chargesheet_filed / closed / convicted |
| `investigating_officer` | String | Name and rank |
| `filed_date` | DateTime | When the FIR was registered |

---

### PersonCrimeLink

Many-to-many link between Person and Crime, with role.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `person_id` | FK → Person | The person |
| `crime_id` | FK → Crime | The crime |
| `role` | Enum(accused/victim/witness) | Role in this crime |
| `raw_name_used` | String | Name as recorded on this specific FIR (may be alias) |

**Design note:** `raw_name_used` is the field that makes Entity Resolution non-trivial. The same person (person_id=42) may appear as "Ravi Kumar" on one FIR and "R. Kumar" on another. The graph is built using `person_id` (resolved), but `raw_name_used` is preserved for audit and for training/scoring the Entity Resolution Agent.

---

### Vehicle

A registered vehicle owned by a person.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `registration_number` | String (unique) | e.g. "KA51 AB1234" |
| `owner_id` | FK → Person | Registered owner |
| `vehicle_type` | String | car / two-wheeler / auto-rickshaw |

---

### Phone

A mobile number registered to a person.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `number` | String (unique) | 10-digit mobile number |
| `owner_id` | FK → Person | Registered owner |

---

### BankAccount

A bank account owned by a person.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `bank` | String | Bank name |
| `account_number` | String (unique) | Account number |
| `owner_id` | FK → Person | Account holder |
| `is_flagged_mule` | Boolean | True if identified as a money-mule account |

---

### Transaction

A financial transaction between two bank accounts.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `amount` | Float | Transaction amount (INR) |
| `timestamp` | DateTime | Transaction date/time |
| `sender_account_id` | FK → BankAccount | Sending account |
| `receiver_account_id` | FK → BankAccount | Receiving account |
| `is_suspicious` | Boolean | True if flagged as suspicious |

---

### PersonAssociation

A direct social or criminal association between two persons.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer PK | — |
| `person_a_id` | FK → Person | First person |
| `person_b_id` | FK → Person | Second person |
| `relation_type` | Enum | family / associate / co_accused / neighbor / business_partner |
| `strength` | Float (0–1) | Relationship strength (used as graph edge weight) |

**Design note:** The graph also derives `PERSON_LINKED_TO_PERSON` edges from co-occurrence on the same crime (via `PersonCrimeLink`). `PersonAssociation` represents explicitly-known social/criminal ties, while `PERSON_LINKED_TO_PERSON` is inferred from shared crime participation.

---

## Enumerations

### CrimeType
`theft` · `burglary` · `fraud` · `cybercrime` · `assault` · `drug_trafficking`

### FIRStatus
`open` · `under_investigation` · `chargesheet_filed` · `closed` · `convicted`

### PersonRole
`accused` · `victim` · `witness`

### RelationType
`family` · `associate` · `co_accused` · `neighbor` · `business_partner`

### Gender
`male` · `female` · `other`

---

## Synthetic Dataset Design

The generator (`backend/datasets/generate_synthetic_data.py`) deliberately injects four patterns to give agents meaningful signals:

| Pattern | How injected | Why |
|---------|-------------|-----|
| Festival-season burglary spike | Mysuru burglaries biased to months 9, 10, 11 | Pattern Agent needs real seasonal signal |
| Repeat offender pool | 5% of persons over-weighted as accused on theft/burglary | Network Agent needs outliers to surface |
| Name aliasing | 30% of persons get 2–3 aliases used in crime records | Entity Resolution needs real ambiguity |
| Money-mule ring | 8 persons with flagged accounts + fan-in transactions | Financial Agent needs a genuine ring to detect |

Reproducible with `--seed 42` (default). Scale up with `--persons 5000 --crimes 10000` for a fuller demo dataset.
