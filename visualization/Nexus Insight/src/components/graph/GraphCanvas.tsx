import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { GraphEdge, GraphNode } from "@/lib/lunarbit/types";
import type { ThemePreset, VizProfile } from "@/lib/lunarbit/presets";

const ForceGraph2D = lazy(() => import("react-force-graph-2d"));

type LinkDatum = GraphEdge & {
  source: GraphNode | string;
  target: GraphNode | string;
};

const RELATIONSHIP_TONES: Record<
  string,
  "evidence" | "financial" | "product" | "identity" | "commerce"
> = {
  EVIDENCED_BY: "evidence",
  ASSERTS: "evidence",
  DERIVED_FROM: "evidence",
  HAS_COMPONENT: "financial",
  RECONCILED_BY: "financial",
  USED: "financial",
  HAS_ITEM_OBSERVATION: "product",
  COMPARED_WITH: "product",
  POSSIBLY_SAME_AS: "identity",
  RESOLVES_TO: "identity",
  ORDERED_FROM: "commerce",
  PLACED_ON: "commerce",
};

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  theme: ThemePreset;
  viz: VizProfile;
  selectedId: string | null;
  onSelect: (node: GraphNode | null) => void;
}

interface ForceGraphHandle {
  d3Force: (
    name: string,
  ) => { strength?: (value: number) => unknown; distance?: (value: number) => unknown } | undefined;
  d3ReheatSimulation?: () => void;
  zoomToFit?: (duration?: number, padding?: number) => void;
}

function useSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      if (!entry) return;
      setSize({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, size };
}

export function GraphCanvas({ nodes, edges, theme, viz, selectedId, onSelect }: Props) {
  const { ref, size } = useSize();
  const fgRef = useRef<ForceGraphHandle | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const data = useMemo(() => {
    const ids = new Set(nodes.map((n) => n.id));
    return {
      nodes: nodes.map((n) => ({ ...n })),
      links: edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e) => ({ ...e })) as unknown as LinkDatum[],
    };
  }, [nodes, edges]);

  const neighbours = useMemo(() => {
    const focus = hovered ?? selectedId;
    if (!focus) return null;
    const set = new Set<string>([focus]);
    edges.forEach((e) => {
      if (e.source === focus) set.add(e.target);
      if (e.target === focus) set.add(e.source);
    });
    return set;
  }, [hovered, selectedId, edges]);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("charge")?.strength(viz.charge);
    fg.d3Force("link")?.distance(viz.linkDistance);
    fg.d3ReheatSimulation?.();
  }, [viz, data]);

  const drawNode = (raw: unknown, ctx: CanvasRenderingContext2D, scale: number) => {
    const node = raw as GraphNode & { x: number; y: number };
    const color = theme.graph.layers[node.layer];
    const dim = neighbours ? !neighbours.has(node.id) : false;
    const r = (2.2 + Math.sqrt(node.weight) * 1.55) * viz.nodeScale;
    ctx.globalAlpha = dim ? 0.18 : 1;

    if (viz.glow > 0 && !dim) {
      ctx.shadowColor = theme.graph.halo;
      ctx.shadowBlur = 10 * viz.glow;
    }

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1 / scale + 0.35;

    if (viz.nodeShape === "orb") {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fill();
    } else if (viz.nodeShape === "ring") {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(node.x, node.y, r * 0.28, 0, Math.PI * 2);
      ctx.fill();
    } else if (viz.nodeShape === "pin") {
      ctx.beginPath();
      ctx.arc(node.x, node.y, Math.max(0.9, r * 0.42), 0, Math.PI * 2);
      ctx.fill();
    } else if (viz.nodeShape === "shard") {
      const sides = 3 + (node.label.length % 4);
      ctx.beginPath();
      for (let i = 0; i < sides; i++) {
        const a = (i / sides) * Math.PI * 2 + node.confidence * 3;
        const px = node.x + Math.cos(a) * r * 1.25;
        const py = node.y + Math.sin(a) * r * 1.25;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
    } else {
      // glyph: layered square bracket marker
      ctx.beginPath();
      ctx.rect(node.x - r, node.y - r, r * 2, r * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(node.x - r * 0.45, node.y);
      ctx.lineTo(node.x + r * 0.45, node.y);
      ctx.stroke();
    }

    ctx.shadowBlur = 0;

    // A small semantic mark survives every visualization preset: geometry says
    // how the graph is drawn; this mark says what the node means.
    ctx.save();
    ctx.globalAlpha = dim ? 0.2 : 0.92;
    ctx.strokeStyle = theme.graph.background;
    ctx.fillStyle = theme.graph.background;
    ctx.lineWidth = Math.max(0.65, 1.4 / scale);
    const mark = Math.max(1.1, r * 0.34);
    ctx.beginPath();
    if (node.layer === "evidence") {
      ctx.rect(node.x - mark * 0.72, node.y - mark * 0.72, mark * 1.44, mark * 1.44);
      ctx.stroke();
      ctx.moveTo(node.x - mark * 0.42, node.y);
      ctx.lineTo(node.x + mark * 0.42, node.y);
      ctx.stroke();
    } else if (node.layer === "commerce") {
      ctx.moveTo(node.x, node.y - mark);
      ctx.lineTo(node.x + mark, node.y);
      ctx.lineTo(node.x, node.y + mark);
      ctx.lineTo(node.x - mark, node.y);
      ctx.closePath();
      ctx.stroke();
    } else if (node.layer === "product") {
      ctx.moveTo(node.x, node.y - mark);
      ctx.lineTo(node.x + mark, node.y + mark * 0.75);
      ctx.lineTo(node.x - mark, node.y + mark * 0.75);
      ctx.closePath();
      ctx.stroke();
    } else if (node.layer === "financial") {
      ctx.moveTo(node.x - mark, node.y - mark * 0.45);
      ctx.lineTo(node.x + mark, node.y - mark * 0.45);
      ctx.moveTo(node.x - mark, node.y + mark * 0.45);
      ctx.lineTo(node.x + mark, node.y + mark * 0.45);
      ctx.stroke();
    } else if (node.layer === "identity") {
      ctx.arc(node.x, node.y, mark * 0.8, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fill();
    } else {
      ctx.moveTo(node.x - mark, node.y);
      ctx.lineTo(node.x + mark, node.y);
      ctx.moveTo(node.x, node.y - mark);
      ctx.lineTo(node.x, node.y + mark);
      ctx.stroke();
    }
    ctx.restore();

    const focused = node.id === (hovered ?? selectedId);
    if (focused) {
      ctx.strokeStyle = theme.graph.halo;
      ctx.lineWidth = 0.8 / scale;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 4.5, 0, Math.PI * 2);
      ctx.stroke();
    }

    const showLabel = viz.labels === "all" || focused || (viz.labels === "hubs" && node.weight > 6);
    if (showLabel && scale > 0.5) {
      ctx.globalAlpha = dim ? 0.2 : 0.9;
      ctx.font = `${Math.max(3.4, 9 / scale)}px "JetBrains Mono", ui-monospace, monospace`;
      ctx.fillStyle = focused ? theme.graph.halo : theme.graph.text;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(node.label, node.x + r + 3, node.y);
    }
    ctx.globalAlpha = 1;
  };

  const linkColor = (raw: unknown) => {
    const link = raw as LinkDatum;
    if (!neighbours) return theme.graph.edge;
    const s = typeof link.source === "string" ? link.source : (link.source as GraphNode).id;
    const t = typeof link.target === "string" ? link.target : (link.target as GraphNode).id;
    if (!neighbours.has(s) || !neighbours.has(t)) return "rgba(255,255,255,0.04)";
    const layer = RELATIONSHIP_TONES[link.relationship_type];
    return layer ? theme.graph.layers[layer] : theme.graph.edgeHot;
  };

  const semanticLinkColor = (raw: unknown) => {
    const link = raw as LinkDatum;
    const layer = RELATIONSHIP_TONES[link.relationship_type];
    return layer ? theme.graph.layers[layer] : theme.graph.edge;
  };

  return (
    <div ref={ref} className="absolute inset-0">
      <Suspense fallback={null}>
        {size.w > 0 && (
          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={data as never}
            backgroundColor={theme.graph.background}
            cooldownTicks={220}
            d3AlphaDecay={0.024}
            d3VelocityDecay={0.32}
            linkColor={linkColor as never}
            linkWidth={
              ((raw: unknown) => {
                const link = raw as LinkDatum;
                const highlighted =
                  neighbours &&
                  [link.source, link.target].every((end) =>
                    neighbours.has(typeof end === "string" ? end : (end as GraphNode).id),
                  );
                const aggregateWeight = Math.min(
                  1.1,
                  Math.log10((link.aggregate_count ?? 0) + 1) * 0.22,
                );
                return highlighted
                  ? (viz.edgeStyle === "beam" ? 1.35 : 0.85) + aggregateWeight
                  : 0.42 + aggregateWeight * 0.34;
              }) as never
            }
            linkCurvature={viz.edgeStyle === "arc" ? 0.28 : 0}
            linkLineDash={(viz.edgeStyle === "dotted" ? [1.5, 3] : null) as never}
            linkCanvasObjectMode={() => "replace"}
            linkCanvasObject={
              ((raw: unknown, ctx: CanvasRenderingContext2D, globalScale: number) => {
                const link = raw as LinkDatum & {
                  source: GraphNode & { x: number; y: number };
                  target: GraphNode & { x: number; y: number };
                };
                const source = typeof link.source === "string" ? null : link.source;
                const target = typeof link.target === "string" ? null : link.target;
                if (!source || !target) return;
                const x1 = source.x;
                const y1 = source.y;
                const x2 = target.x;
                const y2 = target.y;
                const dx = x2 - x1;
                const dy = y2 - y1;
                const distance = Math.hypot(dx, dy) || 1;
                const ux = dx / distance;
                const uy = dy / distance;
                const arrow = Math.max(2.2, 5 / globalScale);
                const endX = x2 - ux * arrow * 1.4;
                const endY = y2 - uy * arrow * 1.4;
                ctx.save();
                ctx.globalAlpha =
                  neighbours && !(neighbours.has(source.id) && neighbours.has(target.id))
                    ? 0.08
                    : 0.72;
                ctx.strokeStyle = semanticLinkColor(link);
                ctx.lineWidth =
                  ((neighbours?.has(source.id) && neighbours?.has(target.id) ? 1 : 0.55) +
                    Math.min(0.75, Math.log10((link.aggregate_count ?? 0) + 1) * 0.16)) /
                  globalScale;
                ctx.setLineDash(
                  viz.edgeStyle === "dotted" ? [2 / globalScale, 4 / globalScale] : [],
                );
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(endX, endY);
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.fillStyle = semanticLinkColor(link);
                ctx.beginPath();
                ctx.moveTo(endX, endY);
                ctx.lineTo(
                  endX - ux * arrow - uy * arrow * 0.6,
                  endY - uy * arrow + ux * arrow * 0.6,
                );
                ctx.lineTo(
                  endX - ux * arrow + uy * arrow * 0.6,
                  endY - uy * arrow - ux * arrow * 0.6,
                );
                ctx.closePath();
                ctx.fill();
                ctx.restore();
              }) as never
            }
            linkDirectionalParticles={viz.particles ? 2 : 0}
            linkDirectionalParticleWidth={1.3}
            linkDirectionalParticleColor={semanticLinkColor as never}
            nodeCanvasObject={drawNode as never}
            nodePointerAreaPaint={
              ((raw: unknown, color: string, ctx: CanvasRenderingContext2D) => {
                const n = raw as GraphNode & { x: number; y: number };
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(n.x, n.y, 7, 0, Math.PI * 2);
                ctx.fill();
              }) as never
            }
            onNodeHover={((n: unknown) => setHovered((n as GraphNode | null)?.id ?? null)) as never}
            onNodeClick={((n: unknown) => onSelect(n as GraphNode)) as never}
            onBackgroundClick={() => onSelect(null)}
            onEngineStop={() => fgRef.current?.zoomToFit(700, 80)}
          />
        )}
      </Suspense>
    </div>
  );
}
