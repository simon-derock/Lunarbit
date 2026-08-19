import { SlidersHorizontal } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { SORTS, type SortId } from "@/lib/lunarbit/presets";
import type { LayerId } from "@/lib/lunarbit/types";
import { cn } from "@/lib/utils";

interface Props {
  layers: LayerId[];
  activeLayers: LayerId[];
  onToggleLayer: (l: LayerId) => void;
  relationships: string[];
  activeRelationships: string[];
  onToggleRelationship: (r: string) => void;
  sort: SortId;
  onSort: (s: SortId) => void;
  minConfidence: number;
  onMinConfidence: (v: number) => void;
  layerColors: Record<LayerId, string>;
  onReset: () => void;
  counts: { nodes: number; edges: number };
}

export function FilterMenu({
  layers,
  activeLayers,
  onToggleLayer,
  relationships,
  activeRelationships,
  onToggleRelationship,
  sort,
  onSort,
  minConfidence,
  onMinConfidence,
  layerColors,
  onReset,
  counts,
}: Props) {
  return (
    <Popover>
      <PopoverTrigger className="panel flex items-center gap-2 px-3 py-2 transition-colors hover:border-primary/40 focus-visible:outline-none">
        <SlidersHorizontal className="size-3.5 text-muted-foreground" />
        <span className="text-left">
          <span className="label-mono block">Filter · sort</span>
          <span className="block text-[0.8125rem] font-medium tracking-tight">
            {activeLayers.length}/{layers.length} layers · ≥{minConfidence.toFixed(2)}
          </span>
        </span>
      </PopoverTrigger>
      <PopoverContent align="start" sideOffset={8} className="panel glow-ring z-50 w-[23rem] p-4">
        <div className="flex items-center justify-between">
          <span className="label-mono">Node layers</span>
          <span className="font-mono text-[0.65rem] text-muted-foreground">
            {counts.nodes} nodes · {counts.edges} edges
          </span>
        </div>
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {layers.map((l) => {
            const on = activeLayers.includes(l);
            return (
              <button
                key={l}
                onClick={() => onToggleLayer(l)}
                className={cn(
                  "flex items-center gap-1.5 rounded-sm border px-2 py-1 font-mono text-[0.65rem] uppercase tracking-widest transition-colors",
                  on
                    ? "border-primary/40 bg-primary/10 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                <span
                  className="size-1.5 rounded-full"
                  style={{ background: layerColors[l], opacity: on ? 1 : 0.35 }}
                />
                {l}
              </button>
            );
          })}
        </div>

        <div className="mt-4 label-mono">Relationship types</div>
        <div className="mt-2 flex max-h-28 flex-wrap gap-1.5 overflow-y-auto no-scrollbar">
          {relationships.map((r) => {
            const on = activeRelationships.includes(r);
            return (
              <button
                key={r}
                onClick={() => onToggleRelationship(r)}
                className={cn(
                  "rounded-sm border px-1.5 py-0.5 font-mono text-[0.6rem] tracking-wider transition-colors",
                  on
                    ? "border-primary/40 bg-primary/10 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {r}
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex items-center justify-between">
          <span className="label-mono">Min confidence</span>
          <span className="font-mono text-[0.65rem] text-foreground">
            {minConfidence.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={0.5}
          max={0.98}
          step={0.01}
          value={minConfidence}
          onChange={(e) => onMinConfidence(Number(e.target.value))}
          className="mt-2 h-0.5 w-full appearance-none rounded-full bg-border accent-[var(--color-primary)]"
        />

        <div className="mt-4 label-mono">Sort by</div>
        <div className="mt-2 grid grid-cols-2 gap-1.5">
          {SORTS.map((s) => (
            <button
              key={s.id}
              onClick={() => onSort(s.id)}
              className={cn(
                "rounded-sm border px-2 py-1.5 text-left font-mono text-[0.65rem] tracking-wide transition-colors",
                sort === s.id
                  ? "border-primary/40 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {s.name}
            </button>
          ))}
        </div>

        <button
          onClick={onReset}
          className="mt-4 w-full border-t border-border pt-3 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:text-foreground"
        >
          Reset projection
        </button>
      </PopoverContent>
    </Popover>
  );
}
