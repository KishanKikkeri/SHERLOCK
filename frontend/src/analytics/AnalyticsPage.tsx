import { useState } from 'react'
import { Users, MailWarning as FileWarning, Network, Gavel, Landmark, ShieldAlert } from 'lucide-react'
import { ANALYTICS_TOPICS } from './topics'
import { AnalyticsTopicCard } from './AnalyticsTopicCard'
import { useMetrics } from '@/lib/queries/system'
import { useSessions } from '@/lib/queries/sessions'
import { Skeleton } from '@/components/ui/Skeleton'

function KpiTile({
  icon: Icon,
  label,
  value,
  isLoading,
}: {
  icon: typeof Users
  label: string
  value: number | undefined
  isLoading: boolean
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-4">
      <Icon className="h-5 w-5 text-accent" aria-hidden />
      <div>
        {isLoading ? <Skeleton className="h-6 w-12" /> : <p className="font-mono text-lg font-semibold text-text">{value ?? '—'}</p>}
        <p className="text-xs text-muted">{label}</p>
      </div>
    </div>
  )
}

export function AnalyticsPage() {
  const { data: metrics, isLoading: metricsLoading } = useMetrics(true)
  const { data: sessions } = useSessions({ status: 'open' })
  const [sessionId, setSessionId] = useState<number | undefined>(undefined)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Analytics</h1>
          <p className="text-sm text-muted">
            Real numbers where they exist; everything else runs a live query against the actual
            investigation agents — see each card's badge for which one.
          </p>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted">
          Session context
          <select
            value={sessionId ?? ''}
            onChange={(e) => setSessionId(e.target.value ? Number(e.target.value) : undefined)}
            className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            <option value="">None</option>
            {sessions?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.session_code}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile icon={Users} label="Persons of interest" value={metrics?.persons} isLoading={metricsLoading} />
        <KpiTile icon={FileWarning} label="Open FIRs" value={metrics?.firs} isLoading={metricsLoading} />
        <KpiTile icon={Network} label="Known relationships" value={metrics?.relationships} isLoading={metricsLoading} />
        <KpiTile icon={Gavel} label="Repeat offenders" value={metrics?.repeat_offenders} isLoading={metricsLoading} />
        <KpiTile icon={Landmark} label="Fraud network size" value={metrics?.fraud_network_size} isLoading={metricsLoading} />
        <KpiTile icon={ShieldAlert} label="Suspicious transactions" value={metrics?.suspicious_transactions} isLoading={metricsLoading} />
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold text-muted">
          Deeper analysis — each button runs a real query through the specialist agent named on its badge, not a mock
        </p>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {ANALYTICS_TOPICS.map((topic) => (
            <AnalyticsTopicCard key={topic.id} topic={topic} sessionId={sessionId} />
          ))}
        </div>
      </div>
    </div>
  )
}
