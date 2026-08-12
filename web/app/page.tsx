"use client";

import Link from "next/link";

import { ConstellationGraph } from "@/components/ConstellationGraph";
import { Icon } from "@/components/Icons";
import { MetricRail } from "@/components/MetricRail";
import { useProfiles } from "@/components/ProfileProvider";
import { openQueryConsole } from "@/components/QueryConsole";
import { SectionHeader } from "@/components/SectionHeader";
import { SignalChart } from "@/components/SignalChart";

export default function OverviewPage() {
  const { dataProfile, visualProfile, query } = useProfiles();
  return (
    <div className="page overview-page">
      <SectionHeader
        eyebrow={`${dataProfile.handle} / ${dataProfile.years}`}
        title="Personal commerce, reconstructed as evidence."
        description={`${dataProfile.archetype}. Every number resolves through deterministic financial events, graph lineage, and source-verification gates.`}
        aside={
          <div className="profile-stamp">
            <span>ACTIVE RENDER</span>
            <b>{visualProfile.name}</b>
            <small>{visualProfile.description}</small>
          </div>
        }
      />
      <MetricRail />

      <section className="overview-grid">
        <article className="panel graph-panel">
          <header className="panel-header">
            <div><span>01 / LIVE TOPOLOGY</span><h2>Evidence constellation</h2></div>
            <Link href={`/graph${query}`}>OPEN EXPLORER <Icon name="arrow" /></Link>
          </header>
          <ConstellationGraph />
        </article>

        <aside className="overview-side">
          <article className="panel finding-panel">
            <header className="panel-header"><div><span>02 / RESEARCH AGENT</span><h2>Verified findings</h2></div><i className="live-dot" /></header>
            <div className="finding-list">
              {dataProfile.findings.map((finding, index) => (
                <div className="finding" key={finding.title}>
                  <span className="finding-index">0{index + 1}</span>
                  <div><small>{finding.tag} / CONF {finding.confidence}</small><strong>{finding.title}</strong><p>{finding.detail}</p></div>
                </div>
              ))}
            </div>
            <Link className="text-link" href={`/economics${query}`}>ENTER ECONOMIC TERRAIN <Icon name="arrow" /></Link>
          </article>

          <article className="panel ask-panel">
            <header className="panel-header"><div><span>03 / ASK LUNARBIT</span><h2>Interrogate the graph</h2></div><Icon name="spark" /></header>
            <div className="question-list">
              {dataProfile.questions.map((question, index) => (
                <button key={question} onClick={() => openQueryConsole(question)} type="button"><span>Q{index + 1}</span>{question}<Icon name="chevron" /></button>
              ))}
            </div>
          </article>
        </aside>
      </section>

      <section className="panel signal-panel">
        <header className="panel-header">
          <div><span>04 / TEMPORAL ECONOMICS</span><h2>Six-year signal field</h2></div>
          <div className="verified-pill"><Icon name="check" /> CANONICAL ORACLE VERIFIED</div>
        </header>
        <SignalChart />
      </section>

      <footer className="page-disclosure"><span>SYNTHETIC MIRROR</span>{dataProfile.disclosure} <b>No private source text is rendered.</b></footer>
    </div>
  );
}
