"use client";

import { useProfiles } from "@/components/ProfileProvider";

function pathFor(values: readonly number[], width: number, height: number): string {
  const maximum = Math.max(...values, 1);
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - (value / maximum) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function SignalChart() {
  const { dataProfile, visualProfile } = useProfiles();
  const width = 680;
  const height = 210;
  const spend = dataProfile.timeline.map((value) => value.spend);
  const fees = dataProfile.timeline.map((value) => value.fees);
  const discount = dataProfile.timeline.map((value) => value.discount);
  const spendPath = pathFor(spend, width, height);

  return (
    <div className="signal-chart-wrap">
      <div className="chart-legend">
        <span style={{ color: visualProfile.palette[0] }}><i /> Spend signal</span>
        <span style={{ color: visualProfile.palette[1] }}><i /> Fee pressure</span>
        <span style={{ color: visualProfile.palette[2] }}><i /> Discount capture</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height + 38}`} role="img" aria-label={`${dataProfile.title} economic signals`}>
        <defs>
          <linearGradient id={`area-${dataProfile.id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={visualProfile.palette[0]} stopOpacity=".28" />
            <stop offset="1" stopColor={visualProfile.palette[0]} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((value) => <line className="chart-gridline" key={value} x1="0" y1={value * (height / 4)} x2={width} y2={value * (height / 4)} />)}
        <path d={`${spendPath} L${width},${height} L0,${height} Z`} fill={`url(#area-${dataProfile.id})`} />
        <path className="chart-path" d={spendPath} stroke={visualProfile.palette[0]} />
        <path className="chart-path secondary" d={pathFor(fees, width, height)} stroke={visualProfile.palette[1]} />
        <path className="chart-path tertiary" d={pathFor(discount, width, height)} stroke={visualProfile.palette[2]} />
        {dataProfile.timeline.map((value, index) => {
          const x = (index / Math.max(dataProfile.timeline.length - 1, 1)) * width;
          const y = height - (value.spend / Math.max(...spend, 1)) * height;
          return <g key={value.period}><circle cx={x} cy={y} r="3.5" fill={visualProfile.palette[0]} /><text className="chart-year" x={x} y={height + 28} textAnchor={index === 0 ? "start" : index === dataProfile.timeline.length - 1 ? "end" : "middle"}>20{value.period}</text></g>;
        })}
      </svg>
    </div>
  );
}
