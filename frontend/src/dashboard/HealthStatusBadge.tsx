import { Activity, AlertTriangle, XCircle } from 'lucide-react'
import { useHealth } from '@/lib/queries/system'
import { Badge } from '@/components/ui/Badge'

export function HealthStatusBadge() {
  const { data, isLoading, isError } = useHealth()

  if (isLoading) {
    return <Badge tone="neutral">Checking…</Badge>
  }

  if (isError || !data) {
    return (
      <Badge tone="critical">
        <XCircle className="h-3 w-3" aria-hidden />
        Backend unreachable
      </Badge>
    )
  }

  if (data.status === 'ok') {
    return (
      <Badge tone="positive">
        <Activity className="h-3 w-3" aria-hidden />
        All systems operational
      </Badge>
    )
  }

  return (
    <Badge tone={data.status === 'down' ? 'critical' : 'warning'}>
      <AlertTriangle className="h-3 w-3" aria-hidden />
      {data.status === 'down' ? 'Backend down' : 'Degraded'}
    </Badge>
  )
}
