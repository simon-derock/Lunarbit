import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { FilterMenu } from "@/components/graph/FilterMenu";
import { Inspector } from "@/components/graph/Inspector";
import { PresetMenu } from "@/components/graph/PresetMenu";
import { QueryConsole } from "@/components/graph/QueryConsole";
import { fetchPublicSnapshot } from "@/lib/lunarbit/api";
import { GRAPH_PROFILES, THEMES, VIZ_PROFILES, type SortId } from "@/lib/lunarbit/presets";
import type { GraphNode, LayerId } from "@/lib/lunarbit/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Lunarbit · Knowledge Graph RAG Console" },
      {
        name: "description",
        content:
          "Graph-native retrieval console: bounded traversal, citation-gated answers and evidence lineage across 54k nodes.",
      },
      { property: "og:title", content: "Lunarbit · Knowledge Graph RAG Console" },
      {
        property: "og:description",
        content:
          "Explore graph profiles, visualization presets and evidence lineage over a validated public projection.",
      },
    ],
  }),
  component: Console,
});

const STATUS_TONE: Record<string, string> = {
  verified: "text-primary",
  residual: "text-muted-foreground",
  conflict: "text-destructive",
  abstained: "text-muted-foreground",
};

function Console() {
  const [themeId, setThemeId] = useState(THEMES[0]!.id);
  const [profileId, setProfileId] = useState(GRAPH_PROFILES[0]!.id);
  const [vizId, setVizId] = useState(VIZ_PROFILES[0]!.id);
  const [sort, setSort] = useState<SortId>("weight");
  const [minConfidence, setMinConfidence] = useState(0.6);
  const [mutedLayers, setMutedLayers] = useState<LayerId[]>([]);
  const [mutedRels, setMutedRels] = useState<string[]>([]);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [snapshot, setSnapshot] = useState<import("@/lib/lunarbit/types").Snapshot | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  const theme = THEMES.find((t) => t.id === themeId)!;
  const profile = GRAPH_PROFILES.find((p) => p.id === profileId)!;
  const viz = VIZ_PROFILES.find((v) => v.id === vizId)!;
  const isAggregateProjection = snapshot?.projection_mode === "neo4j_aggregate_projection";
  const projectionLabel = isAggregateProjection
    ? "neo4j aggregate live"
    : snapshot
      ? "synthetic mirror"
      : "connecting";

  const availableRelationships = useMemo(() => {
    if (profile.id !== "full") return profile.relationships;
    return [...new Set((snapshot?.graph_edges ?? []).map((edge) => edge.relationship_type))].sort();
  }, [profile, snapshot]);

  useEffect(() => {
    const controller = new AbortController();
    setSnapshotError(null);
    fetchPublicSnapshot(controller.signal)
      .then(setSnapshot)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setSnapshotError("API projection unavailable");
      });
    return () => controller.abort();
  }, []);

  const activeLayers = profile.layers.filter((l) => !mutedLayers.includes(l));
  const activeRels = availableRelationships.filter((r) => !mutedRels.includes(r));

  const { nodes, edges } = useMemo(() => {
    const keep = (snapshot?.graph_nodes ?? []).filter(
      (n) => activeLayers.includes(n.layer) && n.confidence >= minConfidence,
    );
    const ids = new Set(keep.map((n) => n.id));
    const keepEdges = (snapshot?.graph_edges ?? []).filter(
      (e) => ids.has(e.source) && ids.has(e.target) && activeRels.includes(e.relationship_type),
    );
    const sorted = [...keep].sort((a, b) => {
      if (sort === "label") return a.label.localeCompare(b.label);
      if (sort === "confidence") return b.confidence - a.confidence;
      if (sort === "sources") return b.source_count - a.source_count;
      return b.weight - a.weight;
    });
    return { nodes: sorted, edges: keepEdges };
  }, [snapshot, activeLayers, activeRels, minConfidence, sort]);

  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const reset = () => {
    setMutedLayers([]);
    setMutedRels([]);
    setMinConfidence(0.6);
    setSort("weight");
  };

  return (
    <div
      style={theme.vars as React.CSSProperties}
      className="relative h-screen w-full overflow-hidden bg-background text-foreground"
    >
      <GraphCanvas
        nodes={nodes}
        edges={edges}
        theme={theme}
        viz={viz}
        selectedId={selected?.id ?? null}
        onSelect={setSelected}
      />

      {/* vignette + grid overlay */}
      <div className="pointer-events-none absolute inset-0 scan-grid opacity-[0.35]" />
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 90% at 50% 45%, transparent 35%, var(--background) 100%)",
        }}
      />

      {/* Header */}
      <header className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between p-5">
        <div className="pointer-events-auto flex items-start gap-4">
          <div className="panel glow-ring px-3.5 py-2.5">
            <div className="flex items-center gap-2">
              <span
                className="size-1.5 rounded-full"
                style={{ background: "var(--primary)", boxShadow: "0 0 10px var(--glow)" }}
              />
              <span className="font-mono text-[0.8125rem] tracking-[0.22em] uppercase">
                lunarbit
              </span>
            </div>
            <p className="label-mono mt-1">graph rag · public projection</p>
          </div>
          <div className="panel hidden px-3.5 py-2.5 md:block">
            <p className="label-mono">scope</p>
            <p className="mt-1 max-w-[19rem] font-mono text-[0.65rem] leading-relaxed text-muted-foreground">
              {profile.scope}
            </p>
          </div>
        </div>

        <div className="pointer-events-auto flex flex-wrap items-start justify-end gap-2">
          <div className="panel hidden items-center gap-2 px-3 py-2 md:flex">
            <span
              className={`size-1.5 rounded-full ${isAggregateProjection ? "bg-emerald-300" : "bg-amber-300"}`}
              style={{
                boxShadow: isAggregateProjection
                  ? "0 0 12px rgba(110,255,190,.9)"
                  : "0 0 12px rgba(255,200,100,.8)",
              }}
            />
            <span className="label-mono">{projectionLabel}</span>
          </div>
          <PresetMenu
            eyebrow="graph profile"
            value={profileId}
            onChange={setProfileId}
            options={GRAPH_PROFILES.map((p) => ({
              id: p.id,
              name: p.name,
              hint: `${p.layers.length} layers · ${p.relationships.length} rel types`,
            }))}
            align="end"
            footer={
              <p className="font-mono text-[0.6rem] leading-relaxed text-muted-foreground">
                Read-only bounded traversal. Profiles switch the projected slice, never the
                canonical graph.
              </p>
            }
          />
          <PresetMenu
            eyebrow="visualization"
            value={vizId}
            onChange={setVizId}
            options={VIZ_PROFILES.map((v) => ({ id: v.id, name: v.name, hint: v.hint }))}
            align="end"
          />
          <PresetMenu
            eyebrow="theme"
            value={themeId}
            onChange={setThemeId}
            options={THEMES.map((t) => ({
              id: t.id,
              name: t.name,
              hint: t.hint,
              swatches: Object.values(t.graph.layers),
            }))}
            align="end"
            width="w-[17rem]"
          />
        </div>
      </header>

      {/* Left rail: metrics */}
      <div className="pointer-events-none absolute left-5 top-1/2 hidden -translate-y-1/2 lg:block">
        <div className="panel pointer-events-auto w-[13.5rem] divide-y divide-border">
          {(snapshot?.metrics ?? []).map((m) => (
            <div key={m.label} className="px-3.5 py-2.5">
              <div className="label-mono">{m.label}</div>
              <div className="mt-0.5 flex items-baseline gap-1.5">
                <span className="font-mono text-lg leading-none tracking-tight">{m.value}</span>
                <span className="font-mono text-[0.6rem] text-muted-foreground">{m.unit}</span>
              </div>
              <div className="mt-0.5 font-mono text-[0.6rem] text-muted-foreground">
                {m.delta} · {m.temporal_scope}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-24 left-5 hidden xl:block">
        <div className="panel pointer-events-auto w-[13.5rem] px-3.5 py-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="label-mono">semantic key</span>
            <span className="font-mono text-[0.55rem] text-muted-foreground">
              {nodes.length} · {edges.length}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
            {Object.entries(theme.graph.layers).map(([layer, color]) => (
              <div key={layer} className="flex items-center gap-1.5">
                <span
                  className="size-1.5 rounded-full"
                  style={{ background: color, boxShadow: `0 0 7px ${color}` }}
                />
                <span className="font-mono text-[0.58rem] uppercase text-muted-foreground">
                  {layer}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right rail: findings / inspector */}
      <div className="pointer-events-none absolute right-5 top-1/2 hidden -translate-y-1/2 lg:block">
        {selected ? (
          <Inspector
            node={selected}
            edges={edges}
            nodesById={nodesById}
            color={theme.graph.layers[selected.layer]}
            onClose={() => setSelected(null)}
          />
        ) : (
          <div className="panel pointer-events-auto w-[19.5rem]">
            <div className="label-mono border-b border-border px-3.5 py-2.5">
              findings · citation gated
            </div>
            <ul className="max-h-[26rem] divide-y divide-border overflow-y-auto no-scrollbar">
              {(snapshot?.findings ?? []).map((f) => (
                <li key={f.id} className="px-3.5 py-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={`label-mono ${STATUS_TONE[f.status]}`}>{f.status}</span>
                    <span className="font-mono text-[0.6rem] text-muted-foreground">
                      {f.confidence.toFixed(2)}
                    </span>
                  </div>
                  <p className="mt-1 text-[0.8125rem] leading-snug tracking-tight">{f.title}</p>
                  <p className="mt-1 font-mono text-[0.6rem] leading-relaxed text-muted-foreground">
                    {f.graph_path.join(" → ")}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Bottom dock */}
      <footer className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 p-5">
        <div className="pointer-events-auto flex items-end gap-2">
          <FilterMenu
            layers={profile.layers}
            activeLayers={activeLayers}
            onToggleLayer={(l) =>
              setMutedLayers((prev) =>
                prev.includes(l) ? prev.filter((x) => x !== l) : [...prev, l],
              )
            }
            relationships={availableRelationships}
            activeRelationships={activeRels}
            onToggleRelationship={(r) =>
              setMutedRels((prev) =>
                prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r],
              )
            }
            sort={sort}
            onSort={setSort}
            minConfidence={minConfidence}
            onMinConfidence={setMinConfidence}
            layerColors={theme.graph.layers}
            onReset={reset}
            counts={{ nodes: nodes.length, edges: edges.length }}
          />
          <div className="panel hidden px-3.5 py-2.5 xl:block">
            <div className="label-mono">evidence</div>
            <div className="mt-1 flex gap-3">
              {(snapshot?.evidence_cards ?? []).map((c) => (
                <div key={c.id} className="max-w-[8.5rem]">
                  <p className="truncate font-mono text-[0.65rem]">{c.title}</p>
                  <p className="font-mono text-[0.6rem] text-muted-foreground">
                    {c.authority} · {c.verification_status}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="pointer-events-auto">
          <QueryConsole />
        </div>
      </footer>

      <p className="pointer-events-none absolute inset-x-0 bottom-1 mx-auto hidden max-w-3xl text-center font-mono text-[0.55rem] text-muted-foreground/70 2xl:block">
        {snapshot?.disclosure ?? snapshotError ?? "Connecting to the public FastAPI projection…"}
      </p>
    </div>
  );
}
