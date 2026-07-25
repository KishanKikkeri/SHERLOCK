import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Network } from 'lucide-react'
import { useGraph, useEntityGraph } from '@/lib/queries/graph'
import { GraphView, type GraphZoomApi } from './GraphView'
import { GraphControls } from './GraphControls'
import { GraphLegend } from './GraphLegend'
import { GraphSearch } from './GraphSearch'
import { NodeDetailPanel } from './NodeDetailPanel'
import { ALL_NODE_TYPES } from './entity-meta'
import { shortestPath, edgesOnPath } from './shortest-path'
import { Card, CardBody, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useLanguage } from '@/providers/LanguageProvider'
import type { GraphNodeType, GraphSearchResult, RawGraphNode } from '@/lib/types'

export function GraphPage() {
  const { personId, nodeType, entityId } = useParams<{
    personId?: string
    nodeType?: string
    entityId?: string
  }>()
  const navigate = useNavigate()
  const { t } = useLanguage()

  // Two ways to arrive here: the legacy /graph/:personId (always a
  // Person), or /graph/node/:nodeType/:entityId (Priority 21 — any
  // entity type, reached by selecting a graph search result).
  const activeType: GraphNodeType | undefined = nodeType
    ? (nodeType as GraphNodeType)
    : personId
      ? 'Person'
      : undefined
  const activeId: number | undefined = nodeType
    ? Number(entityId)
    : personId
      ? Number(personId)
      : undefined

  const [hops, setHops] = useState(2)
  const [clustering, setClustering] = useState(false)
  const [showEdgeLabels, setShowEdgeLabels] = useState(false)
  const [focusMode, setFocusMode] = useState(false)
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null)
  const [visibleTypes, setVisibleTypes] = useState<Set<GraphNodeType>>(new Set(ALL_NODE_TYPES))
  const [selectedNode, setSelectedNode] = useState<RawGraphNode | null>(null)
  const [pathFrom, setPathFrom] = useState<string | null>(null)
  const [pathTo, setPathTo] = useState<string | null>(null)
  const [flashNodeId, setFlashNodeId] = useState<string | null>(null)

  const [zoomApi, setZoomApi] = useState<GraphZoomApi | null>(null)

  // Legacy hook stays wired to the Person-only route so existing deep
  // links / callers of useGraph elsewhere are unaffected; the new
  // generic hook covers every other entity type.
  const legacyQuery = useGraph(personId ? activeId : undefined, hops)
  const entityQuery = useEntityGraph(nodeType ? activeType : undefined, nodeType ? activeId : undefined, hops)
  const { data, isLoading, isError } = personId ? legacyQuery : entityQuery

  const nodes = useMemo(() => data?.nodes ?? [], [data])
  const edges = useMemo(() => data?.edges ?? [], [data])

  // Case context for search ranking (Priority 23) — the currently
  // centered Crime id, when the graph is centered on one.
  const caseId = activeType === 'Crime' ? activeId : undefined

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

  // Priority 21 — selecting any graph search result centers the graph,
  // highlights the node, expands its neighbors, opens the detail panel,
  // and flashes it, while preserving the current zoom level (handled by
  // GraphZoomApi.centerOnNode, which pans without changing scale).
  function handleSelectSearchResult(result: GraphSearchResult) {
    if (result.type === 'CrimeType') return // filter suggestion, not a navigable node — see GraphSearch.tsx
    const isSameGraph = activeType === result.type && activeId === result.id
    navigate(`/graph/node/${result.type}/${result.id}`)
    setPathFrom(null)
    setPathTo(null)
    if (isSameGraph) {
      // Already centered here — just re-flash/re-highlight instead of
      // reloading, since the data won't change.
      setFlashNodeId(result.node_key)
      setTimeout(() => setFlashNodeId(null), 1000)
    }
  }

  // Once the (possibly new) subgraph has loaded and the requested node
  // is actually present, pan to it, select it, and flash it — covers
  // both "just navigated to a brand-new center" and "selected a result
  // already inside the currently-loaded graph".
  useEffect(() => {
    if (!data || !activeType || activeId === undefined) return
    const key = `${activeType}:${activeId}`
    const node = nodes.find((n) => n.id === key)
    if (!node) return
    setSelectedNode(node)
    setFlashNodeId(key)
    zoomApi?.centerOnNode(key)
    const t2 = setTimeout(() => setFlashNodeId(null), 1000)
    return () => clearTimeout(t2)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, activeType, activeId])

  if (!activeType || activeId === undefined || Number.isNaN(activeId)) {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">{t('graph_page.title', 'Network graph')}</h1>
          <p className="text-sm text-muted">
            {t('graph_page.subtitle', 'Search any name, vehicle, phone, FIR, org, or location to open its graph.')}
          </p>
        </div>
        <Card>
          <CardBody>
            <EmptyState
              icon={<Network className="h-6 w-6" />}
              title={t('graph_page.no_graph_title', 'No graph loaded')}
              description={t(
                'graph_page.no_graph_description',
                'Search for anything below — a person, vehicle, phone number, FIR, organization, or location — to center a graph on it.',
              )}
            />
            <div className="mx-auto mt-4 max-w-xs">
              <GraphSearch onSelectResult={handleSelectSearchResult} />
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
          <h1 className="text-2xl font-semibold text-text">{t('graph_page.title', 'Network graph')}</h1>
          <p className="font-mono text-xs text-muted">
            {t('graph_page.centered_on', 'Centered on')} {activeType}:{activeId}
          </p>
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
                description={`No ${activeType} with id ${activeId}, or you don't have permission to view it.`}
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
              flashNodeId={flashNodeId}
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
          <GraphSearch caseId={caseId} onSelectResult={handleSelectSearchResult} />
          {selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
              onCenterHere={
                selectedNode.type === 'Person'
                  ? () => centerOnPerson(selectedNode.data.id as number)
                  : () => handleSelectSearchResult({
                      type: selectedNode.type,
                      label: selectedNode.label,
                      id: selectedNode.data.id as number,
                      node_key: selectedNode.id,
                      score: 1,
                    })
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}
