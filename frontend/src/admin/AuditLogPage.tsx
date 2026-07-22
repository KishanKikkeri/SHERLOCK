import { useState } from 'react'
import { ScrollText } from 'lucide-react'
import { Card, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { Input } from '@/components/ui/Input'
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/Table'
import { useAuditLog } from '@/lib/queries/governance'
import { formatRelativeTime } from '@/lib/format'

export function AuditLogPage() {
  const [action, setAction] = useState('')
  const { data, isLoading } = useAuditLog({ action: action || undefined })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Audit log</h1>
          <p className="text-sm text-muted">Every recorded login, permission check, and export.</p>
        </div>
        <div className="w-56">
          <Input
            placeholder="Filter by action…"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
        </div>
      </div>

      <Card>
        <CardBody className="p-0">
          {isLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data || data.length === 0 ? (
            <EmptyState
              icon={<ScrollText className="h-6 w-6" />}
              title="No audit entries"
              description="Nothing matches this filter yet."
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>When</TH>
                  <TH>Actor</TH>
                  <TH>Action</TH>
                  <TH>Target</TH>
                  <TH>Result</TH>
                </TR>
              </THead>
              <TBody>
                {data.map((entry) => (
                  <TR key={entry.id}>
                    <TD className="font-mono text-xs text-muted">
                      {formatRelativeTime(entry.created_at)}
                    </TD>
                    <TD className="text-text">{entry.username ?? '—'}</TD>
                    <TD className="font-mono text-xs text-text">{entry.action}</TD>
                    <TD className="text-xs text-muted">{entry.target ?? '—'}</TD>
                    <TD>
                      <Badge tone={entry.success ? 'positive' : 'critical'}>
                        {entry.success ? 'Success' : 'Failed'}
                      </Badge>
                    </TD>
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
