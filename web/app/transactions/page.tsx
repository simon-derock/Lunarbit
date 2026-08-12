"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/Icons";
import { useProfiles } from "@/components/ProfileProvider";
import { SectionHeader } from "@/components/SectionHeader";
import { deriveTransactionMoney } from "@/lib/demo-finance";

const merchantAliases = ["Ember Kitchen", "Common Table", "Citrus Counter", "Nightjar Foods", "Green Assembly"];

export default function TransactionsPage() {
  const { dataProfile } = useProfiles();
  const [active, setActive] = useState(0);
  const transactions = useMemo(() => dataProfile.timeline.slice().reverse().map((point, index) => {
    const money = deriveTransactionMoney(point.spend, point.fees, point.discount);
    return {
      id: `${dataProfile.handle.split(" / ")[0]}-${point.period}-${String(index + 1).padStart(3, "0")}`,
      merchant: merchantAliases[(index + dataProfile.id.length) % merchantAliases.length],
      date: `${12 + index} AUG 20${point.period}`,
      item: dataProfile.nodes.find((node) => node.kind === "item")?.label ?? "Comparable meal",
      ...money,
      status: index === 2 ? "CONFLICT PRESERVED" : "RECONCILED",
      source: index % 3 === 0 ? "MAIL ONLY" : "MAIL + PDF",
    };
  }), [dataProfile]);
  const selected = transactions[active] ?? transactions[0];

  return (
    <div className="page transactions-page">
      <SectionHeader eyebrow="04 / TRANSACTION BUNDLES" title="Every order, reconciled—not flattened." description="Mail confirmations and invoices become one canonical order bundle while conflicting scopes, discounts, fees, and documentary lineage remain inspectable." aside={<div className="profile-stamp"><span>ACTIVE LEDGER</span><b>{dataProfile.metrics[0].value}</b><small>{dataProfile.metrics[0].label} · {dataProfile.metrics[0].delta}</small></div>} />
      <section className="transaction-workspace">
        <article className="panel transaction-list-panel">
          <header className="transaction-toolbar"><div><span>CANONICAL LEDGER / RECENT</span><b>{transactions.length} representative events</b></div><div className="ledger-filters"><button className="active" type="button">ALL</button><button type="button">CONFLICTS</button><button type="button">MAIL ONLY</button></div></header>
          <div className="transaction-table" role="list">{transactions.map((transaction, index) => <button className={active === index ? "active" : ""} key={transaction.id} onClick={() => setActive(index)} type="button"><span className="transaction-date">{transaction.date}</span><span className="transaction-merchant"><i /><b>{transaction.merchant}</b><small>{transaction.item}</small></span><span className="transaction-source">{transaction.source}</span><span className="transaction-status">{transaction.status}</span><strong>₹{transaction.total}</strong><Icon name="chevron" /></button>)}</div>
        </article>
        {selected && <aside className="panel receipt-panel">
          <header><span>ORDER BUNDLE</span><strong>{selected.id}</strong><small>{selected.date} / ASIA-KOLKATA</small></header>
          <div className="receipt-merchant"><i /><div><b>{selected.merchant}</b><small>PUBLIC REVIEW ALIAS</small></div></div>
          <dl><div><dt>Item subtotal</dt><dd>₹{selected.subtotal}</dd></div><div><dt>Fees + tax</dt><dd>₹{selected.fees}</dd></div><div className="discount"><dt>Promotion benefit</dt><dd>−₹{selected.discount}</dd></div><div className="receipt-total"><dt>Customer total</dt><dd>₹{selected.total}</dd></div></dl>
          <div className="receipt-proof"><span><Icon name="check" /> {selected.status}</span><small>{selected.source} · 2 scoped assertions</small></div>
          <footer><span>EVIDENCE CELLS</span><div>{["merchant", "items", "money", "time", "proof"].map((value) => <i key={value}>{value}</i>)}</div></footer>
        </aside>}
      </section>
      <footer className="page-disclosure"><span>RECONCILIATION POLICY</span>Document disagreement is represented as graph state; it is never silently averaged or discarded.</footer>
    </div>
  );
}
