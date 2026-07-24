import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FolderSearch } from 'lucide-react'
import { Card, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Skeleton } from '@/components/ui/Skeleton'
import { Tabs } from '@/components/ui/Tabs'
import { useSessions } from '@/lib/queries/sessions'
import { priorityTone, statusTone } from '@/lib/status-tone'
import { formatRelativeTime } from '@/lib/format'
import type { SessionStatus } from '@/lib/types'
import { useLanguage } from '@/providers/LanguageProvider'
import { cn } from '@/lib/cn'

export function InvestigationsListPage() {
  const { t } = useLanguage()
  const [status, setStatus] = useState<SessionStatus | undefined>(undefined)
  const [search, setSearch] = useState('')
  const { data, isLoading } = useSessions({ status })

  const STATUS_TABS: { label: string; value: SessionStatus | undefined }[] = [
    { label: t('investigations.tab_all', 'All'), value: undefined },
    { label: t('investigations.tab_open', 'Open'), value: 'open' },
    { label: t('investigations.tab_reopened', 'Reopened'), value: 'reopened' },
    { label: t('investigations.tab_closed', 'Closed'), value: 'closed' },
    { label: t('investigations.tab_archived', 'Archived'), value: 'archived' },
  ]

  const filtered = (data ?? []).filter((s) =>
    search.trim()
      ? `${s.title} ${s.session_code}`.toLowerCase().includes(search.trim().toLowerCase())
      : true,
  )

  const tabValue = status ?? 'all'

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">{t('investigations.title', 'Investigations')}</h1>
          <p className="mt-1 text-sm text-muted">
            {t('investigations.subtitle', 'All sessions you have access to.')}
          </p>
        </div>
        <div className="w-64">
          <Input
            placeholder={t('investigations.search_placeholder', 'Search by title or code…')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Tabs
        items={STATUS_TABS.map((s) => ({
          label: s.label,
          value: s.value ?? 'all',
          count: s.value === undefined ? data?.length : data?.filter((sess) => sess.status === s.value).length,
        }))}
        value={tabValue}
        onChange={(v) => setStatus(v === 'all' ? undefined : v as SessionStatus)}
      />

      <Card>
        <CardBody className="p-0">
          {isLoading ? (
            <div className="flex flex-col gap-2 p-5">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<FolderSearch className="h-6 w-6" />}
              title={t('investigations.no_match_title', 'No investigations match')}
              description={
                search
                  ? t('investigations.no_match_with_search', 'Try a different search term or clear the filter.')
                  : t('investigations.no_match_without_search', 'No sessions exist for this status yet.')
              }
            />
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {filtered.map((session) => (
                <li key={session.id}>
                  <Link
                    to={`/investigations/${session.id}`}
                    className={cn(
                      'flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-surface-raised/50',
                      session.priority === 'critical' && 'border-l-2 border-l-critical',
                    )}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-text">{session.title}</p>
                      <p className="font-mono text-xs text-muted">
                        {session.session_code} · {t('investigations.updated', 'updated')} {formatRelativeTime(session.updated_at)}
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
