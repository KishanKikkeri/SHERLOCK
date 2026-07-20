// Shapes verified against backend/api/*.py and backend/database/models/*.py
// — see docs/stage-f/02-API-CONTRACTS.md. Keep this file and that doc in sync.

export type Role =
  | 'administrator'
  | 'supervisor'
  | 'investigator'
  | 'analyst'
  | 'policy_maker'
  | 'read_only'

export type Permission =
  | 'view_case'
  | 'participate_case'
  | 'manage_case'
  | 'decide_review'
  | 'use_voice'
  | 'run_investigation'
  | 'export_pdf'
  | 'view_audit'
  | 'manage_users'
  | 'administer_system'

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_at: string
}

export interface UserOut {
  id: number
  username: string
  email: string | null
  full_name: string | null
  officer_id: number | null
  is_active: boolean
  roles: Role[]
}

export type SessionStatus = 'open' | 'closed' | 'reopened' | 'archived'
export type SessionPriority = 'low' | 'medium' | 'high' | 'critical'

export interface InvestigationSession {
  id: number
  session_code: string
  title: string
  fir_id: number | null
  status: SessionStatus
  priority: SessionPriority
  opened_by_officer_id: number | null
  owner_officer_id: number | null
  opened_at: string
  closed_at: string | null
  reopened_at: string | null
  archived_at: string | null
  updated_at: string
  notes: string | null
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'down'
  system: string
  components: Record<string, string>
}

export interface MetricsResponse {
  persons: number
  crimes: number
  firs: number
  relationships: number
  repeat_offenders: number
  fraud_network_size: number
  suspicious_transactions: number
}

export interface NotificationOut {
  id: number
  officer_id: number
  session_id: number | null
  kind: string
  body: string
  read: boolean
  created_at: string
}

export interface ActivityFeedItem {
  id: number
  session_id: number
  actor_officer_id: number | null
  action: string
  detail: string | null
  created_at: string
}

export interface DiscussionRecord {
  id: number
  session_id: number
  turn_index: number
  query: string
  opinions: unknown
  disagreements: unknown
  consensus: string | null
  created_at: string
}

export interface AuditLogEntry {
  id: number
  user_id: number | null
  username: string | null
  action: string
  target: string | null
  success: boolean
  ip_address: string | null
  user_agent: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface RetentionPolicy {
  investigation_sessions_days: number
  conversation_turns_days: number
  audit_log_days: number
  deletion_mode: string
}

// The 16 real node labels from backend/graph/schema.py NODE_LABELS.
// Do not add "Investigation" or "Evidence" here — see
// docs/stage-f/01-DESIGN-SYSTEM.md's correction note.
export type GraphNodeType =
  | 'Person'
  | 'Crime'
  | 'FIR'
  | 'Location'
  | 'Vehicle'
  | 'Phone'
  | 'BankAccount'
  | 'Transaction'
  | 'Accused'
  | 'Victim'
  | 'Witness'
  | 'Officer'
  | 'Court'
  | 'Property'
  | 'Weapon'
  | 'Organization'

// The 20 real relationship types from backend/graph/schema.py RELATIONSHIP_TYPES.
export type GraphEdgeType =
  | 'PERSON_COMMITTED_CRIME'
  | 'PERSON_INVOLVED_IN_FIR'
  | 'PERSON_ASSOCIATED_WITH'
  | 'PERSON_LINKED_TO_PERSON'
  | 'PERSON_OWNS_PHONE'
  | 'PERSON_OWNS_ACCOUNT'
  | 'PERSON_OWNS_VEHICLE'
  | 'CRIME_OCCURRED_AT'
  | 'CRIME_LINKED_TO_FIR'
  | 'ACCOUNT_SENT_TRANSACTION'
  | 'TRANSACTION_TO_ACCOUNT'
  | 'ACCUSED_IN'
  | 'VICTIM_IN'
  | 'WITNESS_OF'
  | 'INVESTIGATED_BY'
  | 'ARRESTED_IN'
  | 'CHARGESHEETED_IN'
  | 'SEIZED_AT'
  | 'RECOVERED_FROM'
  | 'CALLS'
  | 'USES'

export interface GraphNodeData {
  id: number
  [field: string]: unknown
}

export interface RawGraphNode {
  id: string
  label: string
  type: GraphNodeType
  data: GraphNodeData
}

export interface RawGraphEdge {
  source: string
  target: string
  type: GraphEdgeType
}

export interface GraphResponse {
  nodes: RawGraphNode[]
  edges: RawGraphEdge[]
  center?: string
}

export interface ApiError {
  status: number
  detail: string
}
