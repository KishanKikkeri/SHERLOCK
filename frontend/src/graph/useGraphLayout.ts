import { useEffect, useMemo, useRef } from 'react'
import * as d3 from 'd3'
import type { RawGraphEdge, RawGraphNode } from '@/lib/types'
import { ALL_NODE_TYPES } from './entity-meta'
import { computeDegreeMap, nodeRadius } from './node-radius'

export interface SimNode extends d3.SimulationNodeDatum {
  id: string
  type: RawGraphNode['type']
  label: string
  degree: number
  radius: number
}

export interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  type: RawGraphEdge['type']
}

/**
 * Custom d3-force clustering force: pulls each node toward a per-type
 * centroid arranged in a ring, so entity types visually group even
 * though they're not physically merged (nodes still repel/collide
 * normally). Strength is tunable so it can be dialed to zero for an
 * instant, cheap "off" — see GraphControls' clustering toggle.
 */
function forceCluster(strength: number, radius: number) {
  let nodes: SimNode[] = []
  const centers = new Map<string, { x: number; y: number }>()

  function force(alpha: number) {
    if (strength <= 0) return
    for (const node of nodes) {
      const c = centers.get(node.type)
      if (!c || node.x === undefined || node.y === undefined) continue
      node.vx = (node.vx ?? 0) - (node.x - c.x) * alpha * strength
      node.vy = (node.vy ?? 0) - (node.y - c.y) * alpha * strength
    }
  }

  force.initialize = (_nodes: SimNode[]) => {
    nodes = _nodes
    const typesPresent = Array.from(new Set(nodes.map((n) => n.type)))
    typesPresent.forEach((type, i) => {
      const angle = (i / typesPresent.length) * 2 * Math.PI
      centers.set(type, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius })
    })
  }

  return force
}

export function useGraphLayout({
  nodes: rawNodes,
  edges: rawEdges,
  center,
  width,
  height,
  clustering,
  onTick,
}: {
  nodes: RawGraphNode[]
  edges: RawGraphEdge[]
  center?: string
  width: number
  height: number
  clustering: boolean
  onTick: (nodes: SimNode[], links: SimLink[]) => void
}) {
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null)
  const nodesRef = useRef<SimNode[]>([])
  const linksRef = useRef<SimLink[]>([])

  const { simNodes, simLinks } = useMemo(() => {
    const degree = computeDegreeMap(rawEdges)
    const prevPositions = new Map(nodesRef.current.map((n) => [n.id, n]))

    const simNodes: SimNode[] = rawNodes.map((n) => {
      const prev = prevPositions.get(n.id)
      const d = degree.get(n.id) ?? 0
      return {
        id: n.id,
        type: n.type,
        label: n.label,
        degree: d,
        radius: nodeRadius(d, n.id === center),
        // Re-use previous position if this node was already on screen,
        // so reheating/filter toggles don't jump the whole layout.
        x: prev?.x,
        y: prev?.y,
        vx: prev?.vx,
        vy: prev?.vy,
      }
    })
    const simLinks: SimLink[] = rawEdges.map((e, i) => ({
      id: `${e.source}|${e.target}|${e.type}|${i}`,
      source: e.source,
      target: e.target,
      type: e.type,
    }))
    return { simNodes, simLinks }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawNodes, rawEdges, center])

  useEffect(() => {
    nodesRef.current = simNodes
    linksRef.current = simLinks

    const simulation = d3
      .forceSimulation<SimNode>(simNodes)
      .force(
        'link',
        d3
          .forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(80)
          .strength(0.25),
      )
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force(
        'collide',
        d3.forceCollide<SimNode>((d) => d.radius + 6),
      )
      .force('cluster', forceCluster(clustering ? 0.12 : 0, Math.min(width, height) / 3))
      .on('tick', () => onTick(nodesRef.current, linksRef.current))

    simulationRef.current = simulation

    return () => {
      simulation.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simNodes, simLinks, width, height])

  // Toggling clustering shouldn't rebuild the whole simulation — just
  // swap the force's strength and reheat gently.
  useEffect(() => {
    const sim = simulationRef.current
    if (!sim) return
    sim.force('cluster', forceCluster(clustering ? 0.12 : 0, Math.min(width, height) / 3))
    sim.alpha(0.3).restart()
  }, [clustering, width, height])

  return {
    reheat: () => simulationRef.current?.alpha(0.6).restart(),
    getNode: (id: string) => nodesRef.current.find((n) => n.id === id),
    unpinNode: (id: string) => {
      const node = nodesRef.current.find((n) => n.id === id)
      if (node) {
        node.fx = null
        node.fy = null
        simulationRef.current?.alpha(0.4).restart()
      }
    },
    allTypes: ALL_NODE_TYPES,
  }
}
