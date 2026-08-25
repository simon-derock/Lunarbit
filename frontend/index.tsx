import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { GraphSurface } from "./GraphSurface";
import { fetchPublicSnapshot, fetchQueryPlan, mapPublicSnapshot } from "./api";
import {
  GRAPH_PROFILES,
  SORTS,
  THEMES,
  VIZ_PROFILES,
  type GraphNode,
  type LayerId,
  type SortId,
  type Snapshot,
} from "./graph";

const EMPTY_SNAPSHOT: Snapshot = {
  metrics: [],
  graph_nodes: [],
  graph_edges: [],
  findings: [],
  disclosure: "Waiting for the verified public Neo4j projection.",
};

/* ---------------------------------------------------------------- *
 * Minimal flat menu — a rule-bordered plate, no glass, no radius
 * ---------------------------------------------------------------- */
function Menu({
  tag,
  value,
  options,
  onChange,
  align = "start",
  width = "16rem",
  keepOpenOnSelect = false,
}: {
  tag: string;
  value: string;
  options: { id: string; name: string; hint?: string; swatches?: string[] }[];
  onChange: (id: string) => void;
  align?: "start" | "end";
  width?: string;
  keepOpenOnSelect?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const active = options.find((o) => o.id === value) ?? options[0]!;

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="plate flex h-9 min-w-[9.5rem] items-center gap-3 px-3 text-left transition-colors hover:border-foreground/40"
      >
        <span className="tag">{tag}</span>
        <span className="flex-1 truncate text-[11px] text-foreground">{active.name}</span>
        {active.swatches && (
          <span className="flex gap-[2px]">
            {active.swatches.slice(0, 4).map((c, i) => (
              <span key={i} className="h-2.5 w-[3px]" style={{ background: c }} />
            ))}
          </span>
        )}
        <span className="tag">{open ? "—" : "+"}</span>
      </button>
      {open && (
        <div
          className="plate absolute z-50 mt-[-1px] max-h-[22rem] overflow-y-auto no-scrollbar"
          style={{ width, [align === "end" ? "right" : "left"]: 0 }}
        >
          {options.map((o) => (
            <button
              key={o.id}
              onClick={() => {
                onChange(o.id);
                if (!keepOpenOnSelect) setOpen(false);
              }}
              className={`flex w-full items-start gap-2 border-b border-border px-3 py-2.5 text-left transition-colors last:border-b-0 hover:bg-foreground/5 ${
                o.id === value ? "bg-foreground/[0.07]" : ""
              }`}
            >
              <span className="tag w-3 pt-[2px]">{o.id === value ? "▪" : ""}</span>
              <span className="flex-1">
                <span className="block text-[11px] text-foreground">{o.name}</span>
                {o.hint && <span className="mt-[3px] block text-[10px] text-muted-foreground">{o.hint}</span>}
              </span>
              {o.swatches && (
                <span className="flex gap-[2px] pt-[3px]">
                  {o.swatches.slice(0, 6).map((c, i) => (
                    <span key={i} className="h-3 w-[3px]" style={{ background: c }} />
                  ))}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="border-b border-border px-3 py-2.5 last:border-b-0">
      <div className="tag">{label}</div>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

function Chip({
  on,
  onClick,
  children,
  color,
}: {
  on: boolean;
  onClick: () => void;
  children: ReactNode;
  color?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 border px-1.5 py-[3px] text-[9.5px] uppercase tracking-[0.12em] transition-colors ${
        on ? "border-foreground/45 text-foreground" : "border-border text-muted-foreground"
      }`}
    >
      {color && <span className="h-2 w-[3px]" style={{ background: on ? color : "currentColor" }} />}
      {children}
    </button>
  );
}

const STATUS: Record<string, string> = {
  verified: "text-foreground",
  residual: "text-muted-foreground",
  conflict: "text-[color:var(--destructive)]",
  abstained: "text-muted-foreground",
};

export function Console() {
  const defaultViz = VIZ_PROFILES.find((profile) => profile.id === "cortex") ?? VIZ_PROFILES[0]!;
  const [profileId, setProfileId] = useState(GRAPH_PROFILES[0]!.id);
  const [vizId, setVizId] = useState(defaultViz.id);
  const [themeId, setThemeId] = useState(defaultViz.preferredTheme);
  const [sort, setSort] = useState<SortId>("weight");
  const [minConfidence, setMinConfidence] = useState(0.6);
  const [mutedLayers, setMutedLayers] = useState<LayerId[]>([]);
  const [mutedRels, setMutedRels] = useState<string[]>([]);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [panel, setPanel] = useState<"filters" | "findings" | null>("findings");
  const [ask, setAsk] = useState("");
  const [liveSnapshot, setLiveSnapshot] = useState<Snapshot | null>(null);
  const [apiState, setApiState] = useState<"loading" | "live" | "error">("loading");
  const [queryState, setQueryState] = useState<string | null>(null);

  const theme = THEMES.find((t) => t.id === themeId)!;
  const profile = GRAPH_PROFILES.find((p) => p.id === profileId)!;
  const viz = VIZ_PROFILES.find((v) => v.id === vizId)!;
  useEffect(() => {
    let active = true;
    setApiState("loading");
    fetchPublicSnapshot()
      .then((payload) => {
        if (active) {
          setLiveSnapshot(mapPublicSnapshot(payload));
          setApiState("live");
        }
      })
      .catch(() => {
        if (active) setApiState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  const snapshot = liveSnapshot ?? EMPTY_SNAPSHOT;

  const activeLayers = profile.layers.filter((l) => !mutedLayers.includes(l));
  const activeRels = profile.relationships.filter((r) => !mutedRels.includes(r));

  const { nodes, edges } = useMemo(() => {
    const keep = snapshot.graph_nodes.filter(
      (n) => activeLayers.includes(n.layer) && n.confidence >= minConfidence,
    );
    const ids = new Set(keep.map((n) => n.id));
    const keepEdges = snapshot.graph_edges.filter(
      (e) => ids.has(e.source) && ids.has(e.target) && activeRels.includes(e.relationship_type),
    );
    const sorted = [...keep].sort((a, b) => {
      if (sort === "label") return a.label.localeCompare(b.label);
      if (sort === "confidence") return b.confidence - a.confidence;
      if (sort === "sources") return b.source_count - a.source_count;
      return b.weight - a.weight;
    });
    return { nodes: sorted, edges: keepEdges };
  }, [snapshot, activeLayers.join(), activeRels.join(), minConfidence, sort]);

  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const links = selected
    ? edges
        .filter((e) => e.source === selected.id || e.target === selected.id)
        .slice(0, 12)
        .map((e) => ({
          rel: e.relationship_type,
          other: byId.get(e.source === selected.id ? e.target : e.source)?.label ?? "—",
          conf: e.confidence,
        }))
    : [];

  return (
    <main
      style={theme.vars as CSSProperties}
      className="relative h-screen w-full overflow-hidden bg-background text-foreground"
    >
      <GraphSurface
        nodes={nodes}
        edges={edges}
        palette={theme.palette}
        viz={viz}
        selectedId={selected?.id ?? null}
        onSelect={setSelected}
      />

      {apiState === "error" && (
        <div className="pointer-events-auto absolute inset-x-0 top-1/2 mx-auto w-[min(34rem,calc(100%-2rem))] -translate-y-1/2 border border-[color:var(--destructive)] bg-background p-5 text-center">
          <div className="tag text-[color:var(--destructive)]">live graph unavailable</div>
          <p className="serif mt-2 text-[18px]">Start the FastAPI + Neo4j service to load Lunarbit data.</p>
          <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
            No synthetic nodes are rendered. The console is waiting for the verified public projection.
          </p>
        </div>
      )}

      {/* HDR pass: luminance lift, vignette, fine grain */}
      <div className="hdr pointer-events-none absolute inset-0" />
      <div className="grain pointer-events-none absolute inset-0" />



      {/* top bar */}
      <header className="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-start justify-between gap-2 p-4">
        <div className="pointer-events-auto flex items-baseline gap-2.5 px-1 pt-1">
          <h1 className="brandmark text-[18px] tracking-[0.08em] text-foreground">Lunarbit</h1>
          <span className="text-[9px] tracking-[0.08em] text-muted-foreground">by Philip Simon Derock</span>
        </div>


        <div className="pointer-events-auto flex flex-wrap justify-end gap-2">
          <Menu
            tag="view"
            value={profileId}
            onChange={setProfileId}
            align="end"
            width="19rem"
            options={GRAPH_PROFILES.map((p) => ({ id: p.id, name: p.name, hint: p.scope }))}
          />
          <Menu
            tag="style"
            value={vizId}
            onChange={(id) => {
              setVizId(id);
              const next = VIZ_PROFILES.find((v) => v.id === id);
              if (next && THEMES.some((t) => t.id === next.preferredTheme)) {
                setThemeId(next.preferredTheme);
              }
            }}
            align="end"
            width="17rem"
            keepOpenOnSelect
            options={VIZ_PROFILES.map((v) => ({ id: v.id, name: v.name, hint: v.hint }))}
          />

          <Menu
            tag="theme"
            value={themeId}
            onChange={setThemeId}
            align="end"
            width="17rem"
            keepOpenOnSelect
            options={THEMES.map((t) => ({
              id: t.id,
              name: t.name,
              hint: t.hint,
              swatches: Object.values(t.palette.layers),
            }))}
          />
        </div>
      </header>

      {/* left: metrics ledger */}
      <div className="pointer-events-none absolute left-4 top-1/2 hidden -translate-y-1/2 lg:block">
        <div className="pointer-events-auto plate w-[12.5rem]">
          {snapshot.metrics.map((m) => (
            <div key={m.label} className="border-b border-border px-3 py-2 last:border-b-0">
              <div className="tag">{m.label}</div>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="serif text-[19px] leading-none">{m.value}</span>
                <span className="text-[9.5px] text-muted-foreground">{m.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* right: inspector / findings */}
      <div className="pointer-events-none absolute right-4 top-1/2 hidden w-[19rem] -translate-y-1/2 lg:block">
        {selected ? (
          <div className="pointer-events-auto plate">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <span className="tag">node · {selected.type}</span>
              <button className="tag hover:text-foreground" onClick={() => setSelected(null)}>
                close
              </button>
            </div>
            <div className="border-b border-border px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="h-3 w-[3px]" style={{ background: theme.palette.layers[selected.layer] }} />
                <span className="serif text-[17px] leading-none">{selected.label}</span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-y-1 text-[10px] text-muted-foreground">
                <span>layer · {selected.layer}</span>
                <span>scope · {selected.scope}</span>
                <span>conf · {selected.confidence.toFixed(2)}</span>
                <span>sources · {selected.source_count}</span>
                <span>privacy · {selected.privacy_state}</span>
                <span>centrality · {selected.weight.toFixed(1)}</span>
              </div>
            </div>
            <div className="tag border-b border-border px-3 py-2">relationships</div>
            <ul className="max-h-[15rem] overflow-y-auto no-scrollbar">
              {links.map((l, i) => (
                <li
                  key={i}
                  className="flex items-baseline justify-between gap-2 border-b border-border px-3 py-1.5 last:border-b-0"
                >
                  <span className="text-[9.5px] uppercase tracking-[0.14em] text-muted-foreground">
                    {l.rel}
                  </span>
                  <span className="truncate text-[10.5px]">{l.other}</span>
                  <span className="text-[9.5px] text-muted-foreground">{l.conf.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          panel === "findings" && (
            <div className="pointer-events-auto plate">
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <span className="tag">findings · citation gated</span>
                <button className="tag hover:text-foreground" onClick={() => setPanel(null)}>
                  hide
                </button>
              </div>
              <ul className="max-h-[24rem] overflow-y-auto no-scrollbar">
                {snapshot.findings.map((f) => (
                  <li key={f.id} className="border-b border-border px-3 py-2.5 last:border-b-0">
                    <div className="flex items-baseline justify-between">
                      <span className={`tag ${STATUS[f.status]}`}>{f.status}</span>
                      <span className="text-[9.5px] text-muted-foreground">
                        {f.confidence.toFixed(2)}
                      </span>
                    </div>
                    <p className="serif mt-1 text-[14px] leading-tight">{f.title}</p>
                    <p className="mt-1 text-[9.5px] leading-relaxed text-muted-foreground">
                      {f.graph_path.join("  ›  ")}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )
        )}
      </div>

      {/* bottom dock */}
      <footer className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap items-end justify-between gap-2 p-4">
        <div className="pointer-events-auto flex items-end gap-2">
          <div className="plate w-[19rem]">
            <button
              className="flex w-full items-center justify-between border-b border-border px-3 py-2"
              onClick={() => setPanel(panel === "filters" ? null : "filters")}
            >
              <span className="tag">filter · sort</span>
              <span className="text-[10px] text-muted-foreground">
                {nodes.length}n / {edges.length}e
              </span>
            </button>
            {panel === "filters" && (
              <div className="max-h-[24rem] overflow-y-auto no-scrollbar">
                <Field label="layers">
                  <div className="flex flex-wrap gap-1">
                    {profile.layers.map((l) => (
                      <Chip
                        key={l}
                        on={activeLayers.includes(l)}
                        color={theme.palette.layers[l]}
                        onClick={() =>
                          setMutedLayers((p) => (p.includes(l) ? p.filter((x) => x !== l) : [...p, l]))
                        }
                      >
                        {l}
                      </Chip>
                    ))}
                  </div>
                </Field>
                <Field label={`relationships · ${activeRels.length}/${profile.relationships.length}`}>
                  <div className="flex flex-wrap gap-1">
                    {profile.relationships.map((r) => (
                      <Chip
                        key={r}
                        on={activeRels.includes(r)}
                        onClick={() =>
                          setMutedRels((p) => (p.includes(r) ? p.filter((x) => x !== r) : [...p, r]))
                        }
                      >
                        {r.toLowerCase()}
                      </Chip>
                    ))}
                  </div>
                </Field>
                <Field label={`confidence ≥ ${minConfidence.toFixed(2)}`}>
                  <input
                    type="range"
                    min={0.6}
                    max={0.99}
                    step={0.01}
                    value={minConfidence}
                    onChange={(e) => setMinConfidence(Number(e.target.value))}
                    className="h-[3px] w-full appearance-none bg-border accent-[color:var(--primary)]"
                  />
                </Field>
                <Field label="sort">
                  <div className="flex flex-wrap gap-1">
                    {SORTS.map((s) => (
                      <Chip key={s.id} on={sort === s.id} onClick={() => setSort(s.id)}>
                        {s.name}
                      </Chip>
                    ))}
                  </div>
                </Field>
                <Field label="reset">
                  <button
                    className="tag hover:text-foreground"
                    onClick={() => {
                      setMutedLayers([]);
                      setMutedRels([]);
                      setMinConfidence(0.6);
                      setSort("weight");
                    }}
                  >
                    restore defaults
                  </button>
                </Field>
              </div>
            )}
          </div>
          {!panel && (
            <button className="plate h-9 px-3 tag hover:border-foreground/40" onClick={() => setPanel("findings")}>
              findings
            </button>
          )}
        </div>

        <div
          className="pointer-events-auto flex h-10 w-[26rem] max-w-full items-center gap-2.5 border px-3"
          style={{
            background: "color-mix(in oklab, var(--surface) 92%, var(--foreground))",
            borderColor: "color-mix(in oklab, var(--border) 40%, var(--foreground))",
          }}
        >
          <span className="tag text-foreground/70">ask</span>
          <span className="h-3.5 w-px bg-border" />
          <input
            value={ask}
            onChange={(e) => setAsk(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter" || !ask.trim()) return;
              e.preventDefault();
              setQueryState("planning");
              fetchQueryPlan(ask)
                .then((plan) => setQueryState(`${plan.intent} · ${plan.actions.length} actions`))
                .catch(() => setQueryState("public scope abstained"));
            }}
            placeholder="reconcile delivery fees for ORD-4821"
            className="h-full flex-1 bg-transparent text-[11.5px] text-foreground outline-none placeholder:text-muted-foreground/80"
          />
          <span className="text-[9.5px] tracking-[0.12em] text-foreground/60">
            {queryState ?? (ask ? "enter · plan" : "↵")}
          </span>
        </div>

      </footer>

      <p className="pointer-events-none absolute inset-x-0 bottom-1 mx-auto hidden max-w-2xl text-center text-[9px] text-muted-foreground/70 2xl:block">
        {snapshot.disclosure}
      </p>
    </main>
  );
}
