import { useState } from 'react'
import {
  Users, UserX, Repeat, Users2, Building2, MapPinned,
  FileText, ChevronDown, RefreshCcw,
} from 'lucide-react'
import { useSociologicalDashboard, useSociologicalReport } from '@/lib/queries/sociological'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { BarList } from './BarList'
import { CorrelationHeatmap } from './CorrelationHeatmap'

function KpiTile({
  icon: Icon,
  label,
  value,
  isLoading,
}: {
  icon: typeof Users
  label: string
  value: number | string | undefined
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

function UnavailableDimensionCard({ label, reason }: { label: string; reason: string }) {
  return (
    <div className="rounded-md border border-dashed border-border-strong bg-surface-raised p-3">
      <div className="mb-1 flex items-center gap-2">
        <Badge tone="neutral">Extension point</Badge>
        <p className="text-xs font-medium text-text">{label}</p>
      </div>
      <p className="text-[11px] text-muted">{reason}</p>
    </div>
  )
}

function ReportSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border-subtle pt-3 first:border-t-0 first:pt-0">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
      {children}
    </div>
  )
}

export function SociologicalInsightsPage() {
  const { data, isLoading, isError, refetch, isFetching } = useSociologicalDashboard()
  const [reportOpen, setReportOpen] = useState(false)
  const report = useSociologicalReport(reportOpen)

  const risk = data?.social_risk_factors
  const topDistrict = risk?.community_vulnerability.by_district_crime_density[0]

  const unavailable = data
    ? (Object.entries(data.data_availability).filter(([, v]) => v.includes('unavailable')) as [string, string][])
    : []
  const unavailableReasons: Record<string, string> = {}
  if (data) {
    if (!data.urbanization_analysis.available) unavailableReasons.urbanization = data.urbanization_analysis.reason
    if (!data.migration_analysis.available) unavailableReasons.migration = data.migration_analysis.reason
    if (!data.economic_stress_analysis.available) unavailableReasons.economic_stress = data.economic_stress_analysis.reason
    if (!data.education_analysis.available) unavailableReasons.education = data.education_analysis.reason
    if (data.socioeconomic_analysis.unavailable) {
      Object.assign(unavailableReasons, data.socioeconomic_analysis.unavailable)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Sociological Insights</h1>
          <p className="text-sm text-muted">
            Criminology/sociology layer — why patterns emerge, not just where. Every number below is a
            direct tabulation or query against recorded data; anything the schema doesn't have yet is
            named explicitly rather than estimated.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => refetch()} isLoading={isFetching}>
          <RefreshCcw className="h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      {isError && <p className="text-xs text-critical">Failed to load — check the backend is reachable.</p>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile icon={Users} label="Accused in scope" value={data?.scope.accused_sample_size} isLoading={isLoading} />
        <KpiTile icon={UserX} label="Victims in scope" value={data?.scope.victim_sample_size} isLoading={isLoading} />
        <KpiTile icon={Repeat} label="Repeat offenders" value={risk?.repeat_offender_communities.count} isLoading={isLoading} />
        <KpiTile icon={Users2} label="Family-linked pairs" value={risk?.family_crime_links.count} isLoading={isLoading} />
        <KpiTile icon={Building2} label="Gang-affiliated accused" value={risk?.gang_indicators.count} isLoading={isLoading} />
        <KpiTile icon={MapPinned} label="Highest-density district" value={topDistrict?.district} isLoading={isLoading} />
      </div>

      {/* Demographic charts */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader title="Accused demographics" subtitle={`Sample size: ${data?.demographics.accused.sample_size ?? '—'}`} />
          <CardBody className="flex flex-col gap-4">
            {isLoading ? <Skeleton className="h-32 w-full" /> : (
              <>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-text">Gender</p>
                  <BarList data={data!.demographics.accused.gender_distribution} colorClassName="bg-entity-accused" />
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-text">Age bracket</p>
                  <BarList data={data!.demographics.accused.age_bracket_distribution} colorClassName="bg-entity-accused" />
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-text">Top occupations</p>
                  <BarList data={data!.demographics.accused.occupation_distribution} colorClassName="bg-entity-accused" />
                </div>
              </>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Victim demographics" subtitle={`Sample size: ${data?.demographics.victims.sample_size ?? '—'}`} />
          <CardBody className="flex flex-col gap-4">
            {isLoading ? <Skeleton className="h-32 w-full" /> : (
              <>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-text">Gender</p>
                  <BarList data={data!.demographics.victims.gender_distribution} colorClassName="bg-entity-victim" />
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-text">Age bracket</p>
                  <BarList data={data!.demographics.victims.age_bracket_distribution} colorClassName="bg-entity-victim" />
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-text">Top occupations</p>
                  <BarList data={data!.demographics.victims.occupation_distribution} colorClassName="bg-entity-victim" />
                </div>
              </>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Correlation matrix */}
      <Card>
        <CardHeader
          title="Correlation matrix"
          subtitle={data ? `${data.correlation_matrix.method} (n=${data.correlation_matrix.sample_size})` : undefined}
        />
        <CardBody className="flex flex-col gap-5">
          {isLoading ? <Skeleton className="h-40 w-full" /> : (
            <>
              <div>
                <p className="mb-1.5 text-xs font-medium text-text">Gender × crime type</p>
                <CorrelationHeatmap matrix={data!.correlation_matrix.gender_by_crime_type} rowHeader="Gender" colHeader="Crime type" />
              </div>
              <div>
                <p className="mb-1.5 text-xs font-medium text-text">Age bracket × crime type</p>
                <CorrelationHeatmap matrix={data!.correlation_matrix.age_bracket_by_crime_type} rowHeader="Age bracket" colHeader="Crime type" />
              </div>
              <div>
                <p className="mb-1.5 text-xs font-medium text-text">Occupation × crime type (socio-economic correlation)</p>
                <CorrelationHeatmap
                  matrix={data!.socioeconomic_analysis.occupation_crime_correlation}
                  rowHeader="Occupation"
                  colHeader="Crime type"
                />
              </div>
            </>
          )}
        </CardBody>
      </Card>

      {/* Risk summaries + explainability references */}
      <Card>
        <CardHeader title="Social risk factors" subtitle="Each factor's evidence trail doubles as its explainable-AI reference — the exact query/method that produced it." />
        <CardBody className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {isLoading ? <Skeleton className="h-24 w-full md:col-span-2" /> : risk && (
            <>
              <div className="rounded-md border border-border bg-surface-raised p-3">
                <p className="text-sm font-medium text-text">Repeat offender communities</p>
                <p className="font-mono text-lg text-accent">{risk.repeat_offender_communities.count}</p>
                <p className="mt-1 text-[11px] text-muted">{risk.repeat_offender_communities.method}</p>
              </div>
              <div className="rounded-md border border-border bg-surface-raised p-3">
                <p className="text-sm font-medium text-text">Family crime links</p>
                <p className="font-mono text-lg text-accent">{risk.family_crime_links.count}</p>
                <p className="mt-1 text-[11px] text-muted">{risk.family_crime_links.method}</p>
              </div>
              <div className="rounded-md border border-border bg-surface-raised p-3">
                <p className="text-sm font-medium text-text">Gang indicators</p>
                <p className="font-mono text-lg text-accent">{risk.gang_indicators.count}</p>
                <p className="mt-1 text-[11px] text-muted">{risk.gang_indicators.method}</p>
                {Object.keys(risk.gang_indicators.organizations).length > 0 && (
                  <div className="mt-2">
                    <BarList data={risk.gang_indicators.organizations} colorClassName="bg-critical" />
                  </div>
                )}
              </div>
              <div className="rounded-md border border-border bg-surface-raised p-3">
                <p className="text-sm font-medium text-text">Community vulnerability (crime-density proxy)</p>
                <div className="mt-2">
                  <BarList
                    data={Object.fromEntries(risk.community_vulnerability.by_district_crime_density.slice(0, 8).map((d) => [d.district, d.crime_count]))}
                    colorClassName="bg-warning"
                  />
                </div>
                <p className="mt-1 text-[11px] text-muted">{risk.community_vulnerability.method}</p>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      {/* Unavailable dimensions — named, not hidden */}
      {unavailable.length > 0 && (
        <Card>
          <CardHeader
            title="Not yet available in the current schema"
            subtitle="Each has a real extension-point method already built — feeding it real data produces a real analysis with no pipeline changes."
          />
          <CardBody className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {Object.entries(unavailableReasons).map(([dim, reason]) => (
              <UnavailableDimensionCard key={dim} label={dim.replaceAll('_', ' ')} reason={reason} />
            ))}
          </CardBody>
        </Card>
      )}

      {/* Structured sociological report */}
      <Card>
        <CardHeader
          title="Sociological report"
          action={
            <Button variant="secondary" size="sm" onClick={() => setReportOpen((v) => !v)} isLoading={reportOpen && report.isLoading}>
              <FileText className="h-3.5 w-3.5" />
              {reportOpen ? 'Hide report' : 'Generate report'}
              <ChevronDown className={`h-3 w-3 transition-transform ${reportOpen ? 'rotate-180' : ''}`} />
            </Button>
          }
        />
        {reportOpen && (
          <CardBody className="flex flex-col gap-3">
            {report.isError && <p className="text-xs text-critical">Failed to generate report.</p>}
            {report.data && (
              <>
                <ReportSection title="Executive summary">
                  <p className="whitespace-pre-wrap text-sm text-text">{report.data.executive_summary}</p>
                </ReportSection>
                <ReportSection title="Key findings">
                  <ul className="list-inside list-disc text-sm text-text">
                    {report.data.key_findings.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                </ReportSection>
                <ReportSection title="Risk factors">
                  <ul className="flex flex-col gap-1 text-xs text-muted">
                    {report.data.risk_factors.map((rf, i) => (
                      <li key={i} className="font-mono">{JSON.stringify(rf)}</li>
                    ))}
                  </ul>
                </ReportSection>
                <ReportSection title="Evidence">
                  <ul className="list-inside list-disc text-xs text-muted">
                    {report.data.evidence.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </ReportSection>
                <ReportSection title="Recommendations">
                  <ul className="list-inside list-disc text-sm text-text">
                    {report.data.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </ReportSection>
                <ReportSection title="Confidence">
                  <div className="flex items-center gap-2">
                    <Badge tone={report.data.confidence.score >= 0.7 ? 'positive' : report.data.confidence.score >= 0.4 ? 'warning' : 'critical'}>
                      {Math.round(report.data.confidence.score * 100)}%
                    </Badge>
                    <p className="text-xs text-muted">{report.data.confidence.basis}</p>
                  </div>
                </ReportSection>
                <ReportSection title="Supporting data">
                  <p className="text-xs text-muted">
                    Full computed dashboard ({report.data.supporting_data.scope.accused_sample_size} accused,{' '}
                    {report.data.supporting_data.scope.victim_sample_size} victims) — same numbers charted above, kept here for
                    traceability from any claim in this report back to its source figures.
                  </p>
                </ReportSection>
              </>
            )}
          </CardBody>
        )}
      </Card>
    </div>
  )
}
