import { Link } from 'react-router-dom'
import { Network } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import type { OffenderNetworkProfile } from '@/lib/types'

export function NetworkSummary({ network, personId }: { network: OffenderNetworkProfile; personId: number }) {
  const metrics = network.graph_metrics

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="Associates" value={network.associate_count} />
        <Stat label="Organizations" value={network.organizations.length} />
        <Stat label="Financial links" value={network.financial_links.length} />
        <Stat label="Repeat collaborators" value={network.repeat_collaborators.length} />
      </div>

      {metrics.available ? (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Stat label="PageRank" value={metrics.pagerank} />
          <Stat label="Degree centrality" value={metrics.degree_centrality} />
          <Stat label="Community size" value={metrics.community_size} />
          <Stat label="Influence score" value={metrics.influence_score} />
        </div>
      ) : (
        <p className="text-xs text-subtle">{metrics.reason}</p>
      )}

      {network.organizations.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted">Organization ties</p>
          <div className="flex flex-wrap gap-1.5">
            {network.organizations.map((o) => (
              <Badge key={o.organization_id} tone="info">
                {o.name ?? `org_${o.organization_id}`}
                {o.role ? ` — ${o.role}` : ''}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <Link
        to={`/graph/${personId}`}
        className="inline-flex w-fit items-center gap-2 rounded-md border border-border bg-surface-raised px-3 py-1.5 text-xs font-medium text-text transition-colors hover:border-border-strong hover:bg-surface-raised/70"
      >
        <Network className="h-3.5 w-3.5" /> View full network graph
      </Link>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised px-3 py-2">
      <p className="text-lg font-semibold text-text">{value}</p>
      <p className="text-xs text-muted">{label}</p>
    </div>
  )
}
