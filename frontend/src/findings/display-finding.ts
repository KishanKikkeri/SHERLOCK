// A superset of what's actually available today (from
// BoardIntelligence.ai_generated_hypotheses) and the real AgentFinding
// shape (backend/agents/base/finding.py) — fields not exposed by any
// current endpoint are optional and rendered as an honest "not exposed"
// state, never fabricated. See docs/stage-f/02-API-CONTRACTS.md's
// "Explainability / findings" section for exactly what's missing and why.
export interface DisplayFinding {
  id: string
  summary: string
  body?: string
  agent_name: string
  confidence: number
  source_entities: string[]
  /** Real field on AgentFinding, never populated by any endpoint this
   * frontend can currently reach. */
  evidence?: string[]
  /** Same — backend/agents/base/explainability.py populates this on the
   * full AgentFinding, but it never survives into ai_generated_hypotheses. */
  reasoning?: string
  /** Same — real FIR numbers when available, never invented. */
  related_documents?: string[]
  validated?: boolean
}

export function personSourceEntities(sourceEntities: string[]): number[] {
  return sourceEntities
    .filter((e) => e.startsWith('person_'))
    .map((e) => Number(e.split('_')[1]))
    .filter((n) => Number.isInteger(n))
}
