import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FolderSearch } from 'lucide-react'
import { Card, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Skeleton } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'
import { useSessions } from '@/lib/queries/sessions'
import { priorityTone, statusTone } from '@/lib/status-tone'
import { formatRelativeTime } from '@/lib/format'
import type { SessionStatus } from '@/lib/types'
import { cn } from '@/lib/cn'

const STATUS_TABS: { label: string; value: SessionStatus | undefined }[] = [
  { label: 'All', value: undefined },
  { label: 'Open', value: 'open' },
  { label: 'Reopened', value: 'reopened' },
  { label: 'Closed', value: 'closed' },
  { label: 'Archived', value: 'archived' },
]

export function InvestigationsListPage() {
  const [status, setStatus] = useState<SessionStatus | undefined>(undefined)
  const [search, setSearch] = useState('')
  const { data, isLoading } = useSessions({ status })

  const filtered = (data ?? []).filter((s) =>
    search.trim()
      ? `${s.title} ${s.session_code}`.toLowerCase().includes(search.trim().toLowerCase())
      : true,
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text">Investigations</h1>
          <p className="text-sm text-muted">All sessions you have access to.</p>
        </div>
        <div className="w-64">
          <Input
            placeholder="Search by title or code…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="flex gap-1 border-b border-border">
        {STATUS_TABS.map((tab) => (
          <Button
            key={tab.label}
            variant="ghost"
            size="sm"
            onClick={() => setStatus(tab.value)}
            className={cn(
              'rounded-none border-b-2',
              status === tab.value ? 'border-accent text-accent' : 'border-transparent',
            )}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      <Card>
        <CardBody>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<FolderSearch className="h-6 w-6" />}
              title="No investigations match"
              description={
                search
                  ? 'Try a different search term or clear the filter.'
                  : 'No sessions exist for this status yet.'
              }
            />
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {filtered.map((session) => (
                <li key={session.id}>
                  <Link
                    to={`/investigations/${session.id}`}
                    className="flex items-center justify-between gap-3 py-3 hover:opacity-80"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-text">{session.title}</p>
                      <p className="font-mono text-xs text-muted">
                        {session.session_code} · updated {formatRelativeTime(session.updated_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Badge tone={priorityTone(session.priority)} className="capitalize">
                        {session.priority}
                      </Badge>
                      <Badge tone={statusTone(session.status)} className="capitalize">
                        {session.status}
                      </Badge>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
