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

export interface ApiError {
  status: number
  detail: string
}
