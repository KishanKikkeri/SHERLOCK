# SHERLOCK — Crime Intelligence Graph Schema

The Crime Intelligence Graph is SHERLOCK's core intelligence layer. It is a derived view of the PostgreSQL source data, optimised for relationship discovery, network analysis, and shortest-path queries.

---

## Node Labels (8)

| Label | Description | Key Properties |
|-------|-------------|---------------|
| `Person` | Individual (suspect, victim, witness, or associate) | `id`, `name`, `gender`, `age`, `occupation` |
| `Crime` | A criminal incident | `id`, `type`, `timestamp`, `modus_operandi` |
| `FIR` | First Information Report | `id`, `fir_number`, `status`, `investigating_officer` |
| `Location` | A named place in Karnataka | `id`, `name`, `district`, `latitude`, `longitude` |
| `Vehicle` | A registered vehicle | `id`, `registration_number`, `vehicle_type` |
| `Phone` | A mobile phone number | `id`, `number` |
| `BankAccount` | A bank account | `id`, `account_number`, `bank`, `is_flagged_mule` |
| `Transaction` | A financial transaction | `id`, `amount`, `timestamp`, `is_suspicious` |

---

## Relationship Types (11)

### Person → Crime

```
(Person)-[:PERSON_COMMITTED_CRIME {raw_name_used}]->(Crime)
```
Links an accused person to a crime. `raw_name_used` is the name as it appeared on the FIR (may be an alias). Used by the Network Analysis Agent to count PERSON_COMMITTED_CRIME edges per person (repeat offender detection).

---

### Person → FIR

```
(Person)-[:PERSON_INVOLVED_IN_FIR {role, raw_name_used}]->(FIR)
```
Links a victim or witness to a FIR. `role` is "victim" or "witness". Used to map non-accused persons to cases.

---

### Person ↔ Person (Association)

```
(Person)-[:PERSON_ASSOCIATED_WITH {relation_type, strength}]-(Person)
```
Explicit social/criminal association (from `PersonAssociation` table). `relation_type` is one of: family, associate, co_accused, neighbor, business_partner. `strength` is 0–1.

---

### Person ↔ Person (Co-occurrence)

```
(Person)-[:PERSON_LINKED_TO_PERSON {via_crime_id}]-(Person)
```
Inferred association — any two persons appearing on the same crime record (as accused, victim, or witness). `via_crime_id` identifies the linking crime. This edge is derived, not from an explicit association record.

---

### Person → Phone

```
(Person)-[:PERSON_OWNS_PHONE]->(Phone)
```
Asset ownership. Used to discover shared-phone connections between suspects.

---

### Person → BankAccount

```
(Person)-[:PERSON_OWNS_ACCOUNT]->(BankAccount)
```
Asset ownership. Used to trace financial networks from persons to accounts.

---

### Person → Vehicle

```
(Person)-[:PERSON_OWNS_VEHICLE]->(Vehicle)
```
Asset ownership.

---

### Crime → Location

```
(Crime)-[:CRIME_OCCURRED_AT]->(Location)
```
Geographic link. Used by the Pattern Agent for district/month clustering.

---

### Crime → FIR

```
(Crime)-[:CRIME_LINKED_TO_FIR]->(FIR)
```
The official police record for this crime.

---

### BankAccount → Transaction

```
(BankAccount)-[:ACCOUNT_SENT_TRANSACTION]->(Transaction)
```
The sending side of a financial transaction.

---

### Transaction → BankAccount

```
(Transaction)-[:TRANSACTION_TO_ACCOUNT]->(BankAccount)
```
The receiving side. Combined with ACCOUNT_SENT_TRANSACTION, the full transaction path is:

```
(Sender:BankAccount)-[:ACCOUNT_SENT_TRANSACTION]->(t:Transaction)-[:TRANSACTION_TO_ACCOUNT]->(Receiver:BankAccount)
```

---

## Traversal Patterns

### Repeat Offender Detection

Find persons with the most PERSON_COMMITTED_CRIME edges (NetworkX):
```python
crime_count = sum(
    1 for _, _, edata in G.out_edges(node, data=True)
    if edata["type"] == "PERSON_COMMITTED_CRIME"
)
```

Cypher equivalent:
```cypher
MATCH (p:Person)-[:PERSON_COMMITTED_CRIME]->(c:Crime)
WITH p, count(c) AS crime_count
WHERE crime_count >= $min_crimes
RETURN p.id, p.name, crime_count
ORDER BY crime_count DESC
```

---

### Associate Network

Find all persons connected to a given person:
```cypher
MATCH (p:Person {id: $person_id})-[r:PERSON_ASSOCIATED_WITH|PERSON_LINKED_TO_PERSON]-(a:Person)
RETURN a.id, a.name, type(r) AS edge_type, r.relation_type, r.strength
ORDER BY r.strength IS NULL, r.strength DESC
```

---

### Financial Trail (Money Mule Ring)

Trace all transactions into a hub account:
```cypher
MATCH (s:BankAccount)-[:ACCOUNT_SENT_TRANSACTION]->(t:Transaction)
      -[:TRANSACTION_TO_ACCOUNT]->(hub:BankAccount {id: $account_id})
OPTIONAL MATCH (owner:Person)-[:PERSON_OWNS_ACCOUNT]->(s)
RETURN 'received' AS direction, t.id, t.amount, t.is_suspicious,
       s.id AS sender_account, owner.name AS sender_owner
ORDER BY t.timestamp DESC
```

---

### Crime Hotspot Clustering

```cypher
MATCH (c:Crime)-[:CRIME_OCCURRED_AT]->(l:Location)
WHERE $crime_type IS NULL OR c.type = $crime_type
WITH l.district AS district, c.type AS crime_type,
     toInteger(substring(c.timestamp, 5, 2)) AS month,
     count(c) AS count
RETURN district, crime_type, month, count
ORDER BY count DESC
```

---

### Shortest Path (Connection Discovery)

```cypher
MATCH path = shortestPath(
    (a:Person {id: $person_a_id})-[*..6]-(b:Person {id: $person_b_id})
)
RETURN path
```

This is the "demo gold" query — finds hidden connections through any combination of entity types in milliseconds.

Example discovered path:
```
Person: Ravi Kumar
  --[PERSON_LINKED_TO_PERSON via_crime_id=42]-->
Person: Amit Sharma
  --[PERSON_OWNS_ACCOUNT]-->
BankAccount: SBI 4429...
  --[ACCOUNT_SENT_TRANSACTION]-->
Transaction: ₹22,000 (suspicious)
  --[TRANSACTION_TO_ACCOUNT]-->
BankAccount: HDFC 8821... (is_flagged_mule=true)
  --[PERSON_OWNS_ACCOUNT]-->
Person: Unnati Narayanan (hub of fraud ring)
```

---

## Neo4j Uniqueness Constraints

Applied before any data is loaded. Ensures MERGE operations are safe and idempotent.

```cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Person)      REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Crime)       REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:FIR)         REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Location)    REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Vehicle)     REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Phone)       REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:BankAccount) REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Transaction) REQUIRE n.id IS UNIQUE
```

---

## Dataset Statistics (500-person synthetic dataset)

| Metric | Value |
|--------|-------|
| Total nodes | ~2,000 |
| Total relationships | 10,454 |
| PERSON_COMMITTED_CRIME | ~1,400 |
| PERSON_INVOLVED_IN_FIR | ~800 |
| PERSON_LINKED_TO_PERSON | ~4,800 |
| PERSON_ASSOCIATED_WITH | ~550 |
| PERSON_OWNS_PHONE / ACCOUNT / VEHICLE | ~1,200 |
| CRIME_OCCURRED_AT | 1,001 |
| CRIME_LINKED_TO_FIR | 1,001 |
| ACCOUNT_SENT / TRANSACTION_TO | ~600 |

---

## GraphIntelligenceService Abstraction

All agents call through `backend/graph/service.py` — they never write Cypher or import NetworkX:

```python
service = get_graph_service(backend="networkx", session=session)
# or
service = get_graph_service(backend="neo4j")

offenders = service.find_repeat_offenders(min_crimes=2, limit=10)
associates = service.find_associates(person_id=42, limit=20)
network    = service.find_financial_network(account_id=7, max_hops=1)
clusters   = service.find_location_clusters(crime_type="burglary", top_n=10)
path       = service.find_connection(person_a_id=42, person_b_id=213)
```

Both backends (`service_networkx.py` and `service_neo4j.py`) implement this interface identically — the output format is the same regardless of which backend runs.
