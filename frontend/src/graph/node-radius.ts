import type { RawGraphEdge } from '@/lib/types'

export function computeDegreeMap(edges: RawGraphEdge[]): Map<string, number> {
  const degree = new Map<string, number>()
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
  }
  return degree
}

/** Single formula used by both the physics (collision radius) and the
 * rendered circle, so they never visually disagree. */
export function nodeRadius(degree: number, isCenter: boolean): number {
  if (isCenter) return 16
  return Math.min(8 + degree * 1.5, 20)
}
