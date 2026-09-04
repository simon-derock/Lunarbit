import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { formationTargets } from "./graph";
import type { GraphEdge, GraphNode, Palette, VizProfile } from "./graph";

const ForceGraph2D = lazy(() => import("react-force-graph-2d"));

type Pt = { x: number; y: number };
type LinkDatum = GraphEdge & { source: GraphNode & Pt; target: GraphNode & Pt };

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

  const data = useMemo(() => {
    const ids = new Set(nodes.map((n) => n.id));
    return {
      nodes: nodes.map((n) => ({ ...n })),
      links: edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e) => ({ ...e })) as unknown as LinkDatum[],
    };
  }, [nodes, edges]);

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
  const targets = useMemo(() => formationTargets(viz.formation, nodes), [viz.formation, nodes]);
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
  const prog = useRef(0);
  // fit instantly (the opacity envelope carries the motion) and clear the
  // right-hand findings plate in the same frame — no second animation
  const fit = useCallback(() => {
    const fg = fgRef.current;
    if (!fg || userRef.current) return;
    prog.current += 2;
    // Keep a generous visual margin so style changes never crop or over-zoom
    // the complete graph beneath the surrounding inspector plates.
    // Keep the projection large enough to read while leaving room for the
    // surrounding controls. The previous 220px padding made every formation
    // look like a tiny thumbnail on wide screens.
    const compact = size.w > 0 && size.w < 600;
    fg.zoomToFit(compact ? 0 : 84, compact ? 26 : 180);
  }, [size.w]);
  useEffect(() => {
    tickCount.current = 0;
    userRef.current = false;
    prog.current = 0;
  }, [data, viz]);
  const onTick = useCallback(() => {
    if (userRef.current) return;
    tickCount.current += 1;
  }, [fit]);
  const markUser = useCallback(() => {
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
    const zc = Math.min(4, Math.max(0.9, 1.35 / scale));
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

    const show = viz.labels === "all" || active || (viz.labels === "hubs" && n.weight > 12);
    if (show && scale > 0.45) {
      ctx.globalAlpha = (dim ? 0.15 : 0.92) * intro;
      ctx.font = `${Math.max(3.2, 8.4 / scale)}px "IBM Plex Mono", ui-monospace, monospace`;
      ctx.fillStyle = active ? palette.ink : fade(color, 0.72);
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(n.label, n.x + r * 2.9, n.y);
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
      <Suspense fallback={null}>
        {size.w > 0 && (
          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={data as never}
            backgroundColor={palette.paper}
            warmupTicks={0}
            // A short bounded settle keeps style changes responsive; the
            // formation spring continues to hold structured layouts after it.
            cooldownTicks={viz.formStrength > 0 ? 42 : 36}
            d3AlphaDecay={0.11}
            d3VelocityDecay={0.62}
            enableNodeDrag
            enableZoomInteraction
            enablePanInteraction
            linkCanvasObject={drawLink as never}
            linkCanvasObjectMode={(() => "replace") as never}
            linkDirectionalParticles={viz.particles && data.links.length < 180 ? 2 : 0}
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
              n.fx = undefined;
              n.fy = undefined;
              fgRef.current?.d3ReheatSimulation?.();
            }) as never}
            onZoom={markUser as never}
            onBackgroundClick={() => {
              onSelect(null);
              onLinkSelect(null);
            }}
            onEngineTick={onTick}
            onEngineStop={() => fit()}

          />
        )}
      </Suspense>
    </div>
  );
}
