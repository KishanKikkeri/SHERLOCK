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
  notification_type: 'assignment' | 'mention' | 'review_request' | 'review_decision' | 'board_update'
  session_id: number | null
  message: string
  created_at: string
  read_at: string | null
}

export type ActivityFeedKind = 'session' | 'ai_conversation' | 'discussion'

export interface ActivityFeedItem {
  kind: ActivityFeedKind
  event_type: string
  actor_officer_id: number | null
  detail: string | null
  created_at: string
}

export interface PresenceEntry {
  officer_id: number
  status: 'viewing' | 'editing'
  last_seen_at: string
}

export interface AgentOpinion {
  agent_name: string
  finding_type: string
  claim: string
  confidence: number
  evidence: string[]
  validated: boolean
  missing_evidence: boolean
  source_entities: string[]
}

export interface Disagreement {
  entity_kind: string
  entity_id: number
  entity_label: string
  opinions: AgentOpinion[]
  confidence_spread: number
  explanation: string
}

export interface ConsensusResult {
  overall_confidence: number
  per_agent_confidence: Record<string, number>
  consensus_score: number
  agreement_count: number
  disagreement_count: number
  recommended_conclusion: string
  evidence_requests: string[]
}

export interface DiscussionRecord {
  id: number
  session_id: number
  turn_index: number
  query: string
  opinions: AgentOpinion[]
  disagreements: Disagreement[]
  consensus: ConsensusResult
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

export interface BoardIntelligence {
  evidence_summary: { finding_count: number; persons_referenced: number }
  suggested_links: {
    from: string
    to: string
    label: string | null
    confidence: number | null
    reason: string
  }[]
  hidden_connections: { from: string; to: string; path: string[]; hops: number }[]
  contradictions: {
    rejected_finding: { agent: string; summary: string }
    conflicts_with: { agent: string; summary: string }
    shared_entities: string[]
    note: string | null
  }[]
  missing_evidence: { agent: string; gap: string }[]
  ai_generated_hypotheses: {
    title: string
    body: string
    confidence: number
    agent: string
    source_entities: string[]
  }[]
  evidence_clusters: { label: string; member_count: number; finding_types: string[] }[]
  replay: {
    turn_index: number
    query: string
    resolved_query: string
    summary: string
    timestamp: string
  }[]
}

export interface DecisionTimelineEntry {
  turn_index: number
  created_at: string
  query: string
  conclusion: string
  finding_count: number
}

export type CommentTargetType = 'finding' | 'evidence' | 'entity' | 'board_object'
export type BoardObjectType = 'note' | 'link' | 'hypothesis'
export type ReviewStatus = 'draft' | 'in_review' | 'approved' | 'rejected'

export interface Comment {
  id: number
  session_id: number
  target_type: CommentTargetType
  target_ref: string
  author_officer_id: number | null
  body: string
  created_at: string
  edited_at: string | null
}

export interface BoardObject {
  id: number
  session_id: number
  object_type: BoardObjectType
  content: string
  payload: Record<string, unknown> | null
  created_by_officer_id: number | null
  created_at: string
  updated_at: string
}

export interface ReviewRequestRecord {
  id: number
  session_id: number
  status: ReviewStatus
  requested_by_officer_id: number | null
  reviewer_officer_id: number | null
  notes: string | null
  decision_notes: string | null
  created_at: string
  decided_at: string | null
}

export type VoiceIntent =
  | 'empty'
  | 'open_case'
  | 'close_case'
  | 'reopen_case'
  | 'archive_case'
  | 'assign'
  | 'open_board'
  | 'read_report'
  | 'generate_report'
  | 'vehicle_owner'
  | 'freeze_account'
  | 'investigate'

export interface VoiceCommandResult {
  intent: VoiceIntent
  spoken_response: string
  session_id: number | null
  data: Record<string, unknown>
}

export interface VoiceTranscribeResult {
  text: string
  language: string
  confidence: number
  provider: string
  warnings: string[]
}

export interface VoiceQueryResult {
  transcript: string
  detected_language: string
  working_transcript: string
  intent: VoiceIntent
  spoken_response_en: string
  spoken_response: string
  session_id: number | null
  data: Record<string, unknown>
  audio_base64: string | null
  audio_content_type: string | null
  audio_provider: string | null
  warnings: string[]
}

export type VoiceCommandPhrases = Record<string, { en: string; kn: string }>

export interface ApiError {
  status: number
  detail: string
}
