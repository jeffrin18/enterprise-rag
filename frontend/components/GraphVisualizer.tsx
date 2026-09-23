"use client";

import { useMemo, useState } from "react";
import { Share2 } from "lucide-react";
import { GraphSubgraph } from "@/lib/types";

const TYPE_COLORS: Record<string, string> = {
  PERSON: "#22d3ee",
  ORG: "#a78bfa",
  PRODUCT: "#f472b6",
  POLICY: "#fbbf24",
  METRIC: "#34d399",
  SYSTEM: "#60a5fa",
  Entity: "#6366f1",
};

function colorFor(type: string) {
  return TYPE_COLORS[type] ?? "#6366f1";
}

export default function GraphVisualizer({ subgraph }: { subgraph: GraphSubgraph }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const width = 480;
  const height = 320;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) / 2 - 48;

  const positions = useMemo(() => {
    const n = subgraph.nodes.length || 1;
    const map = new Map<string, { x: number; y: number }>();
    subgraph.nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      map.set(node.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
    });
    return map;
  }, [subgraph.nodes, cx, cy, radius]);

  if (!subgraph.nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 text-muted text-sm h-full p-8">
        <Share2 size={20} />
        <span>No graph nodes retrieved for this query.</span>
        <span className="text-xs text-center max-w-xs">
          Ask a relational question (e.g. &quot;How is X connected to Y?&quot;) to trigger the graph
          traversal route.
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 pt-4 pb-2 text-xs uppercase tracking-wider text-muted">
        <Share2 size={14} />
        Retrieved Subgraph ({subgraph.nodes.length} nodes · {subgraph.edges.length} edges)
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full flex-1">
        <g>
          {subgraph.edges.map((edge, i) => {
            const s = positions.get(edge.source);
            const t = positions.get(edge.target);
            if (!s || !t) return null;
            const midX = (s.x + t.x) / 2;
            const midY = (s.y + t.y) / 2;
            const active = hovered === edge.source || hovered === edge.target;
            return (
              <g key={`edge-${i}`}>
                <line
                  x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                  stroke={active ? "#6366f1" : "#242a37"}
                  strokeWidth={active ? 2 : 1}
                />
                <text x={midX} y={midY} fontSize={9} fill="#8b93a7" textAnchor="middle"
                      className="select-none">
                  {edge.relation}
                </text>
              </g>
            );
          })}
        </g>
        <g>
          {subgraph.nodes.map((node) => {
            const p = positions.get(node.id);
            if (!p) return null;
            const active = hovered === node.id;
            return (
              <g
                key={node.id}
                transform={`translate(${p.x}, ${p.y})`}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                className="cursor-pointer"
              >
                <circle r={active ? 20 : 16} fill={colorFor(node.type)} fillOpacity={0.18}
                        stroke={colorFor(node.type)} strokeWidth={active ? 2 : 1.5} />
                <text y={4} fontSize={10} textAnchor="middle" fill="#e5e7eb" className="select-none">
                  {node.label.length > 12 ? `${node.label.slice(0, 11)}…` : node.label}
                </text>
                <text y={active ? 32 : 28} fontSize={8} textAnchor="middle" fill="#8b93a7"
                      className="select-none">
                  {node.type}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
