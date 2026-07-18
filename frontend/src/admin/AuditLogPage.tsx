import { useState } from 'react'
import { ScrollText } from 'lucide-react'
import { Card, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { Input } from '@/components/ui/Input'
import { useAuditLog } from '@/lib/queries/governance'
import { formatRelativeTime } from '@/lib/format'

export function AuditLogPage() {
  const [action, setAction] = useState('')
  const { data, isLoading } = useAuditLog({ action: action || undefined })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text">Audit log</h1>
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
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-4 py-2 font-medium">When</th>
                  <th className="px-4 py-2 font-medium">Actor</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Target</th>
                  <th className="px-4 py-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.map((entry) => (
                  <tr key={entry.id}>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted">
                      {formatRelativeTime(entry.created_at)}
                    </td>
                    <td className="px-4 py-2.5 text-text">{entry.username ?? '—'}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-text">{entry.action}</td>
                    <td className="px-4 py-2.5 text-xs text-muted">{entry.target ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone={entry.success ? 'positive' : 'critical'}>
                        {entry.success ? 'Success' : 'Failed'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
