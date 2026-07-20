import type { RawGraphEdge } from '@/lib/types'

/**
 * Unweighted BFS shortest path over the currently loaded subgraph.
 * Fine for the graph sizes this UI ever holds in memory (a handful of
 * hops from one person) — see docs/stage-f/03-COMPONENT-ARCHITECTURE.md.
 * Returns the ordered list of node ids on the path (inclusive of
 * `from`/`to`), or null if they aren't connected within the loaded data.
 */
export function shortestPath(
  edges: RawGraphEdge[],
  from: string,
  to: string,
): string[] | null {
  if (from === to) return [from]

  const adjacency = new Map<string, Set<string>>()
  for (const edge of edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set())
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set())
    adjacency.get(edge.source)!.add(edge.target)
    adjacency.get(edge.target)!.add(edge.source)
  }

  const cameFrom = new Map<string, string>()
  const visited = new Set<string>([from])
  const queue: string[] = [from]

  while (queue.length > 0) {
    const current = queue.shift()!
    if (current === to) {
      const path: string[] = [to]
      let node = to
      while (cameFrom.has(node)) {
        node = cameFrom.get(node)!
        path.push(node)
      }
      return path.reverse()
    }
    for (const neighbor of adjacency.get(current) ?? []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor)
        cameFrom.set(neighbor, current)
        queue.push(neighbor)
      }
    }
  }

  return null
}

/** Edge ids (as "source|target" pairs, order-insensitive) that lie on a path. */
export function edgesOnPath(path: string[]): Set<string> {
  const result = new Set<string>()
  for (let i = 0; i < path.length - 1; i++) {
    const [a, b] = [path[i], path[i + 1]].sort()
    result.add(`${a}|${b}`)
  }
  return result
}

export function edgePairKey(source: string, target: string): string {
  const [a, b] = [source, target].sort()
  return `${a}|${b}`
}
