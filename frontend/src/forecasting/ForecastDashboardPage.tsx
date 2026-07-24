import { AlertTriangle, TrendingUp, MapPinned, Users2, RefreshCcw, ShieldAlert } from 'lucide-react'
import { useForecastDashboard } from '@/lib/queries/forecast'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { BarList } from '@/sociological/BarList'
import type { EarlyWarning, GangAlert, RepeatAlert, TrendForecast } from '@/lib/types'

function severityTone(severity: string): 'critical' | 'warning' | 'positive' | 'neutral' {
  if (severity === 'Critical') return 'critical'
  if (severity === 'High') return 'warning'
  if (severity === 'Medium') return 'neutral'
  return 'positive'
}

function TrendCard({ f }: { f: TrendForecast }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-text">{f.crime_type ? f.crime_type.replace('_', ' ') : f.label}</p>
        <Badge tone={f.growth >= 15 ? 'warning' : f.growth <= -15 ? 'positive' : 'neutral'}>
          {f.growth >= 0 ? '+' : ''}{f.growth.toFixed(1)}%
        </Badge>
      </div>
      <p className="mt-1 font-mono text-lg text-accent">{f.current} → {f.predicted}</p>
      <p className="mt-1 text-[11px] text-muted">{f.reason}</p>
      <p className="mt-0.5 text-[11px] text-subtle">{f.method} · confidence {Math.round(f.confidence * 100)}% · {f.months_used}mo history</p>
    </div>
  )
}

function WarningRow({ w }: { w: EarlyWarning }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-text">{w.title}</p>
        <Badge tone={severityTone(w.severity)}>{w.severity}</Badge>
      </div>
      <p className="mt-1 text-[11px] text-muted">Predicted for {w.predicted_date} · confidence {Math.round(w.confidence * 100)}%</p>
      <ul className="mt-2 list-inside list-disc text-[11px] text-muted">
        {w.evidence.map((e, i) => <li key={i}>{e}</li>)}
      </ul>
      {w.recommended_actions.map((a, i) => (
        <p key={i} className="mt-1 text-xs text-text">→ {a}</p>
      ))}
    </div>
  )
}

function GangCard({ g }: { g: GangAlert }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-text">{g.gang_id} · {g.category}</p>
        <Badge tone={severityTone(g.risk)}>{g.risk}</Badge>
      </div>
      <p className="mt-1 text-xs text-muted">
        {g.members} member(s) · {g.district ?? 'district unknown'} · activity {g.activity_growth >= 0 ? '+' : ''}{g.activity_growth}%
      </p>
      {g.confirmed_org_membership && <p className="mt-1 text-[11px] text-critical">Recorded gang-org membership confirmed</p>}
      <p className="mt-1 text-[11px] text-subtle">{g.method}</p>
    </div>
  )
}

function RepeatAlertRow({ a }: { a: RepeatAlert }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised p-2.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-text">{a.alert}</p>
        <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
      </div>
      <p className="mt-1 text-[11px] text-muted">
        {a.occurrences} occurrence(s){a.window_days ? ` in ${a.window_days} day(s)` : ''} — {a.recommendation}
      </p>
    </div>
  )
}

export function ForecastDashboardPage() {
  const { data, isLoading, isError, refetch, isFetching } = useForecastDashboard()

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Forecasting & Early Warning</h1>
          <p className="text-sm text-muted">
            Deterministic — moving average / weighted moving average / exponential smoothing, NetworkX
            community detection, and z-score anomaly checks. No LLM anywhere in this pipeline.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => refetch()} isLoading={isFetching}>
          <RefreshCcw className="h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      {isError && <p className="text-xs text-critical">Failed to load — check the backend is reachable.</p>}
      {isLoading && <Skeleton className="h-40 w-full" />}

      {data && (
        <>
          <Card>
            <CardHeader title="Executive summary" />
            <CardBody>
              <p className="text-sm text-text">{data.executive_summary}</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Early warnings"
              subtitle="Severity-ranked, each evidence line traces to a specific engine's real number."
              action={<AlertTriangle className="h-4 w-4 text-warning" aria-hidden />}
            />
            <CardBody className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {data.early_warnings.length === 0 ? (
                <p className="text-xs text-muted">No warnings above threshold in the current data.</p>
              ) : data.early_warnings.map((w, i) => <WarningRow key={i} w={w} />)}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Forecast cards" subtitle="Overall + by crime type, weighted moving average by default" action={<TrendingUp className="h-4 w-4 text-accent" aria-hidden />} />
            <CardBody className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <TrendCard f={{ ...data.forecast_cards.overall, label: 'Overall' }} />
              {data.forecast_cards.by_crime_type.map((f) => <TrendCard key={f.crime_type} f={f} />)}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Upcoming hotspots" subtitle="Persistence + trend + repeat-offenders + festival-season composite" action={<MapPinned className="h-4 w-4 text-accent" aria-hidden />} />
            <CardBody>
              <BarList
                data={Object.fromEntries(data.upcoming_hotspots.map((h) => [h.district, Math.round(h.probability * 100)]))}
                colorClassName="bg-warning"
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Prediction timeline" subtitle="Rolling one-step-ahead forecasts, each fed back into the series" />
            <CardBody>
              <BarList
                data={Object.fromEntries(data.prediction_timeline.map((p) => [p.target_month ?? p.label, p.predicted]))}
                colorClassName="bg-accent"
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Gang activity alerts" subtitle="NetworkX community detection over association/org/co-accused/call/transaction/vehicle/weapon links" action={<Users2 className="h-4 w-4 text-critical" aria-hidden />} />
            <CardBody className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {data.gang_alerts.length === 0 ? (
                <p className="text-xs text-muted">No communities of size ≥ 3 detected in the current data.</p>
              ) : data.gang_alerts.map((g) => <GangCard key={g.gang_id} g={g} />)}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Repeat alerts" subtitle="Fixed-threshold repeats — locations, MO, victim groups, crime types, accused" action={<ShieldAlert className="h-4 w-4 text-warning" aria-hidden />} />
            <CardBody className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {Object.entries(data.repeat_alerts).flatMap(([group, alerts]) =>
                (alerts as RepeatAlert[]).map((a, i) => <RepeatAlertRow key={`${group}-${i}`} a={a} />),
              )}
              {Object.values(data.repeat_alerts).every((a) => a.length === 0) && (
                <p className="text-xs text-muted md:col-span-2">No repeat patterns above threshold in the current data.</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Recommendations" />
            <CardBody>
              <ul className="list-inside list-disc text-sm text-text">
                {data.recommendations.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
