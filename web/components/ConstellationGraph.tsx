"use client";

import { useMemo, useState } from "react";

import { useProfiles } from "@/components/ProfileProvider";
import type { GraphNode } from "@/lib/types";

const kindIndex: Record<GraphNode["kind"], number> = {
  profile: 0,
  platform: 1,
  merchant: 2,
  order: 3,
  item: 4,
  money: 1,
  event: 2,
  evidence: 4,
};

export function ConstellationGraph({ compact = false }: Readonly<{ compact?: boolean }>) {
  const { dataProfile, visualProfile } = useProfiles();
  const [selected, setSelected] = useState(dataProfile.nodes[0]?.id ?? "");
  const nodes = useMemo(
    () => new Map(dataProfile.nodes.map((value) => [value.id, value])),
    [dataProfile.nodes],
  );
  const selectedNode = nodes.get(selected) ?? dataProfile.nodes[0];

  return (
    <div className={`constellation-wrap${compact ? " compact" : ""}`}>
      <svg
        className="constellation"
        role="img"
        aria-label={`${dataProfile.title} evidence graph rendered as ${visualProfile.name}`}
        viewBox="0 0 1000 620"
      >
        <defs>
          <radialGradient id={`core-${dataProfile.id}`}>
            <stop offset="0" stopColor={visualProfile.palette[0]} stopOpacity="0.92" />
            <stop offset="1" stopColor={visualProfile.palette[0]} stopOpacity="0" />
          </radialGradient>
          <filter id="node-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation={visualProfile.rendering === "bloom" ? "15" : "7"} result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <pattern id="micro-grid" width="36" height="36" patternUnits="userSpaceOnUse">
            <path d="M36 0H0V36" fill="none" stroke="currentColor" strokeOpacity=".08" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="1000" height="620" fill="url(#micro-grid)" />
        <circle className="graph-orbit orbit-a" cx="500" cy="310" r="190" />
        <circle className="graph-orbit orbit-b" cx="500" cy="310" r="286" />
        {dataProfile.edges.map((value, index) => {
          const source = nodes.get(value.source);
          const target = nodes.get(value.target);
          if (!source || !target) return null;
          const active = source.id === selected || target.id === selected;
          return (
            <g key={value.id} className={active ? "edge-group active" : "edge-group"}>
              <line
                x1={source.x * 10}
                y1={source.y * 6.2}
                x2={target.x * 10}
                y2={target.y * 6.2}
                style={{ "--edge-color": visualProfile.palette[index % visualProfile.palette.length] } as React.CSSProperties}
              />
              {!compact && active && (
                <text x={(source.x + target.x) * 5} y={(source.y + target.y) * 3.1 - 7}>
                  {value.relation}
                </text>
              )}
            </g>
          );
        })}
        {dataProfile.nodes.map((value, index) => {
          const color = visualProfile.palette[kindIndex[value.kind]];
          const active = value.id === selected;
          const radius = 7 + value.weight * 5;
          return (
            <g
              className={`graph-node ${value.kind}${active ? " active" : ""}`}
              key={value.id}
              onClick={() => setSelected(value.id)}
              role="button"
              aria-label={`${value.kind}: ${value.label}`}
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") setSelected(value.id);
              }}
              transform={`translate(${value.x * 10} ${value.y * 6.2})`}
            >
              <circle className="node-bloom" r={radius * 2.8} fill={`url(#core-${dataProfile.id})`} />
              <circle className="node-ring" r={radius + 6} stroke={color} />
              <circle className="node-core" r={radius} fill={color} filter="url(#node-glow)" />
              <circle className="node-specular" cx={-radius * 0.25} cy={-radius * 0.3} r={Math.max(2, radius * 0.22)} />
              {!compact && (
                <g className="node-label" transform={`translate(${radius + 11} -3)`}>
                  <text>{value.label}</text>
                  <text y="15" className="node-kind">{value.kind.toUpperCase()} · {String(index + 1).padStart(2, "0")}</text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
      {!compact && selectedNode && (
        <div className="graph-inspector">
          <span>SELECTED / {selectedNode.kind.toUpperCase()}</span>
          <strong>{selectedNode.label}</strong>
          <p>{selectedNode.detail}</p>
          <small>{selectedNode.id.replace(`${dataProfile.id}:`, "PUB / ").toUpperCase()}</small>
        </div>
      )}
      <div className="graph-axis axis-x">X / COMMERCIAL SCOPE</div>
      <div className="graph-axis axis-y">Y / EVIDENCE DEPTH</div>
    </div>
  );
}
