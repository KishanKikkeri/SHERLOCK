import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Search } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/Table'
import { useHighRiskPersons, useProfileSearch } from '@/lib/queries/offender'
import type { OffenderProfileSummary } from '@/lib/types'

const BAND_TONE: Record<string, 'positive' | 'warning' | 'critical' | 'neutral'> = {
  'Very Low': 'positive',
  Low: 'positive',
  Medium: 'warning',
  High: 'critical',
  Critical: 'critical',
}

export function HighRiskPersonsPage() {
  const [minRisk, setMinRisk] = useState(41)
  const [nameFilter, setNameFilter] = useState('')
  const { data, isLoading } = useHighRiskPersons(minRisk, 30)
  const search = useProfileSearch()

  const results: OffenderProfileSummary[] | undefined = nameFilter
    ? search.data?.persons
    : data?.persons

  function handleSearch() {
    if (nameFilter.trim()) {
      search.mutate({ name_contains: nameFilter.trim(), min_risk: minRisk, limit: 30 })
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-text">Offender Risk Register</h1>
        <p className="text-xs text-muted">
          Deterministic risk scoring from real FIR/arrest/network/financial records — see any
          person's full dossier for the "because" evidence behind their score.
        </p>
      </div>

      <Card>
        <CardHeader title="Filter" />
        <CardBody className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted" htmlFor="min-risk">
              Minimum risk score
            </label>
            <input
              id="min-risk"
              type="number"
              min={0}
              max={100}
              value={minRisk}
              onChange={(e) => setMinRisk(Number(e.target.value))}
              className="h-9 w-24 rounded-md border border-border bg-surface-raised px-2 text-sm text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
            />
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-muted" htmlFor="name-filter">
              Name contains
            </label>
            <div className="flex gap-2">
              <input
                id="name-filter"
                value={nameFilter}
                onChange={(e) => setNameFilter(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search by name…"
                className="h-9 flex-1 rounded-md border border-border bg-surface-raised px-3 text-sm text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
              />
              <button
                onClick={handleSearch}
                className="flex h-9 items-center gap-1.5 rounded-md border border-border bg-surface-raised px-3 text-sm text-text hover:border-border-strong"
              >
                <Search className="h-3.5 w-3.5" /> Search
              </button>
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          {isLoading || search.isPending ? (
            <p className="py-8 text-center text-sm text-muted">Computing risk scores…</p>
          ) : !results || results.length === 0 ? (
            <EmptyState
              icon={<AlertTriangle className="h-6 w-6" />}
              title="No matching persons"
              description="Try lowering the minimum risk score or clearing the name filter."
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Risk</TH>
                  <TH>Priority</TH>
                  <TH>FIRs</TH>
                  <TH>Crime categories</TH>
                  <TH>Districts</TH>
                </TR>
              </THead>
              <TBody>
                {results.map((p) => (
                  <TR key={p.person_id}>
                    <TD>
                      <Link to={`/offender/${p.person_id}`} className="font-medium text-accent hover:underline">
                        {p.name}
                      </Link>
                    </TD>
                    <TD>
                      <Badge tone={BAND_TONE[p.risk_band] ?? 'neutral'}>
                        {p.risk_score} — {p.risk_band}
                      </Badge>
                    </TD>
                    <TD className="text-text">{p.priority}</TD>
                    <TD className="text-text">{p.fir_count}</TD>
                    <TD className="text-muted">{p.crime_categories.join(', ')}</TD>
                    <TD className="text-muted">{p.districts_operated.join(', ')}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
