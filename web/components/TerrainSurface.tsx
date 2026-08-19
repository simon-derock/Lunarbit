"use client";

import { useProfiles } from "@/components/ProfileProvider";

function linePath(values: readonly number[], row: number) {
  return values
    .map((value, index) => {
      const x = 74 + index * (760 / Math.max(values.length - 1, 1));
      const baseline = 77 + row * 43;
      const wave = Math.sin(index * 1.35 + row * 0.72) * (7 + row * 1.4);
      const y = baseline - value * 0.26 + wave;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

export function TerrainSurface() {
  const { dataProfile, visualProfile } = useProfiles();
  const base = dataProfile.timeline.map((point) => point.index);
  const rows = Array.from({ length: 8 }, (_, row) =>
    base.map((value, index) => value + Math.sin(index + row) * 12 - row * 3),
  );

  return (
    <div className="terrain-wrap">
      <svg viewBox="0 0 900 430" role="img" aria-label={`${dataProfile.title} personal price terrain`}>
        <defs>
          <linearGradient id={`terrain-fill-${dataProfile.id}`} x1="0" y1="0" x2="1" y2="1">
            <stop stopColor={visualProfile.palette[0]} stopOpacity=".2" />
            <stop offset=".52" stopColor={visualProfile.palette[3]} stopOpacity=".04" />
            <stop offset="1" stopColor={visualProfile.palette[1]} stopOpacity=".13" />
          </linearGradient>
          <filter id="terrain-glow"><feGaussianBlur stdDeviation="3" result="g" /><feMerge><feMergeNode in="g" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <path className="terrain-plane" d="M45 41H857V384H45Z" />
        {Array.from({ length: 12 }, (_, index) => <path className="terrain-guide" d={`M${45 + index * 74} 41V384`} key={`v-${index}`} />)}
        {rows.map((values, row) => (
          <g key={row}>
            {row === rows.length - 1 && <path d={`${linePath(values, row)} L834 384 L74 384Z`} fill={`url(#terrain-fill-${dataProfile.id})`} />}
            <path className={`terrain-line${row === 3 ? " terrain-focus" : ""}`} d={linePath(values, row)} />
          </g>
        ))}
        {dataProfile.timeline.map((point, index) => {
          const x = 74 + index * (760 / Math.max(dataProfile.timeline.length - 1, 1));
          const y = 77 + 3 * 43 - point.index * .26 + Math.sin(index * 1.35 + 3 * .72) * 11.2;
          return <g className="terrain-event" key={point.period} transform={`translate(${x} ${y})`}><circle r="5" /><circle r="13" /><text y="-16">{point.period}</text></g>;
        })}
        <text className="terrain-coordinate" x="46" y="29">PRICE SURFACE / NORMALIZED 100</text>
        <text className="terrain-coordinate" x="709" y="412">TIME VECTOR / {dataProfile.years}</text>
      </svg>
      <div className="terrain-readout"><span>ACTIVE RIDGE</span><strong>{dataProfile.findings[0].title}</strong><small>Observed comparisons only · confidence {dataProfile.findings[0].confidence}</small></div>
    </div>
  );
}
