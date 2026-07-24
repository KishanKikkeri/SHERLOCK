import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { GraphNodeType, RawGraphEdge, RawGraphNode } from '@/lib/types'
import { ENTITY_META, edgeLabel, entityLabel } from './entity-meta'
import { useLanguage } from '@/providers/LanguageProvider'
import { useGraphLayout, type SimLink, type SimNode } from './useGraphLayout'
import { computeDegreeMap, nodeRadius } from './node-radius'
import { edgePairKey } from './shortest-path'
import { cn } from '@/lib/cn'

export interface GraphZoomApi {
  zoomIn: () => void
  zoomOut: () => void
  zoomToFit: () => void
  reset: () => void
}

interface GraphViewProps {
  nodes: RawGraphNode[]
  edges: RawGraphEdge[]
  center?: string
  visibleTypes: Set<GraphNodeType>
  clustering: boolean
  showEdgeLabels: boolean
  focusNodeId: string | null
  pathNodeIds: Set<string> | null
  pathEdgeKeys: Set<string> | null
  selectedNodeId: string | null
  onSelectNode: (node: RawGraphNode | null) => void
  onZoomReady: (api: GraphZoomApi | null) => void
}

const MIN_ZOOM = 0.15
const MAX_ZOOM = 4

export function GraphView({
  nodes,
  edges,
  center,
  visibleTypes,
  clustering,
  showEdgeLabels,
  focusNodeId,
  pathNodeIds,
  pathEdgeKeys,
  selectedNodeId,
  onSelectNode,
  onZoomReady,
}: GraphViewProps) {
  const { t } = useLanguage()
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const zoomLayerRef = useRef<SVGGElement>(null)

  const nodeElsRef = useRef(new Map<string, SVGGElement>())
  const linkElsRef = useRef(new Map<string, SVGLineElement>())
  const linkLabelElsRef = useRef(new Map<string, SVGTextElement>())

  const [dims, setDims] = useState({ width: 800, height: 600 })
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)
  const degreeMap = computeDegreeMap(edges)

  // Track container size so the simulation centers correctly and stays
  // correct across sidebar toggles / window resizes.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) setDims({ width, height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const visibleNodeIds = new Set(
    nodes.filter((n) => visibleTypes.has(n.type)).map((n) => n.id),
  )
  const isEdgeVisible = (e: RawGraphEdge) =>
    visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)

  const handleTick = (simNodes: SimNode[], simLinks: SimLink[]) => {
    for (const n of simNodes) {
      const el = nodeElsRef.current.get(n.id)
      if (!el || n.x === undefined || n.y === undefined) continue
      el.setAttribute('transform', `translate(${n.x},${n.y})`)
    }
    for (const l of simLinks) {
      const source = l.source as unknown as SimNode
      const target = l.target as unknown as SimNode
      if (typeof source === 'string' || typeof target === 'string') continue
      const lineEl = linkElsRef.current.get(l.id)
      if (lineEl && source.x !== undefined && target.x !== undefined) {
        lineEl.setAttribute('x1', String(source.x))
        lineEl.setAttribute('y1', String(source.y))
        lineEl.setAttribute('x2', String(target.x))
        lineEl.setAttribute('y2', String(target.y))
      }
      const labelEl = linkLabelElsRef.current.get(l.id)
      if (labelEl && source.x !== undefined && target.x !== undefined) {
        labelEl.setAttribute('x', String((source.x + target.x) / 2))
        labelEl.setAttribute('y', String((source.y! + target.y!) / 2))
      }
    }
  }

  const { reheat, getNode, unpinNode } = useGraphLayout({
    nodes,
    edges,
    center,
    width: dims.width,
    height: dims.height,
    clustering,
    onTick: handleTick,
  })

  // Zoom/pan setup — imperative, transform applied directly to the DOM
  // node so panning/zooming never triggers a React re-render.
  useEffect(() => {
    if (!svgRef.current || !zoomLayerRef.current) return
    const svg = d3.select(svgRef.current)
    const layer = zoomLayerRef.current

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([MIN_ZOOM, MAX_ZOOM])
      .on('zoom', (event) => {
        layer.setAttribute('transform', event.transform.toString())
      })

    svg.call(zoom)

    const api: GraphZoomApi = {
      zoomIn: () => svg.transition().duration(200).call(zoom.scaleBy, 1.4),
      zoomOut: () => svg.transition().duration(200).call(zoom.scaleBy, 1 / 1.4),
      zoomToFit: () => {
        const bounds = svgRef.current
          ?.querySelector<SVGGraphicsElement>('[data-graph-layer]')
          ?.getBBox()
        if (!bounds || bounds.width === 0) return
        const scale = Math.min(
          MAX_ZOOM,
          0.9 / Math.max(bounds.width / dims.width, bounds.height / dims.height),
        )
        const tx = dims.width / 2 - scale * (bounds.x + bounds.width / 2)
        const ty = dims.height / 2 - scale * (bounds.y + bounds.height / 2)
        svg
          .transition()
          .duration(300)
          .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale))
      },
      reset: () => svg.transition().duration(200).call(zoom.transform, d3.zoomIdentity),
    }
    onZoomReady(api)

    return () => {
      onZoomReady(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dims.width, dims.height])

  // Drag to reposition + pin a node; double-click releases the pin.
  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)

    const drag = d3
      .drag<SVGGElement, unknown>()
      .subject(function () {
        const id = this.getAttribute('data-node-id')
        return id ? getNode(id) : null
      })
      .on('start', () => reheat())
      .on('drag', (event) => {
        event.subject.fx = event.x
        event.subject.fy = event.y
      })

    svg.selectAll<SVGGElement, unknown>('[data-node-id]').call(drag)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, dims.width, dims.height])

  const visibleEdges = edges.filter(isEdgeVisible)

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden rounded-lg border border-border bg-surface" style={{ backgroundImage: 'radial-gradient(circle, var(--border-subtle) 1px, transparent 1px)', backgroundSize: '24px 24px' }}>
      {/* oxlint-disable-next-line jsx-a11y/no-static-element-interactions -- this is a
          drawing canvas, not a control; its onClick is a supplementary "click empty
          space to deselect" convenience, with a real keyboard equivalent (Escape,
          below). The actual interactive content is the individually-focusable child
          nodes, each already carrying role="button"/tabIndex. Giving the canvas itself
          a role would misrepresent it to assistive tech. */}
      <svg
        ref={svgRef}
        width={dims.width}
        height={dims.height}
        className="cursor-grab active:cursor-grabbing"
        onClick={(e) => {
          if (e.target === svgRef.current) onSelectNode(null)
        }}
        onKeyDown={(e) => {
          // Keyboard equivalent of clicking empty canvas to deselect —
          // nodes are individually focusable/keyboard-activatable (see
          // role="button" below), Escape clears selection the same way
          // a background click does for mouse users.
          if (e.key === 'Escape') onSelectNode(null)
        }}
      >
        <g ref={zoomLayerRef} data-graph-layer>
          <g className="edges">
            {visibleEdges.map((e, i) => {
              const id = `${e.source}|${e.target}|${e.type}|${i}`
              const onPath = pathEdgeKeys?.has(edgePairKey(e.source, e.target)) ?? false
              const dimmed =
                focusNodeId !== null &&
                e.source !== focusNodeId &&
                e.target !== focusNodeId
              const highlighted =
                hoveredNodeId !== null &&
                (e.source === hoveredNodeId || e.target === hoveredNodeId)
              return (
                <g key={id}>
                  <line
                    ref={(el) => {
                      if (el) linkElsRef.current.set(id, el)
                      else linkElsRef.current.delete(id)
                    }}
                    className={cn(
                      'transition-opacity duration-150',
                      onPath || highlighted ? 'stroke-accent' : 'stroke-border',
                      dimmed ? 'opacity-10' : onPath || highlighted ? 'opacity-100' : 'opacity-60',
                    )}
                    strokeWidth={onPath || highlighted ? 2.5 : 1.25}
                  />
                  {showEdgeLabels && !dimmed && (
                    <text
                      ref={(el) => {
                        if (el) linkLabelElsRef.current.set(id, el)
                        else linkLabelElsRef.current.delete(id)
                      }}
                      textAnchor="middle"
                      className="pointer-events-none select-none fill-muted font-mono text-[8px]"
                    >
                      {edgeLabel(e.type)}
                    </text>
                  )}
                </g>
              )
            })}
          </g>

          <g className="nodes">
            {nodes
              .filter((n) => visibleNodeIds.has(n.id))
              .map((n) => {
                const meta = ENTITY_META[n.type]
                const Icon = meta.icon
                const isCenter = n.id === center
                const isSelected = n.id === selectedNodeId
                const onPath = pathNodeIds?.has(n.id) ?? false
                const dimmed =
                  focusNodeId !== null &&
                  n.id !== focusNodeId &&
                  !edges.some(
                    (e) =>
                      (e.source === focusNodeId && e.target === n.id) ||
                      (e.target === focusNodeId && e.source === n.id),
                  )
                const radius = nodeRadius(degreeMap.get(n.id) ?? 0, isCenter)
                const isHovered = n.id === hoveredNodeId

                return (
                  <g
                    key={n.id}
                    ref={(el) => {
                      if (el) nodeElsRef.current.set(n.id, el)
                      else nodeElsRef.current.delete(n.id)
                    }}
                    data-node-id={n.id}
                    // <g> can't be a native <button> (SVG grouping element, not HTML);
                    // role="button" + tabIndex + onKeyDown is the standard accessible
                    // pattern for interactive SVG graphics.
                    // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
                    role="button"
                    tabIndex={0}
                    aria-label={`${entityLabel(n.type, t)}: ${n.label}`}
                    className={cn(
                      'cursor-pointer outline-none transition-opacity duration-150',
                      dimmed ? 'opacity-15' : 'opacity-100',
                    )}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectNode(n)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onSelectNode(n)
                      }
                    }}
                    onDoubleClick={(e) => {
                      e.stopPropagation()
                      unpinNode(n.id)
                    }}
                    onMouseEnter={() => setHoveredNodeId(n.id)}
                    onMouseLeave={() => setHoveredNodeId((cur) => (cur === n.id ? null : cur))}
                    onFocus={() => setHoveredNodeId(n.id)}
                    onBlur={() => setHoveredNodeId((cur) => (cur === n.id ? null : cur))}
                  >
                    {(onPath || isSelected || isHovered) && (
                      <circle
                        r={radius + 4}
                        className={cn('fill-none', onPath ? 'stroke-accent' : 'stroke-ring')}
                        strokeWidth={2}
                      />
                    )}
                    <circle
                      r={radius}
                      style={{ fill: `var(--${meta.colorVar})` }}
                      className={cn(
                        'stroke-surface',
                        isCenter ? 'stroke-[3px]' : 'stroke-2',
                      )}
                    />
                    <Icon
                      x={-7}
                      y={-7}
                      width={14}
                      height={14}
                      className="pointer-events-none"
                      style={{ stroke: '#fff' }}
                      strokeWidth={2.5}
                    />
                    <text
                      y={radius + 12}
                      textAnchor="middle"
                      className="pointer-events-none select-none fill-text text-[10px] font-medium"
                    >
                      {n.label.length > 18 ? `${n.label.slice(0, 18)}…` : n.label}
                    </text>
                  </g>
                )
              })}
          </g>
        </g>
      </svg>
    </div>
  )
}
