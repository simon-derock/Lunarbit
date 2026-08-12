"use client";

import { ConstellationGraph } from "@/components/ConstellationGraph";
import { Icon } from "@/components/Icons";
import { useProfiles } from "@/components/ProfileProvider";
import { SectionHeader } from "@/components/SectionHeader";

const retrievalStages = ["Exact identifiers", "Lucene / BM25", "MRL / HNSW", "Graph expansion", "Cohere rerank", "Evidence gate"];

export default function GraphPage() {
  const { dataProfile, visualProfile } = useProfiles();
  const kinds = Array.from(new Set(dataProfile.nodes.map((node) => node.kind)));
  return (
    <div className="page graph-explorer-page">
      <SectionHeader eyebrow="02 / GRAPH EXPLORER" title="Navigate the truth topology." description="Trace orders through merchants, components, temporal events, and source proofs. Selection never crosses the active synthetic profile boundary." aside={<div className="profile-stamp"><span>LAYOUT ENGINE</span><b>{visualProfile.rendering.toUpperCase()}</b><small>{dataProfile.nodes.length} visible nodes · {dataProfile.edges.length} typed relations</small></div>} />
      <section className="graph-workspace">
        <article className="panel graph-canvas-panel"><header className="panel-header"><div><span>01 / INTERACTIVE SUBGRAPH</span><h2>{dataProfile.handle} evidence neighborhood</h2></div><div className="verified-pill"><Icon name="check" /> PROFILE CLOSED</div></header><ConstellationGraph /></article>
        <aside className="graph-control-stack">
          <article className="panel taxonomy-panel"><header className="panel-header"><div><span>02 / ONTOLOGY</span><h2>Visible classes</h2></div></header><div className="taxonomy-list">{kinds.map((kind, index) => <div key={kind}><i style={{ background: visualProfile.palette[index % 5] }} /><span>{kind}</span><b>{dataProfile.nodes.filter((node) => node.kind === kind).length.toString().padStart(2, "0")}</b></div>)}</div></article>
          <article className="panel relation-panel"><header className="panel-header"><div><span>03 / RELATIONSHIPS</span><h2>Typed edges</h2></div></header><div className="relation-list">{dataProfile.edges.map((edge) => <div key={edge.id}><span>{edge.relation}</span><small>{edge.source.split(":").at(-1)} → {edge.target.split(":").at(-1)}</small></div>)}</div></article>
        </aside>
      </section>
      <section className="panel retrieval-panel"><header className="panel-header"><div><span>04 / HYBRID RETRIEVAL TRACE</span><h2>Question-to-proof execution path</h2></div><small className="mono-note">RRF / APPLICATION OWNED</small></header><div className="retrieval-trace">{retrievalStages.map((stage, index) => <div key={stage}><span>0{index + 1}</span><i /><strong>{stage}</strong><small>{index < 5 ? "candidate state preserved" : "citations or abstain"}</small></div>)}</div></section>
      <footer className="page-disclosure"><span>GRAPH CONTRACT</span>Every edge resolves within <b>{dataProfile.handle}</b>; unresolved endpoints fail ingestion.</footer>
    </div>
  );
}
