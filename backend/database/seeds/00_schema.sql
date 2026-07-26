DROP TABLE IF EXISTS messages_v2;
DROP TABLE IF EXISTS conversations_v2;
DROP TABLE IF EXISTS investigations_v2;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS session_presence;
DROP TABLE IF EXISTS review_requests;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS board_objects;
DROP TABLE IF EXISTS discussion_records;
DROP TABLE IF EXISTS conversation_turns;
DROP TABLE IF EXISTS session_activity;
DROP TABLE IF EXISTS session_assignments;
DROP TABLE IF EXISTS investigation_sessions;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS call_records;
DROP TABLE IF EXISTS vehicles;
DROP TABLE IF EXISTS weapons;
DROP TABLE IF EXISTS properties;
DROP TABLE IF EXISTS chargesheets;
DROP TABLE IF EXISTS arrests;
DROP TABLE IF EXISTS investigations;
DROP TABLE IF EXISTS witnesses;
DROP TABLE IF EXISTS victims;
DROP TABLE IF EXISTS accused;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS refresh_tokens;
DROP TABLE IF EXISTS user_roles;
DROP TABLE IF EXISTS person_associations;
DROP TABLE IF EXISTS organization_memberships;
DROP TABLE IF EXISTS bank_accounts;
DROP TABLE IF EXISTS phones;
DROP TABLE IF EXISTS firs;
DROP TABLE IF EXISTS person_crime_links;
DROP TABLE IF EXISTS person_aliases;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS crimes;
DROP TABLE IF EXISTS persons;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS organizations;
DROP TABLE IF EXISTS courts;
DROP TABLE IF EXISTS officers;
DROP TABLE IF EXISTS locations;
CREATE TABLE locations (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	district VARCHAR NOT NULL, 
	state VARCHAR NOT NULL, 
	latitude FLOAT NOT NULL, 
	longitude FLOAT NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE officers (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	badge_number VARCHAR NOT NULL, 
	rank VARCHAR(14) NOT NULL, 
	posting_station VARCHAR, 
	contact_number VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (badge_number)
);
CREATE TABLE courts (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	level VARCHAR(10) NOT NULL, 
	district VARCHAR NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE organizations (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	org_type VARCHAR(7) NOT NULL, 
	registration_number VARCHAR, 
	address VARCHAR, 
	PRIMARY KEY (id)
);
CREATE TABLE roles (
	id INTEGER NOT NULL, 
	name VARCHAR(13) NOT NULL, 
	description VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
CREATE TABLE persons (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	gender VARCHAR(6) NOT NULL, 
	age INTEGER NOT NULL, 
	occupation VARCHAR, 
	home_location_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(home_location_id) REFERENCES locations (id)
);
CREATE TABLE crimes (
	id INTEGER NOT NULL, 
	type VARCHAR(16) NOT NULL, 
	timestamp DATETIME NOT NULL, 
	location_id INTEGER NOT NULL, 
	modus_operandi VARCHAR, 
	description TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(location_id) REFERENCES locations (id)
);
CREATE TABLE investigations_v2 (
	id INTEGER NOT NULL, 
	title VARCHAR NOT NULL, 
	description TEXT, 
	status VARCHAR(8) NOT NULL, 
	created_by_officer_id INTEGER, 
	selected_fir_ids_json TEXT, 
	selected_person_ids_json TEXT, 
	selected_account_ids_json TEXT, 
	selected_location_ids_json TEXT, 
	selected_org_ids_json TEXT, 
	graph_state_json TEXT, 
	metadata_json TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	archived_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_officer_id) REFERENCES officers (id)
);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR NOT NULL, 
	email VARCHAR, 
	password_hash VARCHAR NOT NULL, 
	officer_id INTEGER, 
	is_active BOOLEAN NOT NULL, 
	full_name VARCHAR, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	last_login_at DATETIME, 
	deactivated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(officer_id) REFERENCES officers (id)
);
CREATE TABLE person_aliases (
	id INTEGER NOT NULL, 
	person_id INTEGER NOT NULL, 
	alias_name VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id)
);
CREATE TABLE person_crime_links (
	id INTEGER NOT NULL, 
	person_id INTEGER NOT NULL, 
	crime_id INTEGER NOT NULL, 
	role VARCHAR(7) NOT NULL, 
	raw_name_used VARCHAR NOT NULL, 
	source_table VARCHAR NOT NULL, 
	source_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id), 
	FOREIGN KEY(crime_id) REFERENCES crimes (id)
);
CREATE TABLE firs (
	id INTEGER NOT NULL, 
	crime_id INTEGER NOT NULL, 
	fir_number VARCHAR NOT NULL, 
	status VARCHAR(19) NOT NULL, 
	investigating_officer_id INTEGER, 
	filed_date DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (crime_id), 
	FOREIGN KEY(crime_id) REFERENCES crimes (id), 
	UNIQUE (fir_number), 
	FOREIGN KEY(investigating_officer_id) REFERENCES officers (id)
);
CREATE TABLE phones (
	id INTEGER NOT NULL, 
	number VARCHAR NOT NULL, 
	owner_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (number), 
	FOREIGN KEY(owner_id) REFERENCES persons (id)
);
CREATE TABLE bank_accounts (
	id INTEGER NOT NULL, 
	bank VARCHAR NOT NULL, 
	account_number VARCHAR NOT NULL, 
	owner_id INTEGER NOT NULL, 
	organization_id INTEGER, 
	is_flagged_mule BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (account_number), 
	FOREIGN KEY(owner_id) REFERENCES persons (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);
CREATE TABLE organization_memberships (
	id INTEGER NOT NULL, 
	person_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	role VARCHAR, 
	joined_date DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);
CREATE TABLE person_associations (
	id INTEGER NOT NULL, 
	person_a_id INTEGER NOT NULL, 
	person_b_id INTEGER NOT NULL, 
	relation_type VARCHAR(16) NOT NULL, 
	strength FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_a_id) REFERENCES persons (id), 
	FOREIGN KEY(person_b_id) REFERENCES persons (id)
);
CREATE TABLE conversations_v2 (
	id INTEGER NOT NULL, 
	investigation_id INTEGER, 
	nickname VARCHAR NOT NULL, 
	language VARCHAR NOT NULL, 
	pinned BOOLEAN NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	archived_at DATETIME, 
	context_summary TEXT, 
	context_summary_through_msg INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(investigation_id) REFERENCES investigations_v2 (id)
);
CREATE TABLE user_roles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	granted_at DATETIME NOT NULL, 
	granted_by_user_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_role UNIQUE (user_id, role_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	FOREIGN KEY(granted_by_user_id) REFERENCES users (id)
);
CREATE TABLE refresh_tokens (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR NOT NULL, 
	issued_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	revoked_at DATETIME, 
	user_agent VARCHAR, 
	ip_address VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE audit_log (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	username VARCHAR, 
	action VARCHAR NOT NULL, 
	target VARCHAR, 
	success BOOLEAN NOT NULL, 
	ip_address VARCHAR, 
	user_agent VARCHAR, 
	metadata_json TEXT, 
	created_at DATETIME NOT NULL, 
	archived_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE accused (
	id INTEGER NOT NULL, 
	person_id INTEGER NOT NULL, 
	fir_id INTEGER NOT NULL, 
	raw_name_used VARCHAR NOT NULL, 
	repeat_offender BOOLEAN NOT NULL, 
	custody_status VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id)
);
CREATE TABLE victims (
	id INTEGER NOT NULL, 
	person_id INTEGER NOT NULL, 
	fir_id INTEGER NOT NULL, 
	raw_name_used VARCHAR NOT NULL, 
	statement_date DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id)
);
CREATE TABLE witnesses (
	id INTEGER NOT NULL, 
	person_id INTEGER NOT NULL, 
	fir_id INTEGER NOT NULL, 
	raw_name_used VARCHAR NOT NULL, 
	statement_date DATETIME, 
	protection_flag BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id)
);
CREATE TABLE investigations (
	id INTEGER NOT NULL, 
	fir_id INTEGER NOT NULL, 
	officer_id INTEGER NOT NULL, 
	start_date DATETIME NOT NULL, 
	end_date DATETIME, 
	status VARCHAR NOT NULL, 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id), 
	FOREIGN KEY(officer_id) REFERENCES officers (id)
);
CREATE TABLE arrests (
	id INTEGER NOT NULL, 
	person_id INTEGER NOT NULL, 
	fir_id INTEGER NOT NULL, 
	arresting_officer_id INTEGER, 
	location_id INTEGER, 
	arrest_date DATETIME NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES persons (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id), 
	FOREIGN KEY(arresting_officer_id) REFERENCES officers (id), 
	FOREIGN KEY(location_id) REFERENCES locations (id)
);
CREATE TABLE chargesheets (
	id INTEGER NOT NULL, 
	fir_id INTEGER NOT NULL, 
	court_id INTEGER, 
	filing_officer_id INTEGER, 
	filed_date DATETIME NOT NULL, 
	status VARCHAR(9) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id), 
	FOREIGN KEY(court_id) REFERENCES courts (id), 
	FOREIGN KEY(filing_officer_id) REFERENCES officers (id)
);
CREATE TABLE properties (
	id INTEGER NOT NULL, 
	fir_id INTEGER NOT NULL, 
	description VARCHAR NOT NULL, 
	category VARCHAR, 
	estimated_value FLOAT, 
	status VARCHAR(10) NOT NULL, 
	seized_location_id INTEGER, 
	recovered_from_person_id INTEGER, 
	organization_id INTEGER, 
	custodian_officer_id INTEGER, 
	seized_date DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id), 
	FOREIGN KEY(seized_location_id) REFERENCES locations (id), 
	FOREIGN KEY(recovered_from_person_id) REFERENCES persons (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(custodian_officer_id) REFERENCES officers (id)
);
CREATE TABLE weapons (
	id INTEGER NOT NULL, 
	weapon_type VARCHAR(9) NOT NULL, 
	description VARCHAR, 
	serial_number VARCHAR, 
	used_in_fir_id INTEGER, 
	recovered_from_person_id INTEGER, 
	status VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(used_in_fir_id) REFERENCES firs (id), 
	FOREIGN KEY(recovered_from_person_id) REFERENCES persons (id)
);
CREATE TABLE vehicles (
	id INTEGER NOT NULL, 
	registration_number VARCHAR NOT NULL, 
	owner_id INTEGER NOT NULL, 
	vehicle_type VARCHAR NOT NULL, 
	used_in_fir_id INTEGER, 
	seized BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (registration_number), 
	FOREIGN KEY(owner_id) REFERENCES persons (id), 
	FOREIGN KEY(used_in_fir_id) REFERENCES firs (id)
);
CREATE TABLE call_records (
	id INTEGER NOT NULL, 
	caller_phone_id INTEGER NOT NULL, 
	receiver_phone_id INTEGER NOT NULL, 
	timestamp DATETIME NOT NULL, 
	duration_seconds INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(caller_phone_id) REFERENCES phones (id), 
	FOREIGN KEY(receiver_phone_id) REFERENCES phones (id)
);
CREATE TABLE transactions (
	id INTEGER NOT NULL, 
	amount FLOAT NOT NULL, 
	timestamp DATETIME NOT NULL, 
	sender_account_id INTEGER NOT NULL, 
	receiver_account_id INTEGER NOT NULL, 
	is_suspicious BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sender_account_id) REFERENCES bank_accounts (id), 
	FOREIGN KEY(receiver_account_id) REFERENCES bank_accounts (id)
);
CREATE TABLE investigation_sessions (
	id INTEGER NOT NULL, 
	session_code VARCHAR NOT NULL, 
	fir_id INTEGER, 
	title VARCHAR NOT NULL, 
	status VARCHAR(8) NOT NULL, 
	priority VARCHAR(8) NOT NULL, 
	opened_by_officer_id INTEGER, 
	owner_officer_id INTEGER, 
	opened_at DATETIME NOT NULL, 
	closed_at DATETIME, 
	reopened_at DATETIME, 
	archived_at DATETIME, 
	updated_at DATETIME NOT NULL, 
	notes TEXT, 
	context_summary TEXT, 
	context_summary_through_turn INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(fir_id) REFERENCES firs (id), 
	FOREIGN KEY(opened_by_officer_id) REFERENCES officers (id), 
	FOREIGN KEY(owner_officer_id) REFERENCES officers (id)
);
CREATE TABLE messages_v2 (
	id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	role VARCHAR NOT NULL, 
	content TEXT, 
	tool_calls_json TEXT, 
	tool_name VARCHAR, 
	tool_result_json TEXT, 
	tool_call_id VARCHAR, 
	metadata_json TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations_v2 (id)
);
CREATE TABLE session_assignments (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	officer_id INTEGER NOT NULL, 
	role VARCHAR NOT NULL, 
	assigned_at DATETIME NOT NULL, 
	unassigned_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(officer_id) REFERENCES officers (id)
);
CREATE TABLE session_activity (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	event_type VARCHAR NOT NULL, 
	actor_officer_id INTEGER, 
	detail TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(actor_officer_id) REFERENCES officers (id)
);
CREATE TABLE conversation_turns (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	turn_index INTEGER NOT NULL, 
	raw_query TEXT NOT NULL, 
	resolved_query TEXT, 
	last_person_id INTEGER, 
	last_person_name VARCHAR, 
	last_fir_id INTEGER, 
	last_account_id INTEGER, 
	response_summary TEXT, 
	findings_json TEXT, 
	entity_mentions_json TEXT, 
	pending_clarification_json TEXT, 
	topic_reset VARCHAR, 
	archived_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(last_person_id) REFERENCES persons (id), 
	FOREIGN KEY(last_fir_id) REFERENCES firs (id), 
	FOREIGN KEY(last_account_id) REFERENCES bank_accounts (id)
);
CREATE TABLE discussion_records (
	id INTEGER NOT NULL, 
	session_id INTEGER, 
	turn_index INTEGER, 
	"query" TEXT NOT NULL, 
	opinions_json TEXT NOT NULL, 
	disagreements_json TEXT NOT NULL, 
	consensus_json TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id)
);
CREATE TABLE board_objects (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	object_type VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	payload TEXT, 
	created_by_officer_id INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(created_by_officer_id) REFERENCES officers (id)
);
CREATE TABLE comments (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	target_type VARCHAR(12) NOT NULL, 
	target_ref VARCHAR NOT NULL, 
	author_officer_id INTEGER, 
	body TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	edited_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(author_officer_id) REFERENCES officers (id)
);
CREATE TABLE review_requests (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	status VARCHAR(9) NOT NULL, 
	requested_by_officer_id INTEGER, 
	reviewer_officer_id INTEGER, 
	notes TEXT, 
	decision_notes TEXT, 
	created_at DATETIME NOT NULL, 
	decided_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(requested_by_officer_id) REFERENCES officers (id), 
	FOREIGN KEY(reviewer_officer_id) REFERENCES officers (id)
);
CREATE TABLE session_presence (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	officer_id INTEGER NOT NULL, 
	status VARCHAR(7) NOT NULL, 
	last_seen_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(officer_id) REFERENCES officers (id)
);
CREATE TABLE notifications (
	id INTEGER NOT NULL, 
	recipient_officer_id INTEGER NOT NULL, 
	notification_type VARCHAR(15) NOT NULL, 
	session_id INTEGER, 
	related_comment_id INTEGER, 
	related_review_id INTEGER, 
	message TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	read_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipient_officer_id) REFERENCES officers (id), 
	FOREIGN KEY(session_id) REFERENCES investigation_sessions (id), 
	FOREIGN KEY(related_comment_id) REFERENCES comments (id), 
	FOREIGN KEY(related_review_id) REFERENCES review_requests (id)
);
INSERT INTO roles (id, name, description) VALUES (1, 'administrator', 'System administrator with full RBAC access');
INSERT INTO roles (id, name, description) VALUES (2, 'supervisor', 'Police Supervisor / Officer-in-charge');
INSERT INTO roles (id, name, description) VALUES (3, 'investigator', 'Case investigating officer');
INSERT INTO roles (id, name, description) VALUES (4, 'analyst', 'Crime pattern analyst');
INSERT INTO roles (id, name, description) VALUES (5, 'policy_maker', 'High-level decision maker');
INSERT INTO roles (id, name, description) VALUES (6, 'read_only', 'Auditor or read-only visitor');