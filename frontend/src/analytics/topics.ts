import {
  TrendingUp,
  MapPinned,
  Repeat,
  Users,
  Landmark,
  Building2,
  Crosshair,
  Radar,
  ShieldAlert,
  Compass,
  type LucideIcon,
} from 'lucide-react'

export interface AnalyticsTopic {
  id: string
  label: string
  icon: LucideIcon
  /** Real finding_type(s) this maps to — backend/agents/base/explainability.py
   * REASONING_BY_FINDING_TYPE is the source of truth, not guessed. */
  findingTypes: string[]
  agentHint: string
  description: string
  /** Query text sent verbatim as the transcript to POST /voice/command.
   * Free-text phrasing, same as a person would type or say — the
   * backend's own intent classifier + investigation pipeline does the
   * rest, not a structured query language. */
  query: string
  /** decision_support is explicitly "synthesized from this
   * investigation's own findings — no new querying", so it only makes
   * sense against an existing session, unlike every other topic here. */
  requiresSession?: boolean
}

export const ANALYTICS_TOPICS: AnalyticsTopic[] = [
  {
    id: 'crime-trends',
    label: 'Crime trends',
    icon: TrendingUp,
    findingTypes: ['crime_pattern', 'seasonal_spike'],
    agentHint: 'Pattern Analysis agent',
    description: 'Location-clustered crime patterns, including festival-season spikes.',
    query: 'What crime patterns and seasonal trends are showing up across recent cases?',
  },
  {
    id: 'hotspots',
    label: 'Hotspots',
    icon: MapPinned,
    findingTypes: ['hotspot_forecast'],
    agentHint: 'Forecasting agent',
    description: 'Location clusters projected forward from historical concentration.',
    query: 'Where are the emerging crime hotspots based on recent case data?',
  },
  {
    id: 'repeat-offenders',
    label: 'Repeat offenders',
    icon: Repeat,
    findingTypes: ['repeat_offender_network'],
    agentHint: 'Network Analysis agent',
    description: 'Persons linked to multiple crimes, ranked by offense count.',
    query: 'Who are the repeat offenders showing up across multiple cases right now?',
  },
  {
    id: 'officer-workload',
    label: 'Officer workload',
    icon: Users,
    findingTypes: ['officer_profile', 'assignment_recommendation'],
    agentHint: 'Officer Intelligence agent',
    description: "Officers' active caseload, specialization match, and assignment fit.",
    query: 'What does current officer workload and case assignment look like?',
  },
  {
    id: 'financial-crimes',
    label: 'Financial crimes',
    icon: Landmark,
    findingTypes: ['financial_network', 'suspicious_pattern', 'bank_network'],
    agentHint: 'Financial Intelligence agent',
    description: 'Mule accounts, fan-in/fan-out transaction structures, flagged hubs.',
    query: 'Show me suspicious financial networks and flagged bank accounts from recent cases.',
  },
  {
    id: 'organizations',
    label: 'Organizations',
    icon: Building2,
    findingTypes: ['organization_profile'],
    agentHint: 'Organization Intelligence agent',
    description: "An organization traced through membership to members' cases and accounts.",
    query: 'What organizations are showing up with the most member involvement in cases?',
  },
  {
    id: 'weapons',
    label: 'Weapons',
    icon: Crosshair,
    findingTypes: ['weapon_history'],
    agentHint: 'Weapon Intelligence agent',
    description: 'Weapons grouped by serial number to detect reuse across cases.',
    query: 'Are any weapons showing up reused across multiple cases?',
  },
  {
    id: 'forecasts',
    label: 'Forecasts',
    icon: Radar,
    findingTypes: ['predictive_forecast', 'hotspot_forecast'],
    agentHint: 'Forecasting agent',
    description: 'District/crime-type/workload projection from historical clustering.',
    query: 'What does the crime forecast look like for the districts we operate in?',
  },
  {
    id: 'risk-scores',
    label: 'Risk scores',
    icon: ShieldAlert,
    findingTypes: ['behavioral_profile'],
    agentHint: 'Behavioral Intelligence agent',
    description: 'Composite score from crime escalation, severity, and association density.',
    query: 'Which persons of interest currently carry the highest behavioral risk score?',
  },
  {
    id: 'decision-support',
    label: 'Decision support',
    icon: Compass,
    findingTypes: ['decision_support'],
    agentHint: 'Decision Support agent',
    description: "Synthesized from this investigation's own findings — needs a session.",
    query: 'Based on everything found so far in this investigation, what do you recommend?',
    requiresSession: true,
  },
]
