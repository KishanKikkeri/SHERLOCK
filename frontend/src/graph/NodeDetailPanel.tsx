import { X } from 'lucide-react'
import type { RawGraphNode } from '@/lib/types'
import { ENTITY_META } from './entity-meta'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

function fieldLabel(key: string): string {
  const words = key.replaceAll('_', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function fieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

export function NodeDetailPanel({
  node,
  onClose,
  onCenterHere,
}: {
  node: RawGraphNode
  onClose: () => void
  onCenterHere?: () => void
}) {
  const meta = ENTITY_META[node.type]
  const Icon = meta.icon
  const fields = Object.entries(node.data).filter(([key]) => key !== 'id')

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
            style={{ backgroundColor: `var(--${meta.colorVar})` }}
          >
            <Icon className="h-4 w-4" style={{ stroke: '#fff' }} aria-hidden />
          </span>
          <div>
            <p className="text-sm font-medium text-text">{node.label}</p>
            <Badge tone="neutral">{meta.label}</Badge>
          </div>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
        {fields.map(([key, value]) => (
          <div key={key} className="col-span-2 flex items-baseline justify-between gap-2 border-b border-border pb-1.5">
            <dt className="text-xs text-muted">{fieldLabel(key)}</dt>
            <dd className="truncate text-right font-mono text-xs text-text">{fieldValue(value)}</dd>
          </div>
        ))}
      </dl>

      {node.type === 'Person' && onCenterHere && (
        <Button variant="secondary" size="sm" onClick={onCenterHere}>
          Center graph here
        </Button>
      )}
    </div>
  )
}
