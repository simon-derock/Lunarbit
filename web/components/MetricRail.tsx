"use client";

import { useProfiles } from "@/components/ProfileProvider";

export function MetricRail() {
  const { dataProfile, visualProfile } = useProfiles();
  return (
    <section className="metric-rail" aria-label={`${dataProfile.title} headline metrics`}>
      {dataProfile.metrics.map((metric, index) => (
        <article className="metric-cell" key={metric.label}>
          <span className="metric-coordinate">M.{String(index + 1).padStart(2, "0")}</span>
          <p>{metric.label}</p>
          <strong>{metric.value}</strong>
          <small>{metric.delta}</small>
          <i style={{ background: visualProfile.palette[index % visualProfile.palette.length] }} />
        </article>
      ))}
    </section>
  );
}
