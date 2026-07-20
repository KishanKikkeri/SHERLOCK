import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Waypoints, Focus, Tags, Boxes } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { RawGraphNode } from '@/lib/types'
import type { GraphZoomApi } from './GraphView'
import { cn } from '@/lib/cn'

interface GraphControlsProps {
  hops: number
  onHopsChange: (hops: number) => void
  clustering: boolean
  onToggleClustering: () => void
  showEdgeLabels: boolean
  onToggleEdgeLabels: () => void
  focusMode: boolean
  onToggleFocusMode: () => void
  zoomApi: GraphZoomApi | null
  nodes: RawGraphNode[]
  pathFrom: string | null
  pathTo: string | null
  onSetPathFrom: (id: string | null) => void
  onSetPathTo: (id: string | null) => void
  pathFound: boolean | null
}

function ToggleButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: typeof Focus
  label: string
}) {
  return (
    <Button
      variant={active ? 'primary' : 'secondary'}
      size="sm"
      onClick={onClick}
      aria-pressed={active}
      title={label}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {label}
    </Button>
  )
}

export function GraphControls({
  hops,
  onHopsChange,
  clustering,
  onToggleClustering,
  showEdgeLabels,
  onToggleEdgeLabels,
  focusMode,
  onToggleFocusMode,
  zoomApi,
  nodes,
  pathFrom,
  pathTo,
  onSetPathFrom,
  onSetPathTo,
  pathFound,
}: GraphControlsProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-muted">
          Hops
          <select
            value={hops}
            onChange={(e) => onHopsChange(Number(e.target.value))}
            className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            {[1, 2, 3, 4, 5].map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
        </label>

        <ToggleButton active={clustering} onClick={onToggleClustering} icon={Boxes} label="Cluster" />
        <ToggleButton active={showEdgeLabels} onClick={onToggleEdgeLabels} icon={Tags} label="Edge labels" />
        <ToggleButton active={focusMode} onClick={onToggleFocusMode} icon={Focus} label="Focus mode" />

        <div className="ml-auto flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.zoomOut()} aria-label="Zoom out" title="Zoom out">
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.zoomIn()} aria-label="Zoom in" title="Zoom in">
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.zoomToFit()} aria-label="Fit to screen" title="Fit to screen">
            <Maximize2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.reset()} aria-label="Reset zoom" title="Reset zoom">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
        <Waypoints className="mb-2 h-4 w-4 shrink-0 text-muted" aria-hidden />
        <label className="flex flex-col gap-1 text-xs text-muted">
          From
          <select
            value={pathFrom ?? ''}
            onChange={(e) => onSetPathFrom(e.target.value || null)}
            className="h-8 w-40 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            <option value="">Select a node…</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          To
          <select
            value={pathTo ?? ''}
            onChange={(e) => onSetPathTo(e.target.value || null)}
            className="h-8 w-40 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            <option value="">Select a node…</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </select>
        </label>
        {pathFrom && pathTo && (
          <>
            <span
              className={cn(
                'mb-2 text-xs',
                pathFound === false ? 'text-critical' : pathFound ? 'text-positive' : 'text-muted',
              )}
            >
              {pathFound === false ? 'No path in loaded data' : pathFound ? 'Path highlighted' : ''}
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="mb-1"
              onClick={() => {
                onSetPathFrom(null)
                onSetPathTo(null)
              }}
            >
              Clear
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
