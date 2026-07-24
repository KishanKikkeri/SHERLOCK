import type { GraphNodeType, RawGraphNode } from '@/lib/types'
import { ENTITY_META, entityLabel } from './entity-meta'
import { useLanguage } from '@/providers/LanguageProvider'
import { cn } from '@/lib/cn'

export function GraphLegend({
  nodes,
  visibleTypes,
  onToggleType,
}: {
  nodes: RawGraphNode[]
  visibleTypes: Set<GraphNodeType>
  onToggleType: (type: GraphNodeType) => void
}) {
  const { t } = useLanguage()
  const counts = new Map<GraphNodeType, number>()
  for (const n of nodes) counts.set(n.type, (counts.get(n.type) ?? 0) + 1)

  const typesPresent = Array.from(counts.keys()).sort((a, b) =>
    entityLabel(a, t).localeCompare(entityLabel(b, t)),
  )

  if (typesPresent.length === 0) return null

  return (
    <fieldset className="flex flex-wrap gap-1.5 border-0 p-0 m-0">
      <legend className="sr-only">Filter by entity type</legend>
      {typesPresent.map((type) => {
        const meta = ENTITY_META[type]
        const isVisible = visibleTypes.has(type)
        return (
          <button
            key={type}
            type="button"
            onClick={() => onToggleType(type)}
            aria-pressed={isVisible}
            className={cn(
              'flex cursor-pointer items-center gap-1.5 rounded-full border px-2 py-1 text-xs transition-colors duration-150',
              'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
              isVisible
                ? 'border-border bg-surface-raised text-text'
                : 'border-border/50 bg-transparent text-muted opacity-50',
            )}
          >
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: `var(--${meta.colorVar})` }}
              aria-hidden
            />
            {entityLabel(type, t)}
            <span className="font-mono text-muted">{counts.get(type)}</span>
          </button>
        )
      })}
    </fieldset>
  )
}
