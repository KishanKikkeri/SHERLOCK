import { useMutation } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { VoiceCommandResult } from '@/lib/types'

/**
 * There is no dedicated analytics/stats router anywhere in the backend
 * — checked. Every topic in the F7 brief (crime trends, hotspots,
 * repeat offenders, officer workload, financial crimes, organizations,
 * weapons, forecasts, risk scores, decision support) maps to a real
 * specialist agent (backend/agents/*), but the only way to reach any
 * of them is a natural-language query through the investigation
 * pipeline. `POST /voice/command` already *is* that — it's named for
 * voice, but the body is just `{transcript, session_id?}`, no audio
 * involved, and its "investigate" fallback intent runs the exact same
 * `run_investigation_once` the WS stream uses. This hook calls it with
 * typed, topic-specific query text instead of a voice transcript. Real
 * analysis, not a renamed mock — see docs/stage-f/02-API-CONTRACTS.md.
 */
export function useAnalyticsQuery() {
  return useMutation({
    mutationFn: (body: { query: string; session_id?: number }) =>
      apiFetch<VoiceCommandResult>('/voice/command', {
        method: 'POST',
        body: { transcript: body.query, session_id: body.session_id },
      }),
  })
}
