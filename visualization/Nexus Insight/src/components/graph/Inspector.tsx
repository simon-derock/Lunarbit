import { X } from "lucide-react";
import type { GraphEdge, GraphNode } from "@/lib/lunarbit/types";

interface Props {
  node: GraphNode;
  edges: GraphEdge[];
  nodesById: Map<string, GraphNode>;
  color: string;
  onClose: () => void;
}

export function Inspector({ node, edges, nodesById, color, onClose }: Props) {
  const related = edges
    .filter((e) => e.source === node.id || e.target === node.id)
    .slice(0, 9)
    .map((e) => ({
      edge: e,
      other: nodesById.get(e.source === node.id ? e.target : e.source),
      direction: e.source === node.id ? "out" : "in",
    }));

  return (
    <aside className="panel glow-ring pointer-events-auto w-[19.5rem] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="label-mono flex items-center gap-1.5">
            <span className="size-1.5 rounded-full" style={{ background: color }} />
            {node.layer} · {node.type}
          </div>
          <h3 className="mt-1.5 font-mono text-sm tracking-tight">{node.label}</h3>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-y-2.5 border-t border-border pt-3">
        {[
          ["confidence", node.confidence.toFixed(2)],
          ["sources", String(node.source_count)],
          ["centrality", node.weight.toFixed(2)],
          ["privacy", node.privacy_state],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="label-mono">{k}</dt>
            <dd className="font-mono text-xs text-foreground">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 label-mono">Relationships</div>
      <ul className="mt-2 space-y-1.5">
        {related.map(({ edge, other, direction }) => (
          <li key={edge.id} className="flex items-baseline gap-2 font-mono text-[0.65rem]">
            <span className="text-muted-foreground">{direction === "out" ? "→" : "←"}</span>
            <span className="text-foreground/90">{edge.relationship_type}</span>
            <span className="flex-1 truncate text-muted-foreground">{other?.label}</span>
            <span className="text-muted-foreground">
              {edge.aggregate_count?.toLocaleString() ?? edge.confidence.toFixed(2)}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-4 border-t border-border pt-3 font-mono text-[0.6rem] leading-relaxed text-muted-foreground">
        {node.detail} · public projection only
      </p>
    </aside>
  );
}
