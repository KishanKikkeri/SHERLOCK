import { cn } from '@/lib/cn'

/**
 * Dependency-free horizontal bar chart. The repo's only charting library
 * is d3 (used solely by GraphView.tsx's force-directed graph) — no
 * recharts/chart.js here, so demographic distributions render as plain
 * SVG-free bars built from Tailwind width percentages. Good enough for
 * the count-per-category shape every dashboard chart here actually needs.
 */
export function BarList({
  data,
  colorClassName = 'bg-accent',
  emptyLabel = 'No data in scope.',
}: {
  data: Record<string, number>
  colorClassName?: string
  emptyLabel?: string
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map(([, v]) => v))

  if (entries.length === 0) {
    return <p className="text-xs text-muted">{emptyLabel}</p>
  }

  return (
    <div className="flex flex-col gap-2">
      {entries.map(([label, value]) => (
        <div key={label} className="flex items-center gap-2">
          <span className="w-28 shrink-0 truncate text-xs text-muted" title={label}>
            {label}
          </span>
          <div className="h-4 flex-1 overflow-hidden rounded-sm bg-surface-raised">
            <div
              className={cn('h-full rounded-sm', colorClassName)}
              style={{ width: `${(value / max) * 100}%` }}
            />
          </div>
          <span className="w-8 shrink-0 text-right font-mono text-xs text-text">{value}</span>
        </div>
      ))}
    </div>
  )
}
