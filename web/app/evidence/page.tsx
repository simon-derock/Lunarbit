"use client";

import { EvidenceFlow } from "@/components/EvidenceFlow";
import { Icon } from "@/components/Icons";
import { useProfiles } from "@/components/ProfileProvider";
import { SectionHeader } from "@/components/SectionHeader";

export default function EvidencePage() {
  const { dataProfile } = useProfiles();
  return (
    <div className="page evidence-page">
      <SectionHeader eyebrow="05 / EVIDENCE LAB" title="Replay every claim back to proof." description="A forensic workspace for inspecting source locators, canonical money decisions, graph lineage, and the exact evidence set supporting—or refusing—an answer." aside={<div className="profile-stamp"><span>VERIFICATION STATE</span><b>100% LINKED</b><small>Private source content redacted from this synthetic demo</small></div>} />
      <section className="panel evidence-panel"><header className="panel-header"><div><span>01 / CLAIM LINEAGE</span><h2>{dataProfile.findings[0].title}</h2></div><div className="verified-pill"><Icon name="check" /> PROOF COMPLETE</div></header><EvidenceFlow /></section>
      <section className="evidence-lower">
        <article className="panel provenance-panel"><header className="panel-header"><div><span>02 / PROVENANCE CONTRACT</span><h2>Claim support matrix</h2></div></header><div className="support-matrix"><div className="matrix-head"><span>CLAIM</span><span>OBSERVED</span><span>DERIVED</span><span>SIMULATED</span><span>CITED</span></div>{dataProfile.findings.map((finding, index) => <div key={finding.title}><strong>{finding.tag} / {finding.title}</strong><i className={index < 2 ? "on" : ""} /><i className="on" /><i className={index === 2 ? "on amber" : ""} /><i className="on" /></div>)}</div></article>
        <article className="panel abstention-panel"><header className="panel-header"><div><span>03 / GOVERNANCE</span><h2>Abstention is a feature</h2></div></header><div className="abstention-signal"><span>INSUFFICIENT EVIDENCE</span><b>REFUSE → EXPLAIN → REQUEST</b><p>When scope, identity, or citation coverage fails, Lunarbit does not manufacture an answer. The failed gate and missing proof are surfaced directly.</p></div><div className="gate-list">{["Identity closed", "Money reconciled", "Temporal scope", "Citation support"].map((gate, index) => <span key={gate}><Icon name={index === 2 ? "spark" : "check"} />{gate}<b>{index === 2 ? "REVIEW" : "PASS"}</b></span>)}</div></article>
      </section>
      <footer className="page-disclosure"><span>PRIVACY BOUNDARY</span>{dataProfile.disclosure} Source bytes and personal identifiers never enter the public interface.</footer>
    </div>
  );
}
