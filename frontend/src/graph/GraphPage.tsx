import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Network } from 'lucide-react'
import { useGraph } from '@/lib/queries/graph'
import { GraphView, type GraphZoomApi } from './GraphView'
import { GraphControls } from './GraphControls'
import { GraphLegend } from './GraphLegend'
import { GraphSearch } from './GraphSearch'
import { NodeDetailPanel } from './NodeDetailPanel'
import { ALL_NODE_TYPES } from './entity-meta'
import { shortestPath, edgesOnPath } from './shortest-path'
import { Card, CardBody, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import type { GraphNodeType, RawGraphNode } from '@/lib/types'

export function GraphPage() {
  const { personId } = useParams<{ personId: string }>()
  const navigate = useNavigate()
  const centerId = personId ? Number(personId) : undefined

  const [hops, setHops] = useState(2)
  const [clustering, setClustering] = useState(false)
  const [showEdgeLabels, setShowEdgeLabels] = useState(false)
  const [focusMode, setFocusMode] = useState(false)
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null)
  const [visibleTypes, setVisibleTypes] = useState<Set<GraphNodeType>>(new Set(ALL_NODE_TYPES))
  const [selectedNode, setSelectedNode] = useState<RawGraphNode | null>(null)
  const [pathFrom, setPathFrom] = useState<string | null>(null)
  const [pathTo, setPathTo] = useState<string | null>(null)

  const [zoomApi, setZoomApi] = useState<GraphZoomApi | null>(null)

  const { data, isLoading, isError } = useGraph(centerId, hops)
  const nodes = useMemo(() => data?.nodes ?? [], [data])
  const edges = useMemo(() => data?.edges ?? [], [data])

  const path = useMemo(() => {
    if (!pathFrom || !pathTo) return null
    return shortestPath(edges, pathFrom, pathTo)
  }, [edges, pathFrom, pathTo])
  const pathNodeIds = path ? new Set(path) : null
  const pathEdgeKeys = path ? edgesOnPath(path) : null
  const pathFound = pathFrom && pathTo ? path !== null : null

  function toggleType(type: GraphNodeType) {
    setVisibleTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  function handleSelectNode(node: RawGraphNode | null) {
    setSelectedNode(node)
    if (focusMode) setFocusNodeId(node?.id ?? null)
  }

  function centerOnPerson(id: number) {
    navigate(`/graph/${id}`)
    setSelectedNode(null)
    setFocusNodeId(null)
    setPathFrom(null)
    setPathTo(null)
  }

  if (!centerId) {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">Network graph</h1>
          <p className="text-sm text-muted">Explore relationships around a person.</p>
        </div>
        <Card>
          <CardBody>
            <EmptyState
              icon={<Network className="h-6 w-6" />}
              title="No graph loaded"
              description="Every graph is centered on a person. Enter a person ID below to open one — there's no name search yet (see known limitations)."
            />
            <div className="mx-auto mt-4 max-w-xs">
              <GraphSearch nodes={[]} onSelectNode={() => {}} onCenterOnPerson={centerOnPerson} />
            </div>
          </CardBody>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-56px-48px)] flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Network graph</h1>
          <p className="font-mono text-xs text-muted">Centered on Person:{centerId}</p>
        </div>
      </div>

      <GraphControls
        hops={hops}
        onHopsChange={setHops}
        clustering={clustering}
        onToggleClustering={() => setClustering((c) => !c)}
        showEdgeLabels={showEdgeLabels}
        onToggleEdgeLabels={() => setShowEdgeLabels((v) => !v)}
        focusMode={focusMode}
        onToggleFocusMode={() => {
          setFocusMode((f) => !f)
          setFocusNodeId(null)
        }}
        zoomApi={zoomApi}
        nodes={nodes}
        pathFrom={pathFrom}
        pathTo={pathTo}
        onSetPathFrom={setPathFrom}
        onSetPathTo={setPathTo}
        pathFound={pathFound}
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[1fr_280px]">
        <div className="min-h-[420px] lg:min-h-0">
          {isLoading ? (
            <Skeleton className="h-full w-full" />
          ) : isError || !data ? (
            <Card className="flex h-full items-center justify-center">
              <EmptyState
                icon={<Network className="h-6 w-6" />}
                title="Couldn't load this graph"
                description={`No person with id ${centerId}, or you don't have permission to view it.`}
              />
            </Card>
          ) : (
            <GraphView
              nodes={nodes}
              edges={edges}
              center={data.center}
              visibleTypes={visibleTypes}
              clustering={clustering}
              showEdgeLabels={showEdgeLabels}
              focusNodeId={focusNodeId}
              pathNodeIds={pathNodeIds}
              pathEdgeKeys={pathEdgeKeys}
              selectedNodeId={selectedNode?.id ?? null}
              onSelectNode={handleSelectNode}
              onZoomReady={setZoomApi}
            />
          )}
        </div>

        <div className="flex flex-col gap-3 overflow-y-auto">
          <GraphLegend nodes={nodes} visibleTypes={visibleTypes} onToggleType={toggleType} />
          <GraphSearch nodes={nodes} onSelectNode={handleSelectNode} onCenterOnPerson={centerOnPerson} />
          {selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
              onCenterHere={
                selectedNode.type === 'Person'
                  ? () => centerOnPerson(selectedNode.data.id as number)
                  : undefined
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}
