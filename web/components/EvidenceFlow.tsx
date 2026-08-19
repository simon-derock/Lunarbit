"use client";

import { useState } from "react";

import { Icon } from "@/components/Icons";
import { useProfiles } from "@/components/ProfileProvider";

const proofKinds = [
  ["MAIL / HTML", "Order confirmation", "message/rfc822"],
  ["PDF / INVOICE", "Customer invoice", "application/pdf"],
  ["EVENT / MONEY", "Scoped total assertion", "deterministic"],
  ["GRAPH / CLAIM", "Economic finding lineage", "verified"],
] as const;

export function EvidenceFlow() {
  const { dataProfile } = useProfiles();
  const [active, setActive] = useState(2);

  return (
    <div className="evidence-workbench">
      <div className="proof-list" role="list" aria-label="Evidence chain">
        {proofKinds.map(([kind, label, format], index) => (
          <button className={active === index ? "active" : ""} key={kind} onClick={() => setActive(index)} type="button">
            <span>0{index + 1}</span><i /><div><small>{kind}</small><strong>{label}</strong><em>{format}</em></div><Icon name="chevron" />
          </button>
        ))}
      </div>
      <div className="proof-inspector">
        <header><span>PROOF REPLAY / 0{active + 1}</span><b>SHA-256 VERIFIED</b></header>
        <div className="proof-document">
          <span className="redaction-line short" /><span className="redaction-line" /><span className="redaction-line medium" />
          <div className="proof-callout"><span>CANONICAL VALUE</span><strong>{active === 2 ? dataProfile.metrics[1].value : "₹468.00"}</strong><small>scope / customer payable · currency / INR</small></div>
          <span className="redaction-line" /><span className="redaction-line short" />
        </div>
        <footer><span>SOURCE TEXT REDACTED</span><span>LOCATOR / P{active + 1}:L{12 + active * 7}</span></footer>
      </div>
      <aside className="truth-ledger">
        <span>DETERMINISTIC DECISIONS</span>
        <dl><div><dt>Document identity</dt><dd>match / 1.00</dd></div><div><dt>Order resolution</dt><dd>canonical</dd></div><div><dt>Money scope</dt><dd>customer_total</dd></div><div><dt>Conflict policy</dt><dd>preserve both</dd></div></dl>
        <p>LLMs propose semantic structure. Code owns identity, money arithmetic, graph truth, and privacy.</p>
      </aside>
    </div>
  );
}
