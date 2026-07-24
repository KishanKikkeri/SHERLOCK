import { useParams } from 'react-router-dom'
import { AlertCircle, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { useOffenderProfile, useOffenderTimeline } from '@/lib/queries/offender'
import { BehaviorTimeline } from '@/offender/BehaviorTimeline'
import { CrimeHistory } from '@/offender/CrimeHistory'
import { EvidencePanel } from '@/offender/EvidencePanel'
import { ModusProfile } from '@/offender/ModusProfile'
import { NetworkSummary } from '@/offender/NetworkSummary'
import { RecommendationPanel } from '@/offender/RecommendationPanel'
import { RiskGauge } from '@/offender/RiskGauge'

export function OffenderProfilePage() {
  const { personId } = useParams<{ personId: string }>()
  const pid = personId ? Number(personId) : undefined

  const { data: profile, isLoading, isError, error } = useOffenderProfile(pid)
  const { data: timeline } = useOffenderTimeline(pid)

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    )
  }

  if (isError || !profile) {
    return (
      <EmptyState
        icon={<AlertCircle className="h-6 w-6" />}
        title="Couldn't load this profile"
        description={(error as { detail?: string })?.detail ?? 'This person may not exist in the record.'}
      />
    )
  }

  const { identity, criminal_history, behavior_profile, modus_operandi, risk_profile, investigation_priority,
    network_profile, recommendations, aliases } = profile

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">{identity.name}</h1>
          <p className="text-sm text-muted">
            {identity.gender} · {identity.age} yrs
            {identity.occupation ? ` · ${identity.occupation}` : ''}
            {identity.home_location ? ` · ${identity.home_location.district}, ${identity.home_location.state}` : ''}
          </p>
          {aliases.length > 0 && (
            <p className="mt-1 text-xs text-subtle">Also known as: {aliases.join(', ')}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={investigation_priority.priority === 'Routine' ? 'neutral' :
            investigation_priority.priority === 'Critical' || investigation_priority.priority === 'Urgent'
              ? 'critical' : 'warning'}>
            {investigation_priority.priority} priority
          </Badge>
          {criminal_history.habitual_offender && <Badge tone="critical">Habitual offender</Badge>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="flex flex-col items-center justify-center p-6 lg:col-span-1">
          <RiskGauge risk={risk_profile} />
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Recommendations" subtitle="Deterministic, evidence-backed — never LLM-generated" />
          <CardBody>
            <RecommendationPanel recommendations={recommendations} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Criminal history" />
          <CardBody>
            <CrimeHistory history={criminal_history} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Modus operandi" />
          <CardBody>
            <ModusProfile modus={modus_operandi} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Network profile" />
          <CardBody>
            <NetworkSummary network={network_profile} personId={identity.person_id} />
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Behaviour profile" />
          <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <BehaviorStat label="Escalation" value={behavior_profile.escalation.trend} because={behavior_profile.escalation.because} />
            <BehaviorStat label="Aggression" value={`${behavior_profile.aggression.score}/100`} because={behavior_profile.aggression.because} />
            <BehaviorStat label="Planning" value={`${behavior_profile.planning.score}/100`} because={behavior_profile.planning.because} />
            <BehaviorStat label="Mobility" value={behavior_profile.mobility.districts_operated.join(', ') || '—'} because={behavior_profile.mobility.because} />
            <BehaviorStat label="Target selection" value={`${behavior_profile.target_selection.victim_count} victim(s)`} because={behavior_profile.target_selection.because} />
            <BehaviorStat label="Time profile" value={behavior_profile.time_profile.most_common_weekday ?? '—'} because={behavior_profile.time_profile.because} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Case timeline" />
          <CardBody>
            <BehaviorTimeline events={timeline?.events ?? []} />
          </CardBody>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader title="Evidence for this score" />
          <CardBody>
            <EvidencePanel risk={risk_profile} priority={investigation_priority} />
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

function BehaviorStat({ label, value, because }: { label: string; value: string; because: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="text-sm font-medium text-text">{value}</p>
      <p className="text-xs text-subtle">{because}</p>
    </div>
  )
}
