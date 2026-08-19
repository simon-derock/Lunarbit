"use client";

import { SectionHeader } from "@/components/SectionHeader";
import { SignalChart } from "@/components/SignalChart";
import { TerrainSurface } from "@/components/TerrainSurface";
import { useProfiles } from "@/components/ProfileProvider";

const factors = [
  ["Comparable price", 68, "+₹9.4K"],
  ["Basket quantity", 49, "+₹6.8K"],
  ["Fees + tax", 31, "+₹4.3K"],
  ["Merchant mix", -36, "−₹5.0K"],
  ["Discounts", -27, "−₹3.7K"],
] as const;

export default function EconomicsPage() {
  const { dataProfile } = useProfiles();
  const personalFoodIndex = dataProfile.timeline.at(-1)?.index.toFixed(1) ?? "—";
  return (
    <div className="page economics-page">
      <SectionHeader eyebrow="03 / FINANCIAL INTELLIGENCE" title="Commerce becomes an economic terrain." description="Matched-price indices, exact spending decomposition, change points, and bounded counterfactuals expose why personal food economics moved—not merely how much was spent." aside={<div className="profile-stamp"><span>PERSONAL FOOD INDEX</span><b>{personalFoodIndex}</b><small>Profile-relative · never a market CPI claim</small></div>} />
      <section className="economic-grid">
        <article className="panel terrain-panel"><header className="panel-header"><div><span>01 / TEMPORAL EVENT SURFACE</span><h2>Personal price topology</h2></div><span className="mono-note">OBSERVED / NORMALIZED</span></header><TerrainSurface /></article>
        <aside className="panel decomposition-panel"><header className="panel-header"><div><span>02 / EXACT DECOMPOSITION</span><h2>Why spend changed</h2></div></header><div className="factor-list">{factors.map(([name, value, amount], index) => <div key={name}><header><span>0{index + 1} / {name}</span><b>{amount}</b></header><i><span className={value < 0 ? "negative" : ""} style={{ width: `${Math.abs(value)}%` }} /></i></div>)}</div><footer><span>RECONCILED DELTA</span><b>+₹11.8K</b><small>Residual ₹0.00 after deterministic allocation</small></footer></aside>
      </section>
      <section className="economics-lower">
        <article className="panel signal-panel"><header className="panel-header"><div><span>03 / MULTI-SIGNAL SERIES</span><h2>Spend, fees, discounts, index</h2></div></header><SignalChart /></article>
        <article className="panel research-loop"><header className="panel-header"><div><span>04 / AUTONOMOUS RESEARCH</span><h2>Hypothesis loop</h2></div></header><div className="loop-orbit"><div className="loop-core">FINDING<br /><b>{dataProfile.findings[0].confidence}</b></div>{["Hypothesis", "Experiment", "Evidence", "Decision"].map((label, index) => <span className={`loop-node loop-${index}`} key={label}>0{index + 1}<b>{label}</b></span>)}</div><p>{dataProfile.findings[0].detail}</p></article>
      </section>
      <footer className="page-disclosure"><span>ECONOMIC SAFETY</span>Descriptive signals and simulations remain explicitly separated from observed financial truth.</footer>
    </div>
  );
}
