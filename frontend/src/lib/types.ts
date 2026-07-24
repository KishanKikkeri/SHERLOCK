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

// ---------------------------------------------------------------------------
// Stage F2 — Conversation Intelligence System
// Mirrors backend/api/conversation_chat.py + backend/conversation/*.py.
// ---------------------------------------------------------------------------

export type ConversationIntent = 'investigate' | 'summarize' | 'export_pdf' | 'clear_history'

export interface ConversationCitationEntity {
  kind: 'person' | 'fir' | 'account' | 'organization' | 'property' | 'weapon'
  id: number
  label: string
}

export interface ConversationCitation {
  finding_type: string
  agent_name: string
  summary: string
  confidence: number
  validated: boolean
  evidence: string[]
  reasoning: string
  related_documents: string[]
  entities: ConversationCitationEntity[]
}

export interface ConversationMessageResult {
  session_id: number
  intent: ConversationIntent
  message: string
  reply: string
  final_report: Record<string, unknown> | null
  citations: ConversationCitation[]
  suggested_questions: string[]
  pdf_available?: boolean
  pdf_warnings?: string[]
}

export interface ConversationHistoryMessage {
  role: 'user' | 'assistant'
  turn_index: number
  text: string
  created_at: string
  type?: 'answer' | 'clarification'
  options?: { id: number; kind: string; label: string }[]
  archived?: boolean
}

export interface ConversationStreamEvent {
  timestamp: string
  event_type: string
  agent: string | null
  message: string | null
  data: Record<string, unknown> | null
}

export interface ConversationSummaryResult {
  session_id: number
  summary: string | null
  summary_through_turn: number | null
  turn_count: number
}

/** Matches backend/intelligence/executive_summary.py::build_executive_report.
 * Attached as `data.executive_report` on voice `investigate`-intent results
 * (backend/voice/command_router.py) — this is what Analytics cards render
 * by default. The raw `final_report` (all validated + rejected findings,
 * full narrative) is still present alongside it in `data.final_report`
 * for a "Show Agent Trace" view. */
export interface ExecutiveReport {
  title: string
  summary: string
  confidence: number
  risk_level: 'Unknown' | 'Low' | 'Medium' | 'High'
  key_findings: string[]
  supporting_evidence: string[]
  recommendations: string[]
  metrics: Record<string, number>
  entities: { type: string; id: string }[]
  timeline: { label: string; agent: string }[]
  sources: string[]
}

// ---------------------------------------------------------------------------
// Stage G1 — Criminology-Based Offender Profiling Engine
// Mirrors backend/api/offender_profile.py + backend/intelligence/*.py.
// ---------------------------------------------------------------------------

export interface OffenderIdentity {
  person_id: number
  name: string
  gender: string
  age: number
  occupation: string | null
  home_location: { district: string; state: string } | null
}

export interface OffenderCriminalHistory {
  fir_count: number
  arrest_count: number
  chargesheet_count: number
  chargesheets_filed: number
  conviction_count: number
  pending_investigation_count: number
  crime_categories: Record<string, number>
  first_offence_date: string | null
  latest_offence_date: string | null
  days_since_last_offence: number | null
  crime_frequency_per_year: number | null
  repeat_offender: boolean
  habitual_offender: boolean
  custody_status: string | null
  on_bail_no_chargesheet: boolean
}

export interface OffenderBehaviorProfile {
  escalation: { ladder: string[]; score: number; trend: string; because: string }
  aggression: {
    score: number
    violent_offence_count: number
    weapon_incidents: number
    weapons_recovered_from_person: number
    weapon_types: string[]
    because: string
  }
  planning: {
    score: number
    alias_count: number
    vehicle_count: number
    bank_account_count: number
    coordinated_fir_count: number
    indicators: string[]
    because: string
  }
  mobility: {
    districts_operated: string[]
    states_operated: string[]
    average_travel_radius_km: number | null
    because: string
  }
  target_selection: {
    victim_count: number
    victim_gender_distribution: Record<string, number>
    note: string
    because: string
  }
  time_profile: {
    most_common_weekday: string | null
    most_common_month: string | null
    most_common_hour: number | null
    because: string
  }
}

export interface OffenderModusOperandi {
  weapon_usage: string[]
  vehicle_usage: string[]
  financial_method: string | null
  crime_sequence: string[]
  location_preference: { most_common_district: string; occurrences: number; district_spread: Record<string, number> } | null
  mo_keyword_buckets: Record<string, string[]>
  mo_repeat_keywords: string[]
  mo_clustering_method: string
  because: string
}

export interface OffenderRiskProfile {
  overall_score: number
  band: 'Very Low' | 'Low' | 'Medium' | 'High' | 'Critical'
  components: Record<string, number>
  weights: Record<string, number>
  because: string[]
}

export interface OffenderInvestigationPriority {
  priority: 'Routine' | 'Monitor' | 'Priority' | 'Urgent' | 'Critical'
  ladder_index: number
  ladder: string[]
  because: string[]
}

export interface OffenderNetworkProfile {
  associate_count: number
  associates: { associate_id: number; name: string; edge_type: string; relation_type: string | null; strength: number | null }[]
  repeat_collaborators: { associate_id: number; name: string }[]
  organizations: { organization_id: number; name: string | null; role: string | null }[]
  financial_links: { person_id: number; name: string | null; transaction_count: number; suspicious_transaction_count: number; total_amount: number }[]
  shared_address_with: { person_id: number; name: string }[]
  graph_metrics:
    | { available: false; reason: string }
    | { available: true; pagerank: number; degree_centrality: number; community_size: number; influence_score: number; because: string }
  because: string
}

export interface OffenderRecommendation {
  action: string
  because: string
}

export interface OffenderProfile {
  identity: OffenderIdentity
  aliases: string[]
  criminal_history: OffenderCriminalHistory
  behavior_profile: OffenderBehaviorProfile
  modus_operandi: OffenderModusOperandi
  risk_profile: OffenderRiskProfile
  investigation_priority: OffenderInvestigationPriority
  network_profile: OffenderNetworkProfile
  recommendations: OffenderRecommendation[]
}

export interface OffenderProfileSummary {
  person_id: number
  name: string
  risk_score: number
  risk_band: string
  priority: string
  fir_count: number
  crime_categories: string[]
  districts_operated: string[]
}

export interface OffenderTimelineEvent {
  date: string
  type: 'accused' | 'victim' | 'witness' | 'arrest' | 'chargesheet'
  label: string
  fir_id: number
}

// -- Sociological Crime Insights (Agent 2 workstream) -----------------------
// Mirrors backend/intelligence/sociological_insights.py's build_dashboard()
// / build_report() output exactly — see that file for what's real vs a
// placeholder/extension-point.

export interface DemographicBreakdown {
  sample_size: number
  gender_distribution: Record<string, number>
  age_bracket_distribution: Record<string, number>
  occupation_distribution: Record<string, number>
}

export interface SocioeconomicAnalysis {
  occupation_crime_correlation: Record<string, Record<string, number>>
  note: string
  unavailable: Record<string, string>
}

export interface RepeatOffenderCommunities {
  count: number
  person_ids: number[]
  method: string
}

export interface FamilyCrimeLinks {
  count: number
  links: { person_a: number; person_b: number; strength: number }[]
  method: string
}

export interface GangIndicators {
  count: number
  person_ids: number[]
  organizations: Record<string, number>
  method: string
}

export interface CommunityVulnerability {
  by_district_crime_density: { district: string; crime_count: number }[]
  method: string
}

export interface SocialRiskFactors {
  repeat_offender_communities: RepeatOffenderCommunities
  family_crime_links: FamilyCrimeLinks
  gang_indicators: GangIndicators
  community_vulnerability: CommunityVulnerability
}

export interface UnavailableDimension {
  available: false
  reason: string
}

export interface CorrelationMatrix {
  gender_by_crime_type: Record<string, Record<string, number>>
  age_bracket_by_crime_type: Record<string, Record<string, number>>
  sample_size: number
  method: string
}

export interface SociologicalDashboard {
  scope: {
    accused_sample_size: number
    victim_sample_size: number
    scoped_to_investigation: boolean
  }
  demographics: {
    accused: DemographicBreakdown
    victims: DemographicBreakdown
  }
  socioeconomic_analysis: SocioeconomicAnalysis
  social_risk_factors: SocialRiskFactors
  urbanization_analysis: UnavailableDimension | { available: true; crime_count_by_urbanization_tier: Record<string, number> }
  migration_analysis: UnavailableDimension | { available: true; accused_count_by_origin_district: Record<string, number> }
  economic_stress_analysis: UnavailableDimension | { available: true; district_crime_vs_economic_indicators: Record<string, unknown> }
  education_analysis: UnavailableDimension | { available: true; accused_count_by_education_level: Record<string, number> }
  correlation_matrix: CorrelationMatrix
  data_availability: Record<string, string>
}

export interface SociologicalReport {
  executive_summary: string
  key_findings: string[]
  risk_factors: Record<string, unknown>[]
  evidence: string[]
  recommendations: string[]
  confidence: { score: number; basis: string }
  supporting_data: SociologicalDashboard
}

// -- Forecasting & Early Warning Engine (Requirement 8) ---------------------
// Mirrors backend/forecasting/summary_engine.py's generate_forecast_dashboard()
// output. Deterministic — no LLM anywhere in this package.

export interface TrendForecast {
  label: string
  current: number
  predicted: number
  growth: number
  confidence: number
  method: string
  months_used: number
  reason: string
  crime_type?: string | null
  district?: string | null
  target_month?: string
}

export interface HotspotPrediction {
  district: string
  predicted_risk: 'High' | 'Medium' | 'Low'
  probability: number
  expected_incidents: number
  confidence: number
  evidence: {
    currently_a_hotspot: boolean
    trend_growth_pct: number
    repeat_offenders_in_district: number
    festival_season_share: number
  }
  neighboring_hotspot_influence:
    | { available: false; reason: string }
    | { available: true; neighbors: string[]; avg_neighbor_growth_pct: number }
}

export interface RepeatAlert {
  alert: string
  severity: 'Critical' | 'High' | 'Medium' | 'Low'
  occurrences: number
  window_days: number | null
  recommendation: string
  district?: string
  location?: string
  [key: string]: unknown
}

export interface RepeatAlerts {
  repeat_locations: RepeatAlert[]
  repeat_accused: RepeatAlert[]
  repeat_mo: RepeatAlert[]
  repeat_victim_groups: RepeatAlert[]
  repeat_crime_types: RepeatAlert[]
}

export interface GangAlert {
  gang_id: string
  members: number
  member_person_ids: number[]
  activity_growth: number
  risk: 'Critical' | 'High' | 'Medium' | 'Low'
  category: 'Emerging' | 'Growing' | 'High-risk' | 'Dormant' | 'Stable'
  district: string | null
  confirmed_org_membership: boolean
  most_central_person_id: number | null
  evidence: Record<string, number>
  method: string
}

export interface EarlyWarning {
  title: string
  severity: 'Critical' | 'High' | 'Medium' | 'Low'
  confidence: number
  predicted_date: string
  evidence: string[]
  recommended_actions: string[]
}

export interface ForecastDashboard {
  executive_summary: string
  forecast_cards: {
    overall: TrendForecast
    by_crime_type: TrendForecast[]
  }
  upcoming_hotspots: HotspotPrediction[]
  emerging_crime_types: TrendForecast[]
  gang_alerts: GangAlert[]
  repeat_alerts: RepeatAlerts
  prediction_timeline: TrendForecast[]
  recommendations: string[]
  early_warnings: EarlyWarning[]
}
