import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Waypoints, Focus, Tags, Boxes } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { RawGraphNode } from '@/lib/types'
import type { GraphZoomApi } from './GraphView'
import { useLanguage } from '@/providers/LanguageProvider'
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
  const { t } = useLanguage()

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-muted">
          {t('graph_controls.hops', 'Hops')}
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

        <ToggleButton active={clustering} onClick={onToggleClustering} icon={Boxes} label={t('graph_controls.cluster', 'Cluster')} />
        <ToggleButton active={showEdgeLabels} onClick={onToggleEdgeLabels} icon={Tags} label={t('graph_controls.edge_labels', 'Edge labels')} />
        <ToggleButton active={focusMode} onClick={onToggleFocusMode} icon={Focus} label={t('graph_controls.focus_mode', 'Focus mode')} />

        <div className="ml-auto flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.zoomOut()} aria-label={t('graph_controls.zoom_out', 'Zoom out')} title={t('graph_controls.zoom_out', 'Zoom out')}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.zoomIn()} aria-label={t('graph_controls.zoom_in', 'Zoom in')} title={t('graph_controls.zoom_in', 'Zoom in')}>
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.zoomToFit()} aria-label={t('graph_controls.fit_to_screen', 'Fit to screen')} title={t('graph_controls.fit_to_screen', 'Fit to screen')}>
            <Maximize2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => zoomApi?.reset()} aria-label={t('graph_controls.reset_zoom', 'Reset zoom')} title={t('graph_controls.reset_zoom', 'Reset zoom')}>
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
        <Waypoints className="mb-2 h-4 w-4 shrink-0 text-muted" aria-hidden />
        <label className="flex flex-col gap-1 text-xs text-muted">
          {t('graph_controls.from', 'From')}
          <select
            value={pathFrom ?? ''}
            onChange={(e) => onSetPathFrom(e.target.value || null)}
            className="h-8 w-40 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            <option value="">{t('graph_controls.select_a_node', 'Select a node…')}</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          {t('graph_controls.to', 'To')}
          <select
            value={pathTo ?? ''}
            onChange={(e) => onSetPathTo(e.target.value || null)}
            className="h-8 w-40 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
          >
            <option value="">{t('graph_controls.select_a_node', 'Select a node…')}</option>
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
              {pathFound === false
                ? t('graph_controls.no_path', 'No path in loaded data')
                : pathFound
                  ? t('graph_controls.path_highlighted', 'Path highlighted')
                  : ''}
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
              {t('graph_controls.clear', 'Clear')}
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
