import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { formationTargets } from "./graph";
import type { GraphEdge, GraphNode, Palette, VizProfile } from "./graph";

type Pt = { x: number; y: number };
type LinkDatum = GraphEdge & { source: GraphNode & Pt; target: GraphNode & Pt };
type LabelSide = "left" | "right" | "top" | "bottom";

/**
 * Prefer the side away from the local chain direction.  For a left-to-right
 * chain this puts the first node's label on the left and the next node's label
 * on the right, instead of making both labels grow into the edge corridor.
 */
function preferredLabelSide(node: GraphNode & Pt, neighbors: Pt[], seed: number): LabelSide {
  if (neighbors.length) {
    const dx = neighbors.reduce((sum, point) => sum + (point.x - node.x), 0) / neighbors.length;
    const dy = neighbors.reduce((sum, point) => sum + (point.y - node.y), 0) / neighbors.length;
    if (Math.abs(dx) > Math.abs(dy) * 0.7 && Math.abs(dx) > 1) return dx > 0 ? "left" : "right";
    if (Math.abs(dy) > 1) return dy > 0 ? "top" : "bottom";
  }
  return seed < 0.5 ? "left" : "right";
}

function labelCandidates(preferred: LabelSide): LabelSide[] {
  const opposite: Record<LabelSide, LabelSide> = { left: "right", right: "left", top: "bottom", bottom: "top" };
  const horizontal = preferred === "left" || preferred === "right";
  return horizontal
    ? [preferred, opposite[preferred], "top", "bottom"]
    : [preferred, opposite[preferred], "left", "right"];
}

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  palette: Palette;
  viz: VizProfile;
  selectedId: string | null;
  onSelect: (node: GraphNode | null) => void;
  onLinkSelect: (edge: GraphEdge | null) => void;
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

function fade(hex: string, alpha: number) {
  if (!hex.startsWith("#")) return hex;
  const v = hex.slice(1);
  const full = v.length === 3 ? v.split("").map((c) => c + c).join("") : v;
  const n = parseInt(full, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

function hash(id: string) {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = (h ^ id.charCodeAt(i)) * 16777619;
  return (h >>> 0) / 4294967296;
}

export function GraphSurface({ nodes, edges, palette, viz, selectedId, onSelect, onLinkSelect }: Props) {
  const { ref, size } = useSize();
  const fgRef = useRef<any>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [ready, setReady] = useState(0);
  const introRef = useRef(0); // 0 → 1 reveal envelope
  const labelGridRef = useRef<Set<string>>(new Set());
  const labelNeighborsRef = useRef<Map<string, Pt[]>>(new Map());
  const nodeLookupRef = useRef<Map<string, GraphNode>>(new Map());

  const data = useMemo(() => {
    const ids = new Set(nodes.map((n) => n.id));
    return {
      nodes: nodes.map((n) => ({ ...n })),
      links: edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e) => ({ ...e })) as unknown as LinkDatum[],
    };
  }, [nodes, edges]);

  useEffect(() => {
    nodeLookupRef.current = new Map(data.nodes.map((node) => [node.id, node]));
  }, [data]);

  /* ---------- fluid intro: reveal envelope eased over ~1.1s ---------- */
  useEffect(() => {
    introRef.current = 0;
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 1200);
      introRef.current = 1 - Math.pow(1 - p, 3);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [data, viz]);

  const focus = hovered ?? selectedId;
  const near = useMemo(() => {
    if (!focus) return null;
    const set = new Set<string>([focus]);
    edges.forEach((e) => {
      if (e.source === focus) set.add(e.target);
      if (e.target === focus) set.add(e.source);
    });
    return set;
  }, [focus, edges]);

  /* ---------- formation: pull nodes onto a silhouette ---------- */
  const targets = useMemo(() => {
    // Keep formation coordinates device-independent. The camera fit below is
    // measured from the actual canvas, so the same topology can adapt to a
    // narrow phone, tablet split view, or resizable laptop without a second
    // hard-coded geometry scale fighting the force simulation.
    return formationTargets(viz.formation, nodes);
  }, [viz.formation, nodes, size.w]);
  const targetsRef = useRef(targets);
  targetsRef.current = targets;
  const strengthRef = useRef(viz.formStrength);
  strengthRef.current = viz.formStrength;
  const simNodes = useRef<(GraphNode & Pt & { vx: number; vy: number; fx?: number; fy?: number })[]>([]);

  useEffect(() => {
    const fg = fgRef.current;
    // the graph is lazy-loaded: retry until the instance exists
    if (!fg) {
      const id = setTimeout(() => setReady((v) => v + 1), 120);
      return () => clearTimeout(id);
    }
    const formed = viz.formStrength > 0;
    fg.d3Force("charge")?.strength(formed ? viz.charge * 0.06 : viz.charge);
    fg.d3Force("link")?.distance(viz.linkDistance);
    fg.d3Force("link")?.strength(formed ? 0.01 : 1);
    fg.d3Force("center")?.strength?.(formed ? 0 : 1);
    // spring toward the silhouette, independent of the cooling alpha so the
    // formation still reads once the simulation has relaxed
    const form = (() => {
      const st = strengthRef.current;
      if (!st) return;
      for (const nd of simNodes.current) {
        // Let the pointer own a node while it is being dragged. Without this
        // guard the formation spring immediately pulled it back under the
        // cursor, which made organic marks feel impossible to move.
        if (nd.fx != null || nd.fy != null) continue;
        const t = targetsRef.current.get(nd.id);
        if (!t) continue;
        nd.vx += (t.x - nd.x) * st;
        nd.vy += (t.y - nd.y) * st;
      }
    }) as (() => void) & { initialize?: (ns: unknown[]) => void };
    form.initialize = (ns: unknown[]) => {
      simNodes.current = ns as (GraphNode & Pt & { vx: number; vy: number; fx?: number; fy?: number })[];
    };
    fg.d3Force("form", form);
    fg.d3ReheatSimulation?.();
    return undefined;
  }, [viz, data, ready]);

  /* ---------- framing: one instant fit, never fighting the user ---------- */
  const tickCount = useRef(0);
  const userRef = useRef(false);
  const fittingRef = useRef(false);
  const programmaticUntilRef = useRef(0);
  const initialFitUntilRef = useRef(0);
  const prog = useRef(0);
  // fit instantly (the opacity envelope carries the motion) and clear the
  // right-hand findings plate in the same frame — no second animation
  const fit = useCallback(() => {
    const fg = fgRef.current;
    if (!fg) return;
    if (userRef.current && performance.now() >= initialFitUntilRef.current) return;
    if (performance.now() < initialFitUntilRef.current) userRef.current = false;
    fittingRef.current = true;
    programmaticUntilRef.current = performance.now() + 700;
    prog.current += 2;
    // Keep a generous visual margin so style changes never crop or over-zoom
    // the complete graph beneath the surrounding inspector plates.
    // Keep the projection large enough to read while leaving room for the
    // surrounding controls. The previous 220px padding made every formation
    // look like a tiny thumbnail on wide screens.
    const compact = size.w > 0 && size.w < 600;
    // Keep the complete formation comfortably inside the viewport. The live
    // projection is dense enough that tight framing reads as over-zoomed,
    // especially on narrow phone screens.
    const padding = compact
      ? Math.max(56, Math.min(104, Math.round(size.w * 0.16)))
      : 60;
    fg.zoomToFit(padding, compact ? 0 : 220);
    window.requestAnimationFrame(() => {
      if (userRef.current && performance.now() >= initialFitUntilRef.current) {
        fittingRef.current = false;
        return;
      }
      const fittedZoom = fg.zoom();
      if (typeof fittedZoom === "number" && Number.isFinite(fittedZoom)) {
        // Leave a little breathing room for safe-area controls without using a
        // device-specific zoom constant. The getter is sampled after
        // zoomToFit commits its camera transform.
        const phoneScale = Math.max(0.34, Math.min(0.4, size.w / 1100));
        fg.zoom(fittedZoom * (compact ? phoneScale : 1.15), 0);
      }
      fittingRef.current = false;
    });
  }, [size.h, size.w]);
  // Formation forces can continue moving nodes after the first engine stop.
  // Refit a few times during the initial reveal, but never after the user has
  // taken ownership of the camera or a node.
  useEffect(() => {
    if (!size.w || !size.h) return;
    const timers = [500, 1400, 2600, 5200, 7600].map((delay) => window.setTimeout(fit, delay));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [data, fit, size.h, size.w, viz]);
  useEffect(() => {
    tickCount.current = 0;
    userRef.current = false;
    initialFitUntilRef.current = performance.now() + 3200;
    prog.current = 0;
  }, [data, viz]);
  const onTick = useCallback(() => {
    if (userRef.current) return;
    tickCount.current += 1;
  }, [fit]);
  const markUser = useCallback(() => {
    if (
      fittingRef.current ||
      performance.now() < programmaticUntilRef.current ||
      performance.now() < initialFitUntilRef.current
    ) return;
    if (prog.current > 0) prog.current -= 1;
    else userRef.current = true;
  }, []);



  const hueOf = (n: GraphNode) => {
    if (viz.colorMode === "layer") return palette.layers[n.layer];
    const ramp = palette.chroma;
    return ramp[Math.floor(hash(n.id) * ramp.length) % ramp.length]!;
  };

  /* dark gamuts get a light-bloom pass so signal reads as emitted, not printed */
  const isDark = useMemo(() => {
    const v = palette.paper.replace("#", "");
    const f = v.length === 3 ? v.split("").map((c) => c + c).join("") : v;
    const num = parseInt(f, 16);
    const l = (((num >> 16) & 255) * 0.299 + ((num >> 8) & 255) * 0.587 + (num & 255) * 0.114) / 255;
    return l < 0.4;
  }, [palette.paper]);

  /* ---------------- node marks ---------------- */
  const drawNode = (raw: unknown, ctx: CanvasRenderingContext2D, scale: number) => {
    const n = raw as GraphNode & Pt;
    const color = hueOf(n);
    const dim = near ? !near.has(n.id) : false;
    const active = n.id === focus;
    const intro = introRef.current;
    const dense = nodes.length > 220 || scale < 0.55;
    // screen-space compensation: marks stay legible when the fit zooms out
    const zc = Math.min(2.4, Math.max(0.72, 1.0 / scale));
    const r = (3.4 + Math.sqrt(n.weight) * 1.8) * viz.scale * zc * (0.65 + intro * 0.35);
    const hair = Math.max(0.55, 1.1 / scale);
    const seed = hash(n.id);

    ctx.globalAlpha = (dim ? 0.12 : 1) * (0.2 + intro * 0.8);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = hair;
    // shadowBlur is the single most expensive canvas op — reserve it for the
    // focused mark so panning and zooming stay at frame rate
    if (isDark && active) {
      ctx.shadowColor = fade(color, 0.85);
      ctx.shadowBlur = 14 * Math.min(1.6, 1 / Math.max(0.35, scale));
    }


    if (viz.nodeMark === "soma") {
      /* neuron: irregular soma body + tapering dendrite arbor */
      const arms = dense ? 3 : 4 + Math.floor(seed * 4);
      for (let i = 0; i < arms; i++) {
        const a = (i / arms) * Math.PI * 2 + seed * 6.28;
        const len = r * (2.6 + seed * 2.4 + (i % 2 ? 0.9 : 0)) * (0.4 + intro * 0.6);
        const bend = (seed - 0.5) * 1.1;
        let px = n.x;
        let py = n.y;
        let ang = a;
        let w = Math.max(0.22, r * 0.34);
        const segs = dense ? 2 : 4;
        for (let s = 0; s < segs; s++) {
          const step = len / segs;
          const nx2 = px + Math.cos(ang) * step;
          const ny2 = py + Math.sin(ang) * step;
          ctx.lineWidth = w;
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.quadraticCurveTo(
            px + Math.cos(ang + bend) * step * 0.6,
            py + Math.sin(ang + bend) * step * 0.6,
            nx2,
            ny2,
          );
          ctx.stroke();
          // terminal twig
          if (s === segs - 2) {
            ctx.lineWidth = w * 0.55;
            ctx.beginPath();
            ctx.moveTo(nx2, ny2);
            ctx.lineTo(
              nx2 + Math.cos(ang - bend * 1.8) * step * 0.8,
              ny2 + Math.sin(ang - bend * 1.8) * step * 0.8,
            );
            ctx.stroke();
          }
          px = nx2;
          py = ny2;
          ang += bend * 0.55;
          w *= 0.56;
        }
      }
      // soma: organic lobed body
      ctx.beginPath();
      const lobes = 7;
      for (let i = 0; i <= lobes; i++) {
        const a = (i / lobes) * Math.PI * 2;
        const rr = r * (0.9 + Math.sin(a * 3 + seed * 9) * 0.16);
        const px = n.x + Math.cos(a) * rr;
        const py = n.y + Math.sin(a) * rr * 0.92;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
    } else if (viz.nodeMark === "orb") {
      /* multi-hue orb with soft chromatic bloom */
      const R = r * 3.2;
      const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, R);
      g.addColorStop(0, fade(color, 1));
      g.addColorStop(0.3, fade(color, 0.5));
      g.addColorStop(0.62, fade(color, 0.16));
      g.addColorStop(1, fade(color, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(n.x, n.y, R, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r * (0.7 + n.confidence * 0.45), 0, Math.PI * 2);
      ctx.fill();
    } else if (viz.nodeMark === "vertex") {
      /* space fabric: wireframe diamond vertex */
      const s = r * 1.15;
      ctx.fillStyle = palette.paper;
      ctx.beginPath();
      ctx.moveTo(n.x, n.y - s);
      ctx.lineTo(n.x + s, n.y);
      ctx.lineTo(n.x, n.y + s);
      ctx.lineTo(n.x - s, n.y);
      ctx.closePath();
      ctx.fill();
      ctx.lineWidth = hair * 1.4;
      ctx.strokeStyle = color;
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(n.x, n.y, Math.max(0.4, s * 0.22 * n.confidence), 0, Math.PI * 2);
      ctx.fill();
    } else if (viz.nodeMark === "moon") {
      /* the moon IS the node — lit body with a phase terminator, no ring */
      const R = r * 1.3;
      ctx.beginPath();
      ctx.arc(n.x, n.y, R, 0, Math.PI * 2);
      ctx.fill();
      // occluder sweeps the phase: full → gibbous → crescent
      const d = R * (0.2 + seed * 1.05);
      if (d > R * 0.28) {
        ctx.save();
        ctx.globalCompositeOperation = "destination-out";
        ctx.beginPath();
        ctx.arc(n.x - d, n.y - d * 0.24, R * 1.02, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    } else if (viz.nodeMark === "planet") {
      /* an orrery of bodies: gas giants with rings, rocky worlds, moons, stars */
      const kind = Math.floor(seed * 100) % 5;
      const R = r * 1.35;
      if (kind === 4) {
        // star: four-point flare, no disc
        const L = R * 2.6;
        ctx.lineWidth = Math.max(0.3, hair * 1.2);
        ctx.strokeStyle = color;
        ctx.beginPath();
        for (let i = 0; i < 4; i++) {
          const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
          ctx.moveTo(n.x, n.y);
          ctx.lineTo(n.x + Math.cos(a) * L * (i % 2 ? 0.5 : 1), n.y + Math.sin(a) * L * (i % 2 ? 0.5 : 1));
        }
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(n.x, n.y, R * 0.32, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // body
        ctx.beginPath();
        ctx.arc(n.x, n.y, R, 0, Math.PI * 2);
        ctx.fill();
        // banding (gas giant) or mare patches (rocky)
        ctx.save();
        ctx.beginPath();
        ctx.arc(n.x, n.y, R, 0, Math.PI * 2);
        ctx.clip();
        ctx.globalCompositeOperation = "destination-out";
        if (kind === 0 || kind === 1) {
          const bands = 3 + Math.floor(seed * 3);
          for (let i = 0; i < bands; i++) {
            const off = (-R + (i + 0.5) * ((2 * R) / bands)) * 1;
            ctx.globalAlpha = 0.22 + ((i * 7 + seed * 10) % 3) * 0.08;
            ctx.fillRect(n.x - R, n.y + off - R * 0.09, R * 2, R * 0.16);
          }
        } else {
          for (let i = 0; i < 3; i++) {
            ctx.globalAlpha = 0.2;
            const a = seed * 9 + i * 2.1;
            ctx.beginPath();
            ctx.arc(n.x + Math.cos(a) * R * 0.45, n.y + Math.sin(a) * R * 0.45, R * 0.26, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        ctx.restore();
        // ring system on the giants
        if (kind === 0) {
          ctx.strokeStyle = color;
          ctx.save();
          ctx.translate(n.x, n.y);
          ctx.rotate(-0.42 + seed * 0.5);
          for (let i = 0; i < 2; i++) {
            ctx.lineWidth = Math.max(0.28, hair * (1.4 - i * 0.5));
            ctx.beginPath();
            ctx.ellipse(0, 0, R * (1.75 + i * 0.4), R * (0.4 + i * 0.08), 0, 0, Math.PI * 2);
            ctx.stroke();
          }
          ctx.restore();
        }
        // a small satellite moon
        if (kind === 2 || kind === 3) {
          const a = seed * 6.28;
          ctx.beginPath();
          ctx.arc(n.x + Math.cos(a) * R * 2.1, n.y + Math.sin(a) * R * 1.5, Math.max(0.3, R * 0.22), 0, Math.PI * 2);
          ctx.fill();
        }
      }
    } else if (viz.nodeMark === "ganglion") {
      /* lacquer stencil neuron: hard-edged star soma, recursive dendrite arbor */
      const rnd = (k: number) => {
        const v = Math.sin(seed * 91.7 + k * 12.9898) * 43758.5453;
        return v - Math.floor(v);
      };
      const branch = (
        px: number,
        py: number,
        ang: number,
        len: number,
        w: number,
        depth: number,
        k: number,
      ) => {
        if (depth <= 0 || len < r * 0.28) return;
        const bend = (rnd(k) - 0.5) * 0.9;
        const ex = px + Math.cos(ang) * len;
        const ey = py + Math.sin(ang) * len;
        ctx.lineWidth = Math.max(0.22, w);
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.quadraticCurveTo(
          px + Math.cos(ang + bend * 0.6) * len * 0.55,
          py + Math.sin(ang + bend * 0.6) * len * 0.55,
          ex,
          ey,
        );
        ctx.stroke();
        const spread = 0.42 + rnd(k + 3) * 0.4;
        branch(ex, ey, ang + spread, len * 0.66, w * 0.6, depth - 1, k * 2 + 1);
        branch(ex, ey, ang - spread * 0.8, len * 0.6, w * 0.58, depth - 1, k * 2 + 2);
      };
      const arms = 5 + Math.floor(seed * 3);
      for (let i = 0; i < arms; i++) {
        const a = (i / arms) * Math.PI * 2 + seed * 6.28;
        branch(n.x, n.y, a, r * (2.2 + rnd(i) * 1.5) * (0.35 + intro * 0.65), r * 0.4, 3, i + 1);
      }
      // hard stencil soma: spiky star, flat fill
      ctx.beginPath();
      const pts = arms * 2;
      for (let i = 0; i <= pts; i++) {
        const a = (i / pts) * Math.PI * 2 + seed * 6.28;
        const rr = r * (i % 2 ? 0.55 : 1.15);
        const px = n.x + Math.cos(a) * rr;
        const py = n.y + Math.sin(a) * rr;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
      // nucleus void
      ctx.save();
      ctx.globalCompositeOperation = "destination-out";
      ctx.beginPath();
      ctx.arc(n.x, n.y, r * 0.26, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    } else if (viz.nodeMark === "astro") {
      /* cultured tissue: translucent lit soma with beaded processes */
      const R = r * 2.1;
      const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, R);
      g.addColorStop(0, fade(palette.ink, 0.9));
      g.addColorStop(0.22, fade(color, 0.85));
      g.addColorStop(0.62, fade(color, 0.22));
      g.addColorStop(1, fade(color, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(n.x, n.y, R, 0, Math.PI * 2);
      ctx.fill();
      // processes with varicosity beads
      const arms = 4 + Math.floor(seed * 4);
      for (let i = 0; i < arms; i++) {
        const a = (i / arms) * Math.PI * 2 + seed * 6.28;
        const len = r * (2.6 + seed * 2.2) * (0.4 + intro * 0.6);
        ctx.strokeStyle = fade(color, 0.6);
        ctx.lineWidth = Math.max(0.24, r * 0.16);
        ctx.beginPath();
        ctx.moveTo(n.x, n.y);
        ctx.quadraticCurveTo(
          n.x + Math.cos(a + 0.3) * len * 0.55,
          n.y + Math.sin(a + 0.3) * len * 0.55,
          n.x + Math.cos(a) * len,
          n.y + Math.sin(a) * len,
        );
        ctx.stroke();
        for (let b = 1; b <= 2; b++) {
          const d = len * (b / 2.4);
          ctx.fillStyle = fade(palette.ink, 0.55);
          ctx.beginPath();
          ctx.arc(n.x + Math.cos(a) * d, n.y + Math.sin(a) * d, Math.max(0.22, r * 0.16), 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.fillStyle = fade(palette.ink, 0.95);
      ctx.beginPath();
      ctx.arc(n.x, n.y, Math.max(0.35, r * 0.38), 0, Math.PI * 2);
      ctx.fill();

    } else if (viz.nodeMark === "arbor") {
      /* Golgi stain: one densely ramified arbor, hairline tissue, beaded tips */
      const rnd = (k: number) => {
        const v = Math.sin(seed * 77.3 + k * 19.19) * 43758.5453;
        return v - Math.floor(v);
      };
      const grow = (
        px: number,
        py: number,
        ang: number,
        len: number,
        w: number,
        depth: number,
        k: number,
      ) => {
        if (depth <= 0 || len < r * 0.22) return;
        const bend = (rnd(k) - 0.5) * 1.15;
        const ex = px + Math.cos(ang) * len;
        const ey = py + Math.sin(ang) * len;
        ctx.lineWidth = Math.max(0.18, w);
        ctx.strokeStyle = fade(color, 0.55 + depth * 0.1);
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.quadraticCurveTo(
          px + Math.cos(ang + bend * 0.7) * len * 0.5,
          py + Math.sin(ang + bend * 0.7) * len * 0.5,
          ex,
          ey,
        );
        ctx.stroke();
        if (depth === 1) {
          ctx.fillStyle = fade(color, 0.9);
          ctx.beginPath();
          ctx.arc(ex, ey, Math.max(0.2, w * 0.9), 0, Math.PI * 2);
          ctx.fill();
        }
        const spread = 0.5 + rnd(k + 5) * 0.55;
        grow(ex, ey, ang + spread, len * 0.62, w * 0.62, depth - 1, k * 2 + 1);
        grow(ex, ey, ang - spread * 0.85, len * 0.58, w * 0.6, depth - 1, k * 2 + 2);
      };
      const arms = dense ? 3 : 6 + Math.floor(seed * 4);
      for (let i = 0; i < arms; i++) {
        const a = (i / arms) * Math.PI * 2 + seed * 6.28;
        grow(
          n.x,
          n.y,
          a,
          r * (1.9 + rnd(i) * 1.3) * (0.45 + intro * 0.55),
          r * 0.3,
          dense ? 2 : 4,
          i + 1,
        );
      }
      // soma: a small dense knot, not a disc
      ctx.fillStyle = color;
      ctx.beginPath();
      for (let i = 0; i <= 9; i++) {
        const a = (i / 9) * Math.PI * 2;
        const rr = r * (0.6 + rnd(i + 40) * 0.32);
        const px = n.x + Math.cos(a) * rr * 1.25;
        const py = n.y + Math.sin(a) * rr * 0.8;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
    } else {
      // nova: radial spokes, count from sources, length from confidence
      const spokes = Math.max(5, Math.min(14, n.source_count * 2 + 5));
      ctx.lineWidth = hair * 1.1;
      for (let i = 0; i < spokes; i++) {
        const a = (i / spokes) * Math.PI * 2 + seed * 6.28;
        const inner = r * 0.55;
        const outer = r * (1.5 + n.confidence * 1.6) * (i % 2 ? 0.68 : 1) * (0.5 + intro * 0.5);
        ctx.beginPath();
        ctx.moveTo(n.x + Math.cos(a) * inner, n.y + Math.sin(a) * inner);
        ctx.lineTo(n.x + Math.cos(a) * outer, n.y + Math.sin(a) * outer);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(n.x, n.y, r * 0.42, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.shadowBlur = 0;

    if (active) {
      ctx.strokeStyle = palette.ink;
      ctx.lineWidth = hair;
      const b = r * 2.6;
      ctx.beginPath();
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sy]) => {
        ctx.moveTo(n.x + sx! * b, n.y + sy! * b * 0.55);
        ctx.lineTo(n.x + sx! * b, n.y + sy! * b);
        ctx.lineTo(n.x + sx! * b * 0.55, n.y + sy! * b);
      });
      ctx.stroke();
    }

    // Names are part of the graph's meaning, not a hover-only decoration.
    // Keep them readable by choosing the side away from the local edge
    // corridor and reserving screen-space cells before painting a label.
    const phone = size.w > 0 && size.w < 600;
    const degree = labelNeighborsRef.current.get(n.id)?.length ?? 0;
    const highSignal = active || n.id === hovered || degree > 0 || n.source_count >= 2 || n.weight >= 6;
    // The public projection may omit enrichment counters such as source_count
    // and weight. Use real topology as the mobile signal so connected food,
    // order, merchant, and evidence nodes retain their names instead of
    // disappearing simply because optional metadata was not projected.
    // Collision-aware placement still declutters dense formations.
    const show = !phone || highSignal;
    if (show && (scale > 0.2 || active)) {
      const labelSize = active
        ? Math.max(10, Math.min(14, 8.4 / Math.max(scale, 0.6)))
        : dense
          ? Math.max(5.2, Math.min(7.4, 6.8 / Math.max(scale, 0.7)))
          : Math.max(6.2, Math.min(9.5, 7.6 / Math.max(scale, 0.7)));
      ctx.globalAlpha = (dim ? 0.12 : active ? 1 : 0.78) * intro;
      ctx.font = `${active ? 500 : 400} ${labelSize}px "IBM Plex Mono", ui-monospace, monospace`;
      ctx.textBaseline = "middle";
      const label = n.label?.trim() || n.type || n.id;
      const labelWidth = ctx.measureText(label).width;
      const neighbors = labelNeighborsRef.current.get(n.id) ?? [];
      const preferred = preferredLabelSide(n, neighbors, hash(n.id));
      const gap = Math.max(5 / Math.max(scale, 0.45), r * 0.72);
      const labelHeight = labelSize * 1.45;
      const cellW = 96 / Math.max(scale, 0.45);
      const cellH = 20 / Math.max(scale, 0.45);
      let chosen: { side: LabelSide; x: number; y: number } | null = null;
      for (const side of labelCandidates(preferred)) {
        const offset = r * 2.9 + gap;
        const x = side === "left" ? n.x - offset : side === "right" ? n.x + offset : n.x;
        const y = side === "top" ? n.y - offset : side === "bottom" ? n.y + offset : n.y;
        const left = side === "right" ? x : side === "left" ? x - labelWidth : x - labelWidth / 2;
        const right = side === "right" ? x + labelWidth : side === "left" ? x : x + labelWidth / 2;
        const top = y - labelHeight / 2;
        const bottom = y + labelHeight / 2;
        const colStart = Math.floor((left - cellW * 0.08) / cellW);
        const colEnd = Math.floor((right + cellW * 0.08) / cellW);
        const rowStart = Math.floor((top - cellH * 0.15) / cellH);
        const rowEnd = Math.floor((bottom + cellH * 0.15) / cellH);
        let occupied = false;
        for (let col = colStart; col <= colEnd && !occupied; col += 1) {
          for (let row = rowStart; row <= rowEnd; row += 1) {
            if (labelGridRef.current.has(`${col}:${row}`)) {
              occupied = true;
              break;
            }
          }
        }
        if (!occupied || active) {
          chosen = { side, x, y };
          for (let col = colStart; col <= colEnd; col += 1) {
            for (let row = rowStart; row <= rowEnd; row += 1) labelGridRef.current.add(`${col}:${row}`);
          }
          break;
        }
      }
      if (!chosen) {
        ctx.globalAlpha = 1;
        return;
      }
      ctx.textAlign = chosen.side === "right" ? "left" : chosen.side === "left" ? "right" : "center";
      // A hairline paper keyline keeps labels readable over bright graph
      // marks without adding cards or dashboard chrome to the canvas.
      ctx.strokeStyle = fade(palette.paper, isDark ? 0.72 : 0.9);
      ctx.lineWidth = Math.max(1.5, labelSize * 0.22);
      ctx.strokeText(label, chosen.x, chosen.y);
      ctx.fillStyle = active ? palette.ink : fade(color, 0.82);
      ctx.fillText(label, chosen.x, chosen.y);
    }
    ctx.globalAlpha = 1;

  };

  /* ---------------- edge marks ---------------- */
  const drawLink = (raw: unknown, ctx: CanvasRenderingContext2D, scale: number) => {
    const l = raw as LinkDatum;
    const s = l.source;
    const t = l.target;
    if (!s || !t || typeof s.x !== "number" || typeof t.x !== "number") return;
    const intro = introRef.current;
    const hot = near ? near.has(s.id) && near.has(t.id) : false;
    ctx.globalAlpha = intro;
    ctx.lineCap = "round";

    if (near && !hot) {
      ctx.strokeStyle = fade(palette.ink, 0.03);
      ctx.lineWidth = Math.max(0.2, 0.45 / scale);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
      ctx.globalAlpha = 1;
      return;
    }

    const w = Math.max(0.25, (hot ? 1.15 : 0.55) / scale);
    const dx = t.x - s.x;
    const dy = t.y - s.y;
    const len = Math.hypot(dx, dy) || 1;

    if (viz.edgeMark === "dendrite") {
      /* axon: thick at the soma, tapering to a fine terminal */
      const nx = -dy / len;
      const ny = dx / len;
      const bow = len * 0.09 * (hash(l.id) - 0.5) * 2;
      const cx = (s.x + t.x) / 2 + nx * bow;
      const cy = (s.y + t.y) / 2 + ny * bow;
      const half = Math.max(0.28, (hot ? 2.1 : 1.15) * viz.scale);
      ctx.fillStyle = hot ? palette.edgeHot : palette.edge;
      ctx.beginPath();
      ctx.moveTo(s.x + nx * half, s.y + ny * half);
      ctx.quadraticCurveTo(cx + nx * half * 0.35, cy + ny * half * 0.35, t.x, t.y);
      ctx.quadraticCurveTo(cx - nx * half * 0.35, cy - ny * half * 0.35, s.x - nx * half, s.y - ny * half);
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
      return;
    }

    if (viz.edgeMark === "spectral") {
      const g = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
      g.addColorStop(0, fade(hueOf(s), hot ? 0.95 : 0.42));
      g.addColorStop(0.5, fade(hueOf(t), hot ? 0.8 : 0.3));
      g.addColorStop(1, fade(hueOf(t), hot ? 0.95 : 0.42));
      ctx.strokeStyle = g;
      ctx.lineWidth = w * 0.95;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.quadraticCurveTo(
        (s.x + t.x) / 2 - dy * 0.08,
        (s.y + t.y) / 2 + dx * 0.08,
        t.x,
        t.y,
      );
      ctx.stroke();
      ctx.globalAlpha = 1;
      return;
    }

    if (viz.edgeMark === "mesh") {
      /* taut fabric: straight strand with a slack sag and grid tick */
      ctx.strokeStyle = hot ? palette.edgeHot : palette.edge;
      ctx.lineWidth = w * 0.8;
      const sag = Math.min(18, len * 0.05);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.quadraticCurveTo((s.x + t.x) / 2, (s.y + t.y) / 2 + sag, t.x, t.y);
      ctx.stroke();
      const d = Math.max(0.3, (hot ? 1.3 : 0.7) / scale);
      ctx.fillStyle = hot ? palette.edgeHot : palette.edge;
      ctx.fillRect((s.x + t.x) / 2 - d / 2, (s.y + t.y) / 2 + sag / 2 - d / 2, d, d);
      ctx.globalAlpha = 1;
      return;
    }

    if (viz.edgeMark === "filament") {
      const nx = -dy / len;
      const ny = dx / len;
      const half = w * (hot ? 2.4 : 1.6);
      const mx = (s.x + t.x) / 2 + nx * len * 0.06;
      const my = (s.y + t.y) / 2 + ny * len * 0.06;
      ctx.fillStyle = hot ? palette.edgeHot : palette.edge;
      ctx.beginPath();
      ctx.moveTo(s.x + nx * half, s.y + ny * half);
      ctx.quadraticCurveTo(mx + nx * half * 0.6, my + ny * half * 0.6, t.x, t.y);
      ctx.quadraticCurveTo(mx - nx * half * 0.6, my - ny * half * 0.6, s.x - nx * half, s.y - ny * half);
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
      return;
    }

    if (viz.edgeMark === "axon") {
      /* lacquer axon: flat, hard-edged, tapering from soma to terminal */
      const nx = -dy / len;
      const ny = dx / len;
      const bow = len * 0.13 * (hash(l.id) - 0.5) * 2;
      const cx = (s.x + t.x) / 2 + nx * bow;
      const cy = (s.y + t.y) / 2 + ny * bow;
      const half = Math.max(0.22, (hot ? 1.9 : 0.95) * viz.scale);
      ctx.fillStyle = hot ? palette.edgeHot : fade(hueOf(s), 0.62);
      ctx.beginPath();
      ctx.moveTo(s.x + nx * half, s.y + ny * half);
      ctx.quadraticCurveTo(cx + nx * half * 0.3, cy + ny * half * 0.3, t.x, t.y);
      ctx.quadraticCurveTo(cx - nx * half * 0.3, cy - ny * half * 0.3, s.x - nx * half, s.y - ny * half);
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
      return;
    }

    if (viz.edgeMark === "varicose") {
      /* myelinated strand: gradient filament studded with varicosity beads */
      const g = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
      g.addColorStop(0, fade(hueOf(s), hot ? 0.95 : 0.4));
      g.addColorStop(0.5, fade(palette.ink, hot ? 0.6 : 0.16));
      g.addColorStop(1, fade(hueOf(t), hot ? 0.95 : 0.4));
      ctx.strokeStyle = g;
      ctx.lineWidth = w * (hot ? 1.5 : 0.8);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
      const beads = Math.min(5, Math.max(2, Math.round(len / 70)));
      ctx.fillStyle = fade(palette.ink, hot ? 0.7 : 0.22);
      for (let i = 1; i < beads; i++) {
        const u = i / beads;
        const rr = Math.max(0.2, w * (hot ? 1.5 : 0.9));
        ctx.beginPath();
        ctx.arc(s.x + dx * u, s.y + dy * u, rr, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      return;
    }


    if (viz.edgeMark === "tendril") {
      /* stained tissue strand: hairline, slightly wandering, terminal bead */
      const nx = -dy / len;
      const ny = dx / len;
      const bow = len * 0.16 * (hash(l.id) - 0.5) * 2;
      ctx.strokeStyle = hot ? palette.edgeHot : fade(hueOf(s), 0.34);
      ctx.lineWidth = Math.max(0.2, w * (hot ? 1.3 : 0.6));
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.bezierCurveTo(
        s.x + dx * 0.32 + nx * bow,
        s.y + dy * 0.32 + ny * bow,
        s.x + dx * 0.68 - nx * bow,
        s.y + dy * 0.68 - ny * bow,
        t.x,
        t.y,
      );
      ctx.stroke();
      ctx.globalAlpha = 1;
      return;
    }

    // hair: quiet straight sky-line
    ctx.strokeStyle = hot ? palette.edgeHot : palette.edge;
    ctx.lineWidth = w * 0.7;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.stroke();
    ctx.globalAlpha = 1;
  };

  return (
    <div ref={ref} className="absolute inset-0">
      {size.w > 0 && (
          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={data as never}
            backgroundColor={
              [
                "#12100d",
                "#07191c",
                "#080b16",
                "#0a0b0f",
                "#061012",
                "#f3efe5",
                "#0b1119",
                "#100d19",
                "#0b0d0d",
                "#080d16",
                "#eee8dc",
              ].includes(palette.paper)
                ? "rgba(0,0,0,0)"
                : palette.paper
            }
            warmupTicks={0}
            // A short bounded settle keeps style changes responsive; the
            // formation spring continues to hold structured layouts after it.
            cooldownTicks={size.w > 0 && size.w < 600 ? 12 : viz.formStrength > 0 ? 42 : 36}
            d3AlphaDecay={0.11}
            d3VelocityDecay={0.62}
            enableNodeDrag
            enableZoomInteraction
            enablePanInteraction
            linkCanvasObject={drawLink as never}
            linkCanvasObjectMode={(() => "replace") as never}
            linkDirectionalParticles={size.w >= 600 && viz.particles && data.links.length < 180 ? 2 : 0}
            linkDirectionalParticleWidth={1.1}
            linkDirectionalParticleColor={(() => palette.edgeHot) as never}
            nodeRelSize={6}
            nodeCanvasObject={drawNode as never}
            nodePointerAreaPaint={
              ((raw: unknown, color: string, ctx: CanvasRenderingContext2D, scale: number) => {
                const n = raw as GraphNode & Pt;
                const zc = Math.min(2.2, Math.max(0.7, 0.8 / (scale || 1)));
                const hit = Math.max(
                  14 / (scale || 1),
                  (2.6 + Math.sqrt(n.weight) * 1.5) * viz.scale * zc * 1.6,
                );
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(n.x, n.y, hit, 0, Math.PI * 2);
                ctx.fill();
              }) as never
            }
            onNodeHover={((n: unknown) => setHovered((n as GraphNode | null)?.id ?? null)) as never}
            onNodeClick={((n: unknown) => {
              onLinkSelect(null);
              onSelect(n as GraphNode);
            }) as never}
            linkPointerAreaPaint={((raw: unknown, color: string, ctx: CanvasRenderingContext2D, scale: number) => {
              const l = raw as LinkDatum;
              if (!l.source || !l.target) return;
              ctx.strokeStyle = color;
              ctx.lineWidth = Math.max(12 / (scale || 1), 8);
              ctx.beginPath();
              ctx.moveTo(l.source.x, l.source.y);
              ctx.lineTo(l.target.x, l.target.y);
              ctx.stroke();
            }) as never}
            onLinkClick={((l: unknown) => {
              onSelect(null);
              onLinkSelect(l as GraphEdge);
            }) as never}
            onNodeDrag={((raw: unknown) => {
              userRef.current = true;
              const n = raw as GraphNode & Pt & { fx?: number; fy?: number };
              n.fx = n.x;
              n.fy = n.y;
            }) as never}
            onNodeDragEnd={((raw: unknown) => {
              const n = raw as GraphNode & Pt & { fx?: number; fy?: number };
              // Preserve the user-authored position instead of rubber-banding
              // formed layouts back to their generated target.
              n.fx = n.x;
              n.fy = n.y;
            }) as never}
            onZoom={markUser as never}
            onBackgroundClick={() => {
              onSelect(null);
              onLinkSelect(null);
            }}
            onEngineTick={onTick}
            onEngineStop={() => fit()}
            onRenderFramePre={() => {
              labelGridRef.current.clear();
              const neighbors = new Map<string, Pt[]>();
              for (const link of data.links) {
                const source = (typeof link.source === "object" ? link.source : nodeLookupRef.current.get(String(link.source))) as (GraphNode & Pt) | undefined;
                const target = (typeof link.target === "object" ? link.target : nodeLookupRef.current.get(String(link.target))) as (GraphNode & Pt) | undefined;
                if (!source || !target) continue;
                neighbors.set(source.id, [...(neighbors.get(source.id) ?? []), target]);
                neighbors.set(target.id, [...(neighbors.get(target.id) ?? []), source]);
              }
              labelNeighborsRef.current = neighbors;
            }}

          />
      )}
    </div>
  );
}
