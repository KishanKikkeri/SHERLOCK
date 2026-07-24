import { ShieldCheck } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'
import { useRetentionPolicy, useRunRetentionSweep } from '@/lib/queries/governance'
import { useLanguage } from '@/providers/LanguageProvider'

export function GovernancePage() {
  const { data: policy, isLoading } = useRetentionPolicy()
  const runSweep = useRunRetentionSweep()
  const { t } = useLanguage()

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-text">{t('admin_pages.governance_title', 'Governance')}</h1>
        <p className="text-sm text-muted">{t('admin_pages.governance_subtitle', 'Data retention policy for this deployment.')}</p>
      </div>

      <Card>
        <CardHeader
          title={t('admin_pages.retention_policy', 'Retention policy')}
          action={
            <ShieldCheck className="h-4 w-4 text-accent" aria-hidden />
          }
        />
        <CardBody>
          {isLoading || !policy ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-muted">Investigation sessions</dt>
                <dd className="font-mono text-text">{policy.investigation_sessions_days} days</dd>
              </div>
              <div>
                <dt className="text-muted">Conversation turns</dt>
                <dd className="font-mono text-text">{policy.conversation_turns_days} days</dd>
              </div>
              <div>
                <dt className="text-muted">Audit log</dt>
                <dd className="font-mono text-text">{policy.audit_log_days} days</dd>
              </div>
              <div>
                <dt className="text-muted">Deletion mode</dt>
                <dd className="text-text">{policy.deletion_mode}</dd>
              </div>
            </dl>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardBody className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-text">Run archival sweep now</p>
            <p className="text-xs text-muted">
              Idempotent — safe to run more than once. Applies the policy above immediately
              instead of waiting for the next scheduled run.
            </p>
          </div>
          <Button
            variant="secondary"
            isLoading={runSweep.isPending}
            onClick={() => runSweep.mutate()}
          >
            Run now
          </Button>
        </CardBody>
      </Card>
    </div>
  )
}
