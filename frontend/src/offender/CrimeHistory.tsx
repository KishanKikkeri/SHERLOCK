import { Badge } from '@/components/ui/Badge'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/Table'
import type { OffenderCriminalHistory } from '@/lib/types'

export function CrimeHistory({ history }: { history: OffenderCriminalHistory }) {
  const rows: [string, string][] = [
    ['FIRs (accused)', String(history.fir_count)],
    ['Arrests', String(history.arrest_count)],
    ['Chargesheets filed', `${history.chargesheets_filed} / ${history.chargesheet_count}`],
    ['Convictions', String(history.conviction_count)],
    ['Pending investigations', String(history.pending_investigation_count)],
    ['First offence', history.first_offence_date ? new Date(history.first_offence_date).toLocaleDateString() : '—'],
    ['Latest offence', history.latest_offence_date ? new Date(history.latest_offence_date).toLocaleDateString() : '—'],
    [
      'Crime frequency',
      history.crime_frequency_per_year !== null ? `${history.crime_frequency_per_year} / year` : 'n/a (single offence)',
    ],
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {history.repeat_offender && <Badge tone="warning">Repeat offender</Badge>}
        {history.habitual_offender && <Badge tone="critical">Habitual offender</Badge>}
        {history.on_bail_no_chargesheet && <Badge tone="critical">On bail, no chargesheet</Badge>}
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Metric</TH>
            <TH>Value</TH>
          </TR>
        </THead>
        <TBody>
          {rows.map(([label, value]) => (
            <TR key={label}>
              <TD className="text-muted">{label}</TD>
              <TD className="font-medium text-text">{value}</TD>
            </TR>
          ))}
        </TBody>
      </Table>

      {Object.keys(history.crime_categories).length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-muted">Crime categories</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(history.crime_categories).map(([type, count]) => (
              <Badge key={type} tone="neutral">
                {type} × {count}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
