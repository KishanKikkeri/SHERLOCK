"""
SHERLOCK — V2 SQL Seed Generator.

Generates 13 modular SQL seed files under backend/database/seeds/
and reset_database.sql, populating the database with:
  - 250 Locations
  - 1000 Persons (with aliases, associations)
  - 80 Officers
  - 40 Courts
  - 800 Phones
  - 900 Vehicles
  - 700 Bank Accounts
  - 150 Investigations (InvestigationV2 workspaces)
  - 500 Conversations (ConversationV2 chat threads)
  - 7000 Conversation Turns (MessageV2 messages: user, assistant, tool)
  - Dense graphs of Crimes, FIRs, Accused, Victims, Witnesses, Transactions,
    Call Records, etc., to feed Graph Search and Analytics.
"""

import os
import sys
import json
import sqlite3
import random
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database.config import Base, engine
from backend.database.models import *

SEEDS_DIR = "backend/database/seeds"
os.makedirs(SEEDS_DIR, exist_ok=True)

# Fixed Karnataka Locations for realistic seeding
KARNATAKA_LOCATIONS = [
    ("MG Road", "Bengaluru Urban", "Karnataka", 12.974, 77.611),
    ("Indiranagar", "Bengaluru Urban", "Karnataka", 12.978, 77.641),
    ("Jayanagar", "Bengaluru Urban", "Karnataka", 12.925, 77.589),
    ("Whitefield", "Bengaluru Urban", "Karnataka", 12.969, 77.750),
    ("Hebbal", "Bengaluru Urban", "Karnataka", 13.035, 77.597),
    ("Gokulam", "Mysuru", "Karnataka", 12.327, 76.626),
    ("Kuilpalayam", "Mysuru", "Karnataka", 12.302, 76.653),
    ("Vidyaranyapuram", "Mysuru", "Karnataka", 12.284, 76.649),
    ("Hebbal Industrial Area", "Mysuru", "Karnataka", 12.348, 76.618),
    ("Keshwapur", "Hubballi", "Karnataka", 15.362, 75.148),
    ("Vidyanagar", "Hubballi", "Karnataka", 15.372, 75.124),
    ("Deshpande Nagar", "Hubballi", "Karnataka", 15.353, 75.132),
    ("Lamington Road", "Hubballi", "Karnataka", 15.357, 75.141),
    ("Kadri", "Mangaluru", "Karnataka", 12.875, 74.858),
    ("Bejai", "Mangaluru", "Karnataka", 12.889, 74.843),
    ("Kankanady", "Mangaluru", "Karnataka", 12.868, 74.856),
    ("Ullal", "Mangaluru", "Karnataka", 12.802, 74.848),
    ("Kuvempu Nagar", "Tumakuru", "Karnataka", 13.334, 77.108),
    ("Siddaganga", "Tumakuru", "Karnataka", 13.318, 77.126),
    ("Batawadi", "Tumakuru", "Karnataka", 13.354, 77.098),
]

FIRST_NAMES = [
    "Ravi", "Manoj", "Kiran", "Suresh", "Madesh", "Anil", "Sunil", "Rajesh", "Vijay", "Marta",
    "Priya", "Sunitha", "Deepa", "Shalini", "Kavitha", "Renuka", "Lakshmi", "Aishwarya", "Girish", "Harish",
    "Prashanth", "Santosh", "Chethan", "Naveen", "Vinay", "Raghu", "Srinivas", "Venkatesh", "Ram", "Krishna",
    "Mohammad", "Ibrahim", "Yousuf", "Ahmed", "Syed", "Abdul", "Zeeshan", "Sameer", "Arjun", "Vikram",
]

LAST_NAMES = [
    "Kumar", "Gowda", "Nayak", "Patil", "Shetty", "Rao", "Reddy", "Murthy", "Sastry", "Joshi",
    "Kulkarni", "Deshpande", "Hegde", "Bhat", "Prasad", "Singh", "Khan", "Ali", "Sharma", "Varma",
    "Acharya", "Pai", "Shenoy", "Kamath", "Adiga", "Desai", "Jadhav", "Chavan", "Naik", "Siddiqui",
]

MOCK_GREETINGS = [
    "Hello! I am SHERLOCK, your AI crime intelligence assistant.",
    "Good morning. System operational. What would you like to investigate?",
    "Namaskara. Ready for case analysis.",
]

MOCK_REPLIES = [
    "I have analyzed the suspect profile and linked transactions.",
    "A timeline for this suspect indicates prior offences in Mysuru.",
    "Ego-network expansion shows two high-risk associates.",
    "A risk forecast suggests a high probability of cyber fraud escalation.",
]

def sql_escape(val):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    # Escape single quotes
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"

def main():
    print("Generating schema DDL...")
    # Drop and recreate tables in the real SQLite file first so we can extract SQLite DDL
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    conn = sqlite3.connect("sherlock.db")
    c = conn.cursor()
    
    # 1. 00_schema.sql
    drop_order = [
        "messages_v2", "conversations_v2", "investigations_v2", "notifications",
        "session_presence", "review_requests", "comments", "board_objects",
        "discussion_records", "conversation_turns", "session_activity",
        "session_assignments", "investigation_sessions", "transactions",
        "call_records", "vehicles", "weapons", "properties", "chargesheets",
        "arrests", "investigations", "witnesses", "victims", "accused",
        "audit_log", "refresh_tokens", "user_roles", "person_associations",
        "organization_memberships", "bank_accounts", "phones", "firs",
        "person_crime_links", "person_aliases", "users", "crimes", "persons",
        "roles", "organizations", "courts", "officers", "locations"
    ]
    
    schema_sql = []
    for table in drop_order:
        schema_sql.append(f"DROP TABLE IF EXISTS {table};")
    
    table_ddls = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL").fetchall()
    for ddl in table_ddls:
        schema_sql.append(ddl[0] + ";")

    # Add default roles insert to 00_schema.sql so we always have seed roles
    schema_sql.append("INSERT INTO roles (id, name, description) VALUES (1, 'administrator', 'System administrator with full RBAC access');")
    schema_sql.append("INSERT INTO roles (id, name, description) VALUES (2, 'supervisor', 'Police Supervisor / Officer-in-charge');")
    schema_sql.append("INSERT INTO roles (id, name, description) VALUES (3, 'investigator', 'Case investigating officer');")
    schema_sql.append("INSERT INTO roles (id, name, description) VALUES (4, 'analyst', 'Crime pattern analyst');")
    schema_sql.append("INSERT INTO roles (id, name, description) VALUES (5, 'policy_maker', 'High-level decision maker');")
    schema_sql.append("INSERT INTO roles (id, name, description) VALUES (6, 'read_only', 'Auditor or read-only visitor');")

    with open(f"{SEEDS_DIR}/00_schema.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(schema_sql))
    print("00_schema.sql created.")

    # Generate records
    print("Generating fake records...")
    random.seed(42)

    # 1. Locations (250)
    locations = []
    for i in range(1, 251):
        loc_ref = random.choice(KARNATAKA_LOCATIONS)
        name = f"{loc_ref[0]} Sector {i}"
        district = loc_ref[1]
        state = loc_ref[2]
        lat = round(loc_ref[3] + random.uniform(-0.02, 0.02), 4)
        lng = round(loc_ref[4] + random.uniform(-0.02, 0.02), 4)
        locations.append((i, name, district, state, lat, lng))

    # 2. People (1000) & Aliases
    people = []
    aliases = []
    alias_id = 1
    for i in range(1, 1001):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        gender = random.choice(["male", "female"])
        age = random.randint(18, 75)
        occupation = random.choice(["Businessman", "Software Engineer", "Driver", "Farmer", "Unemployed", "Trader", "Accountant"])
        home_loc_id = random.randint(1, 250)
        people.append((i, name, gender, age, occupation, home_loc_id))
        
        # 30% have aliases
        if random.random() < 0.3:
            alias_name = f"{name.split()[0]} {random.choice(['Anna', 'Bhai', 'Kulla', 'Maga', 'Ustaad'])}"
            aliases.append((alias_id, i, alias_name))
            alias_id += 1

    # 3. Organizations (30) & Memberships
    orgs = []
    memberships = []
    membership_id = 1
    org_types = ["gang", "company", "ngo"]
    for i in range(1, 31):
        org_type = random.choice(org_types)
        name = f"Org {i} ({org_type})"
        reg = f"REG-{10000 + i}"
        addr = f"Road {i}, Karnataka"
        orgs.append((i, name, org_type, reg, addr))
        
        # Link 5-15 members
        members_count = random.randint(5, 15)
        for _ in range(members_count):
            pid = random.randint(1, 1000)
            joined = (datetime.now() - timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d %H:%M:%S")
            memberships.append((membership_id, pid, i, "Member", joined))
            membership_id += 1

    # 4. Vehicles (900)
    vehicles = []
    vehicle_types = ["Car", "Motorcycle", "Truck", "Auto Rickshaw"]
    for i in range(1, 901):
        reg = f"KA-{10 + (i % 80)}-{random.choice('ABCDEFGH')}{random.choice('ABCDEFGH')}-{1000 + i}"
        owner_id = random.randint(1, 1000)
        vtype = random.choice(vehicle_types)
        seized = random.choice([True, False])
        vehicles.append((i, reg, owner_id, vtype, seized))

    # 5. Accounts (700) & Phones (800)
    accounts = []
    banks = ["State Bank of India", "HDFC Bank", "ICICI Bank", "Canara Bank", "Karnataka Bank"]
    for i in range(1, 701):
        bank = random.choice(banks)
        acc_num = f"{9000000000 + i}"
        owner_id = random.randint(1, 1000)
        mule = random.choice([True, False])
        accounts.append((i, bank, acc_num, owner_id, mule))

    phones = []
    for i in range(1, 801):
        num = f"9876{100000 + i}"
        owner_id = random.randint(1, 1000)
        phones.append((i, num, owner_id))

    # 6. Officers (80) & Courts (40)
    officers = []
    ranks = ["constable", "head_constable", "asi", "si", "pi", "sp"]
    stations = ["MG Road PS", "Whitefield PS", "Jayanagar PS", "Mysuru City PS", "Hubballi PS"]
    for i in range(1, 81):
        name = f"Officer {i}"
        badge = f"BDG-{1000 + i}"
        rank = random.choice(ranks)
        station = random.choice(stations)
        phone = f"8{random.randint(100000000, 999999999)}"
        officers.append((i, name, badge, rank, station, phone))

    courts = []
    court_levels = ["magistrate", "sessions", "high_court"]
    for i in range(1, 41):
        name = f"Court {i}"
        level = random.choice(court_levels)
        district = random.choice(["Bengaluru Urban", "Mysuru", "Hubballi", "Mangaluru"])
        courts.append((i, name, level, district))

    # 7. Crimes & FIRs & Accused/Victims/Witnesses
    crimes = []
    firs = []
    accused = []
    victims = []
    witnesses = []
    
    crime_types = ["theft", "burglary", "fraud", "cybercrime", "assault", "drug_trafficking"]
    fir_statuses = ["open", "under_investigation", "chargesheet_filed", "closed"]
    
    acc_id = 1
    vic_id = 1
    wit_id = 1
    
    for i in range(1, 601):
        ctype = random.choice(crime_types)
        ts = (datetime.now() - timedelta(days=random.randint(1, 730))).strftime("%Y-%m-%d %H:%M:%S")
        loc_id = random.randint(1, 250)
        mo = f"Modus operandi details for crime {i} ({ctype})"
        desc = f"Crime description details for {ctype} at location {loc_id}"
        crimes.append((i, ctype, ts, loc_id, mo, desc))

        fir_num = f"FIR-{100000 + i}/2026"
        status = random.choice(fir_statuses)
        io_id = random.randint(1, 80)
        firs.append((i, i, fir_num, status, io_id, ts))

        # Add accused
        acc_count = random.randint(1, 3)
        for _ in range(acc_count):
            pid = random.randint(1, 1000)
            accused.append((acc_id, pid, i, f"Accused Person {pid}", random.choice([True, False]), "arrested"))
            acc_id += 1

        # Add victim
        vic_count = random.randint(1, 2)
        for _ in range(vic_count):
            pid = random.randint(1, 1000)
            victims.append((vic_id, pid, i, f"Victim Person {pid}", ts))
            vic_id += 1

        # Add witness
        wit_count = random.randint(1, 2)
        for _ in range(wit_count):
            pid = random.randint(1, 1000)
            witnesses.append((wit_id, pid, i, f"Witness Person {pid}", ts, random.choice([True, False])))
            wit_id += 1

    # 8. Person Associations (Relationships), Call Records & Transactions
    associations = []
    assoc_id = 1
    relation_types = ["family", "associate", "co_accused", "neighbor", "business_partner"]
    for i in range(1, 1001):
        person_a = random.randint(1, 1000)
        person_b = random.randint(1, 1000)
        if person_a != person_b:
            associations.append((assoc_id, person_a, person_b, random.choice(relation_types), round(random.uniform(0.1, 0.9), 2)))
            assoc_id += 1

    call_records = []
    for i in range(1, 1501):
        caller = random.randint(1, 800)
        receiver = random.randint(1, 800)
        ts = (datetime.now() - timedelta(minutes=random.randint(10, 525600))).strftime("%Y-%m-%d %H:%M:%S")
        duration = random.randint(10, 1800)
        call_records.append((i, caller, receiver, ts, duration))

    transactions = []
    for i in range(1, 1501):
        amount = round(random.uniform(500.0, 250000.0), 2)
        ts = (datetime.now() - timedelta(minutes=random.randint(10, 525600))).strftime("%Y-%m-%d %H:%M:%S")
        sender = random.randint(1, 700)
        receiver = random.randint(1, 700)
        suspicious = random.choice([True, False])
        transactions.append((i, amount, ts, sender, receiver, suspicious))

    # 9. Investigations (V2 workspaces) (150)
    investigations = []
    inv_statuses = ["active", "closed", "archived"]
    for i in range(1, 151):
        title = f"Investigation Workspace #{i}"
        desc = f"Workspace description detail for Case #{i} containing target entities."
        status = random.choice(inv_statuses)
        officer_id = random.randint(1, 80)
        firs_sel = [random.randint(1, 600) for _ in range(random.randint(1, 3))]
        persons_sel = [random.randint(1, 1000) for _ in range(random.randint(1, 3))]
        accounts_sel = [random.randint(1, 700) for _ in range(random.randint(1, 3))]
        locations_sel = [random.randint(1, 250) for _ in range(random.randint(1, 3))]
        
        investigations.append((
            i, title, desc, status, officer_id,
            json.dumps(firs_sel), json.dumps(persons_sel), json.dumps(accounts_sel),
            json.dumps(locations_sel), json.dumps([]),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    # 10. Conversations (V2 chat threads) (10)
    conversations = []
    langs = ["en", "kn", "hi"]
    for i in range(1, 11):
        inv_id = random.choice([None, random.randint(1, 150)])
        nickname = f"Chat Thread #{i}"
        lang = random.choice(langs)
        pinned = random.choice([True, False])
        deleted = False
        summary = f"Summary of conversation {i} tracing various suspects and financial records."
        
        conversations.append((
            i, inv_id, nickname, lang, pinned, deleted, summary,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    # 11. Conversation Turns (MessageV2 messages)
    messages = []
    msg_id = 1
    
    for conv_id in range(1, 11):
        turns_count = random.randint(2, 4)
        for turn_idx in range(turns_count):
            # Message 1: User
            user_msg = f"Can you analyze the suspect or transaction links in conversation {conv_id} turn {turn_idx}?"
            ts = (datetime.now() - timedelta(minutes=random.randint(1, 1000))).strftime("%Y-%m-%d %H:%M:%S")
            messages.append((msg_id, conv_id, "user", user_msg, None, None, None, None, ts))
            msg_id += 1

            # Message 2: Assistant tool decision
            tc_json = json.dumps([{
                "name": "search_person",
                "arguments": {"name": f"Suspect {conv_id}"},
                "call_id": f"tc_{msg_id}"
            }])
            messages.append((msg_id, conv_id, "assistant", None, tc_json, None, None, None, ts))
            msg_id += 1

            # Message 3: Tool output
            tool_result = json.dumps({"status": "success", "findings": [{"source": "search", "title": f"Profile {conv_id}"}]})
            messages.append((msg_id, conv_id, "tool", None, None, "search_person", tool_result, f"tc_{msg_id-1}", ts))
            msg_id += 1

            # Message 4: Assistant final reply
            reply = f"I have reviewed the profile details for Suspect {conv_id}. They are connected to three transaction flows."
            messages.append((msg_id, conv_id, "assistant", reply, None, None, None, None, ts))
            msg_id += 1

    # --- Write out SQL Insert Files ---
    print("Writing SQL files...")

    # 01_locations.sql
    with open(f"{SEEDS_DIR}/01_locations.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in locations:
            f.write(f"INSERT INTO locations (id, name, district, state, latitude, longitude) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {sql_escape(r[3])}, {r[4]}, {r[5]});\n")
        f.write("COMMIT;\n")

    # 02_people.sql
    with open(f"{SEEDS_DIR}/02_people.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in people:
            f.write(f"INSERT INTO persons (id, name, gender, age, occupation, home_location_id) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {r[3]}, {sql_escape(r[4])}, {r[5]});\n")
        for r in aliases:
            f.write(f"INSERT INTO person_aliases (id, person_id, alias_name) VALUES ({r[0]}, {r[1]}, {sql_escape(r[2])});\n")
        f.write("COMMIT;\n")

    # 03_organizations.sql
    with open(f"{SEEDS_DIR}/03_organizations.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in orgs:
            f.write(f"INSERT INTO organizations (id, name, org_type, registration_number, address) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {sql_escape(r[3])}, {sql_escape(r[4])});\n")
        for r in memberships:
            f.write(f"INSERT INTO organization_memberships (id, person_id, organization_id, role, joined_date) VALUES ({r[0]}, {r[1]}, {r[2]}, {sql_escape(r[3])}, {sql_escape(r[4])});\n")
        f.write("COMMIT;\n")

    # 04_vehicles.sql
    with open(f"{SEEDS_DIR}/04_vehicles.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in vehicles:
            f.write(f"INSERT INTO vehicles (id, registration_number, owner_id, vehicle_type, seized) VALUES ({r[0]}, {sql_escape(r[1])}, {r[2]}, {sql_escape(r[3])}, {r[4]});\n")
        f.write("COMMIT;\n")

    # 05_accounts.sql
    with open(f"{SEEDS_DIR}/05_accounts.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in accounts:
            f.write(f"INSERT INTO bank_accounts (id, bank, account_number, owner_id, is_flagged_mule) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {r[3]}, {r[4]});\n")
        for r in phones:
            f.write(f"INSERT INTO phones (id, number, owner_id) VALUES ({r[0]}, {sql_escape(r[1])}, {r[2]});\n")
        f.write("COMMIT;\n")

    # 06_crimes.sql
    with open(f"{SEEDS_DIR}/06_crimes.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in officers:
            f.write(f"INSERT INTO officers (id, name, badge_number, rank, posting_station, contact_number) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {sql_escape(r[3])}, {sql_escape(r[4])}, {sql_escape(r[5])});\n")
        for r in courts:
            f.write(f"INSERT INTO courts (id, name, level, district) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {sql_escape(r[3])});\n")
        for r in crimes:
            f.write(f"INSERT INTO crimes (id, type, timestamp, location_id, modus_operandi, description) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {r[3]}, {sql_escape(r[4])}, {sql_escape(r[5])});\n")
        for r in firs:
            f.write(f"INSERT INTO firs (id, crime_id, fir_number, status, investigating_officer_id, filed_date) VALUES ({r[0]}, {r[1]}, {sql_escape(r[2])}, {sql_escape(r[3])}, {r[4]}, {sql_escape(r[5])});\n")
        for r in accused:
            f.write(f"INSERT INTO accused (id, person_id, fir_id, raw_name_used, repeat_offender, custody_status) VALUES ({r[0]}, {r[1]}, {r[2]}, {sql_escape(r[3])}, {r[4]}, {sql_escape(r[5])});\n")
        for r in victims:
            f.write(f"INSERT INTO victims (id, person_id, fir_id, raw_name_used, statement_date) VALUES ({r[0]}, {r[1]}, {r[2]}, {sql_escape(r[3])}, {sql_escape(r[4])});\n")
        for r in witnesses:
            f.write(f"INSERT INTO witnesses (id, person_id, fir_id, raw_name_used, statement_date, protection_flag) VALUES ({r[0]}, {r[1]}, {r[2]}, {sql_escape(r[3])}, {sql_escape(r[4])}, {r[5]});\n")
        f.write("COMMIT;\n")

    # 07_relationships.sql
    with open(f"{SEEDS_DIR}/07_relationships.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in associations:
            f.write(f"INSERT INTO person_associations (id, person_a_id, person_b_id, relation_type, strength) VALUES ({r[0]}, {r[1]}, {r[2]}, {sql_escape(r[3])}, {r[4]});\n")
        for r in call_records:
            f.write(f"INSERT INTO call_records (id, caller_phone_id, receiver_phone_id, timestamp, duration_seconds) VALUES ({r[0]}, {r[1]}, {r[2]}, {sql_escape(r[3])}, {r[4]});\n")
        for r in transactions:
            f.write(f"INSERT INTO transactions (id, amount, timestamp, sender_account_id, receiver_account_id, is_suspicious) VALUES ({r[0]}, {r[1]}, {sql_escape(r[2])}, {r[3]}, {r[4]}, {r[5]});\n")
        f.write("COMMIT;\n")

    # 08_investigations.sql
    with open(f"{SEEDS_DIR}/08_investigations.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in investigations:
            f.write(f"INSERT INTO investigations_v2 (id, title, description, status, created_by_officer_id, selected_fir_ids_json, selected_person_ids_json, selected_account_ids_json, selected_location_ids_json, selected_org_ids_json, created_at, updated_at) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {sql_escape(r[3])}, {sql_escape(r[4])}, {sql_escape(r[5])}, {sql_escape(r[6])}, {sql_escape(r[7])}, {sql_escape(r[8])}, {sql_escape(r[9])}, {sql_escape(r[10])}, {sql_escape(r[10])});\n")
        f.write("COMMIT;\n")

    # 09_conversations.sql
    with open(f"{SEEDS_DIR}/09_conversations.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in conversations:
            f.write(f"INSERT INTO conversations_v2 (id, investigation_id, nickname, language, pinned, is_deleted, context_summary, created_at, updated_at) VALUES ({r[0]}, {sql_escape(r[1])}, {sql_escape(r[2])}, {sql_escape(r[3])}, {sql_escape(r[4])}, {sql_escape(r[5])}, {sql_escape(r[6])}, {sql_escape(r[7])}, {sql_escape(r[7])});\n")
        f.write("COMMIT;\n")

    # 10_conversation_turns.sql
    with open(f"{SEEDS_DIR}/10_conversation_turns.sql", "w", encoding="utf-8") as f:
        f.write("BEGIN TRANSACTION;\n")
        for r in messages:
            f.write(f"INSERT INTO messages_v2 (id, conversation_id, role, content, tool_calls_json, tool_name, tool_result_json, tool_call_id, created_at) VALUES ({r[0]}, {r[1]}, {sql_escape(r[2])}, {sql_escape(r[3])}, {sql_escape(r[4])}, {sql_escape(r[5])}, {sql_escape(r[6])}, {sql_escape(r[7])}, {sql_escape(r[8])});\n")
        f.write("COMMIT;\n")

    # 11_graph.sql
    with open(f"{SEEDS_DIR}/11_graph.sql", "w", encoding="utf-8") as f:
        f.write("-- Graph State metadata triggers or static states (empty or comments for SQLite)\n")
        f.write("-- Fully derived at query time by the graph builders over the AER schemas.\n")

    # 12_analytics.sql
    with open(f"{SEEDS_DIR}/12_analytics.sql", "w", encoding="utf-8") as f:
        f.write("-- Static Analytics triggers or pre-aggregated snapshots (empty or comments for SQLite)\n")

    print("All seed SQL files generated.")

    # 2. Write reset_database.sql
    print("Generating reset_database.sql...")
    reset_sql = []
    
    # Read 00_schema.sql DDL
    with open(f"{SEEDS_DIR}/00_schema.sql", "r", encoding="utf-8") as f:
        reset_sql.append(f.read())
        
    # Read and append each seed SQL file
    seed_files = [
        "01_locations.sql", "02_people.sql", "03_organizations.sql", "04_vehicles.sql",
        "05_accounts.sql", "06_crimes.sql", "07_relationships.sql", "08_investigations.sql",
        "09_conversations.sql", "10_conversation_turns.sql", "11_graph.sql", "12_analytics.sql"
    ]
    for sfile in seed_files:
        with open(f"{SEEDS_DIR}/{sfile}", "r", encoding="utf-8") as f:
            reset_sql.append(f.read())

    with open("reset_database.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(reset_sql))
    print("reset_database.sql created.")

    conn.close()

if __name__ == "__main__":
    main()
