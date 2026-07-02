// ─────────────────────────────────────────────────────────────────
// SHERLOCK — Intelligence Graph Panel (center)
// D3 force graph with animated node creation.
// Nodes appear one-by-one as the investigation builds the graph.
// ─────────────────────────────────────────────────────────────────

import { useEffect, useRef, useState } from 'react';
import type { GraphData, GraphNode, NodeType } from '../../lib/types';
import styles from './GraphPanel.module.css';

// ── Node colour by entity type ────────────────────────────────
const NODE_COLORS: Record<NodeType | string, string> = {
  Person:      '#38BDF8',
  Crime:       '#EF4444',
  FIR:         '#EC4899',
  Location:    '#10B981',
  BankAccount: '#F59E0B',
  Phone:       '#8B5CF6',
  Vehicle:     '#6B7280',
  Transaction: '#F97316',
};

const NODE_RADIUS: Record<NodeType | string, number> = {
  Person:      14,
  Crime:       10,
  FIR:          8,
  Location:    10,
  BankAccount: 10,
  Phone:        8,
  Vehicle:      8,
  Transaction:  8,
};

// ── Mini legend ───────────────────────────────────────────────
const LEGEND_ITEMS: { type: string; label: string }[] = [
  { type: 'Person',      label: 'Person' },
  { type: 'Crime',       label: 'Crime' },
  { type: 'Location',    label: 'Location' },
  { type: 'BankAccount', label: 'Account' },
  { type: 'FIR',         label: 'FIR' },
];

interface Props {
  graphData: GraphData | null;
  isLoading: boolean;
  personId: number | null;
}

export function GraphPanel({ graphData, isLoading, personId }: Props) {
  const svgRef   = useRef<SVGSVGElement>(null);
  const gRef     = useRef<SVGGElement | null>(null);
  const simRef   = useRef<unknown>(null);
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);

  useEffect(() => {
    if (!graphData || !svgRef.current) return;

    // Lazy-load D3 so it doesn't block initial render
    import('d3').then((d3) => {
      const svg = d3.select(svgRef.current!);
      svg.selectAll('*').remove();

      const W = svgRef.current!.clientWidth  || 600;
      const H = svgRef.current!.clientHeight || 400;

      // Zoom layer
      const g = svg.append('g');
      gRef.current = g.node();

      svg.call(
        d3.zoom<SVGSVGElement, unknown>()
          .scaleExtent([0.25, 4])
          .on('zoom', (e) => g.attr('transform', e.transform)),
      );

      // Arrow markers per colour
      const defs = svg.append('defs');
      Object.entries(NODE_COLORS).forEach(([type, color]) => {
        defs.append('marker')
          .attr('id', `arrow-${type}`)
          .attr('viewBox', '0 -4 8 8')
          .attr('refX', 22).attr('refY', 0)
          .attr('markerWidth', 5).attr('markerHeight', 5)
          .attr('orient', 'auto')
          .append('path').attr('d', 'M0,-4L8,0L0,4')
          .attr('fill', color).attr('opacity', 0.5);
      });

      // Clone data so D3 can mutate positions. SimulationNodeDatum adds x/y/fx/fy.
      type SimNode = GraphNode & d3.SimulationNodeDatum;
      const nodes: SimNode[] = graphData.nodes.map((n) => ({ ...n }));
      const edges = graphData.edges.map((e) => ({ ...e }));

      const nodeById = new Map(nodes.map((n) => [n.id, n]));
      const links = edges
        .map((e) => ({ source: nodeById.get(e.source)!, target: nodeById.get(e.target)!, type: e.type }))
        .filter((e) => e.source && e.target);

      // Force simulation
      const sim = d3.forceSimulation<SimNode>(nodes)
        .force('link', d3.forceLink(links).id((d: unknown) => (d as GraphNode).id).distance(90).strength(0.4))
        .force('charge', d3.forceManyBody().strength(-260))
        .force('center', d3.forceCenter(W / 2, H / 2))
        .force('collision', d3.forceCollide((d: unknown) => NODE_RADIUS[(d as GraphNode).type] + 6));

      simRef.current = sim;

      // Edges
      const linkSel = g.append('g').attr('class', 'links')
        .selectAll('line').data(links).enter().append('line')
        .attr('stroke', (d) => NODE_COLORS[d.type?.split('_')[0] ?? ''] ?? '#1F2937')
        .attr('stroke-width', 1)
        .attr('stroke-opacity', 0)
        .attr('marker-end', (d) => `url(#arrow-${d.source.type})`)
        .transition().duration(600).attr('stroke-opacity', 0.25);

      // Nodes
      const nodeSel = g.append('g').attr('class', 'nodes')
        .selectAll('g').data(nodes).enter().append('g')
        .attr('class', 'node')
        .call(
          d3.drag<SVGGElement, SimNode>()
            .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }),
        );

      // Circle with entrance animation
      nodeSel.append('circle')
        .attr('r', 0)
        .attr('fill', (d) => NODE_COLORS[d.type] ?? '#4B5563')
        .attr('fill-opacity', 0.85)
        .attr('stroke', (d) => d.id === graphData.center ? '#fff' : NODE_COLORS[d.type] ?? '#4B5563')
        .attr('stroke-width', (d) => d.id === graphData.center ? 2 : 0)
        .transition().duration(400).delay((_, i) => i * 40)
        .attr('r', (d) => NODE_RADIUS[d.type] ?? 8);

      // Type initial
      nodeSel.append('text')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'central')
        .attr('fill', '#0B1220')
        .attr('font-size', '8px')
        .attr('font-weight', '700')
        .attr('font-family', 'Inter, sans-serif')
        .attr('pointer-events', 'none')
        .attr('opacity', 0)
        .text((d) => d.type[0])
        .transition().duration(300).delay((_, i) => i * 40 + 200)
        .attr('opacity', 1);

      // Label below node
      nodeSel.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', (d) => (NODE_RADIUS[d.type] ?? 8) + 12)
        .attr('fill', '#94A3B8')
        .attr('font-size', '9px')
        .attr('font-family', 'Inter, sans-serif')
        .attr('pointer-events', 'none')
        .attr('opacity', 0)
        .text((d) => {
          const lbl = d.label ?? '';
          return lbl.length > 16 ? lbl.slice(0, 16) + '…' : lbl;
        })
        .transition().duration(300).delay((_, i) => i * 40 + 300)
        .attr('opacity', 1);

      // Tooltip on hover
      nodeSel
        .on('mouseenter', function (_, d) {
          d3.select(this).select('circle')
            .transition().duration(120).attr('r', (NODE_RADIUS[d.type] ?? 8) + 3);
        })
        .on('mouseleave', function (_, d) {
          d3.select(this).select('circle')
            .transition().duration(120).attr('r', NODE_RADIUS[d.type] ?? 8);
        });

      // Tick
      sim.on('tick', () => {
        linkSel
          .attr('x1', (d) => (d.source as SimNode).x!)
          .attr('y1', (d) => (d.source as SimNode).y!)
          .attr('x2', (d) => (d.target as SimNode).x!)
          .attr('y2', (d) => (d.target as SimNode).y!);
        nodeSel.attr('transform', (d) => `translate(${d.x},${d.y})`);
      });

      sim.on('end', () => {
        setNodeCount(nodes.length);
        setEdgeCount(edges.length);
      });
    });

    return () => {
      if (simRef.current) {
        (simRef.current as { stop: () => void }).stop();
      }
    };
  }, [graphData]);

  return (
    <div className={styles.root}>
      {/* Panel header */}
      <div className={styles.header}>
        <span className={styles.label}>Intelligence Graph</span>
        {nodeCount > 0 && (
          <span className={styles.counts}>
            {nodeCount} nodes · {edgeCount} edges
          </span>
        )}
      </div>

      {/* SVG canvas */}
      <div className={styles.canvas}>
        {!personId && !isLoading && (
          <div className={styles.empty}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.2">
              <circle cx="12" cy="12" r="3" />
              <circle cx="4"  cy="6"  r="2" />
              <circle cx="20" cy="6"  r="2" />
              <circle cx="4"  cy="18" r="2" />
              <circle cx="20" cy="18" r="2" />
              <line x1="6"  y1="6.8"  x2="10" y2="10.5" />
              <line x1="18" y1="6.8"  x2="14" y2="10.5" />
              <line x1="6"  y1="17.2" x2="10" y2="13.5" />
              <line x1="18" y1="17.2" x2="14" y2="13.5" />
            </svg>
            <p>Crime Intelligence Graph</p>
            <p className={styles.emptyHint}>Populated after network analysis</p>
          </div>
        )}

        {isLoading && (
          <div className={styles.empty}>
            <svg className={styles.spin} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 3a9 9 0 1 0 9 9" strokeLinecap="round" />
            </svg>
            <p>Building graph…</p>
          </div>
        )}

        <svg ref={svgRef} className={styles.svg} aria-label="Crime intelligence network graph" role="img" />
      </div>

      {/* Legend */}
      {nodeCount > 0 && (
        <div className={styles.legend} role="list" aria-label="Node type legend">
          {LEGEND_ITEMS.map((item) => (
            <div key={item.type} className={styles.legendItem} role="listitem">
              <span className={styles.legendDot} style={{ background: NODE_COLORS[item.type] }} aria-hidden />
              <span className={styles.legendLabel}>{item.label}</span>
            </div>
          ))}
          <span className={styles.legendHint}>Drag · scroll to zoom</span>
        </div>
      )}
    </div>
  );
}
