"use client";

import { Icon } from "@/components/Icons";
import { SectionHeader } from "@/components/SectionHeader";

const dimensions = [
  { dimension: 256, hit: 97.5, mrr: .975, p50: 6.75, p95: 8.49, candidate: true },
  { dimension: 512, hit: 97.5, mrr: .975, p50: 7.88, p95: 11.93 },
  { dimension: 1024, hit: 97.5, mrr: .975, p50: 8.76, p95: 15.06 },
  { dimension: 1536, hit: 97.5, mrr: .975, p50: 10.99, p95: 14.15, reference: true },
] as const;

const qualityGates = [
  ["Graph closure", "PASS", "53,983 nodes"],
  ["Embedding coverage", "PASS", "24,675 / 24,675"],
  ["Relevance-set queries", "PASS", "40 balanced"],
  ["Natural-language golden set", "PENDING", "human review"],
] as const;

export default function BenchmarksPage() {
  return (
    <div className="page benchmarks-page">
      <SectionHeader eyebrow="06 / EVALUATION CONTROL" title="Benchmarks with the caveats left in." description="Retrieval quality, latency, dimensional ablations, and governance gates are versioned as product evidence. Diagnostic failures remain visible instead of being polished away." aside={<div className="profile-stamp"><span>PROTOCOL</span><b>RELEVANCE-SET V2</b><small>Cohere Embed v4 · HNSW · 40 balanced queries</small></div>} />
      <section className="benchmark-hero">
        <article className="panel mrl-panel"><header className="panel-header"><div><span>01 / MRL ABLATION</span><h2>Recall retained as vectors compress</h2></div><div className="verified-pill"><Icon name="check" /> VERSIONED ARTIFACT</div></header><div className="dimension-chart">{dimensions.map((row) => <div className={"candidate" in row && row.candidate ? "candidate" : ""} key={row.dimension}><header><span>{row.dimension}D</span><b>{row.hit}%</b><small>HIT@10</small></header><i><span style={{ height: `${row.hit}%` }} /></i><footer>{"candidate" in row && row.candidate ? "CANDIDATE" : "reference" in row && row.reference ? "REFERENCE" : "NON-INFERIOR"}</footer></div>)}</div><p className="benchmark-caveat">Relevance is normalized semantic-summary equivalence over balanced unique and ambiguous strata. This does not replace a human-reviewed user-query golden set.</p></article>
        <aside className="panel latency-panel"><header className="panel-header"><div><span>02 / LOCAL HNSW</span><h2>Latency field</h2></div></header><div className="latency-list">{dimensions.map((row) => <div key={row.dimension}><span>{row.dimension}D</span><i><b style={{ width: `${row.p50 / 16 * 100}%` }} /></i><strong>{row.p50.toFixed(2)} ms</strong><small>P95 {row.p95.toFixed(2)}</small></div>)}</div><div className="latency-delta"><span>PROVISIONAL GAIN</span><b>−38.6%</b><small>256D p50 versus native 1536D</small></div></aside>
      </section>
      <section className="benchmark-lower">
        <article className="panel benchmark-table-panel"><header className="panel-header"><div><span>03 / FULL MEASUREMENTS</span><h2>Dimensional comparison</h2></div></header><table><thead><tr><th>INDEX</th><th>HIT@1</th><th>HIT@5</th><th>HIT@10</th><th>MRR</th><th>P50</th><th>ROLE</th></tr></thead><tbody>{dimensions.map((row) => <tr key={row.dimension}><td>MRL_{row.dimension}</td><td>{row.hit}%</td><td>{row.hit}%</td><td>{row.hit}%</td><td>{row.mrr}</td><td>{row.p50.toFixed(2)}ms</td><td>{"candidate" in row ? "candidate" : "reference" in row ? "reference" : "ablation"}</td></tr>)}</tbody></table></article>
        <article className="panel quality-panel"><header className="panel-header"><div><span>04 / RELEASE GATES</span><h2>Measured readiness</h2></div></header><div className="quality-gates">{qualityGates.map(([name, state, detail]) => <div key={name}><Icon name={state === "PASS" ? "check" : "spark"} /><span><b>{name}</b><small>{detail}</small></span><strong className={state === "PASS" ? "pass" : "pending"}>{state}</strong></div>)}</div></article>
      </section>
      <footer className="page-disclosure"><span>EVALUATION INTEGRITY</span>The superseded exact-chunk benchmark remains documented as a diagnostic example of duplicate-evidence metric failure.</footer>
    </div>
  );
}
