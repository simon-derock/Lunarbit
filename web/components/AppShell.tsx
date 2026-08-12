"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Icon, type IconName } from "@/components/Icons";
import { ProfileControls } from "@/components/ProfileControls";
import { useProfiles } from "@/components/ProfileProvider";

const navigation: readonly { href: string; label: string; index: string; icon: IconName }[] = [
  { href: "/", label: "Overview", index: "01", icon: "overview" },
  { href: "/graph", label: "Graph explorer", index: "02", icon: "graph" },
  { href: "/economics", label: "Economic terrain", index: "03", icon: "economics" },
  { href: "/transactions", label: "Transactions", index: "04", icon: "transactions" },
  { href: "/evidence", label: "Evidence lab", index: "05", icon: "evidence" },
  { href: "/benchmarks", label: "Benchmarks", index: "06", icon: "benchmark" },
];

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const { query, dataProfile, visualProfile } = useProfiles();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="wordmark" href={`/${query}`} aria-label="Lunarbit overview">
          <span className="mark-orbit"><i /><i /></span>
          <span>LUNARBIT</span>
          <small>ECONOMIC INTELLIGENCE</small>
        </Link>
        <ProfileControls />
        <div className="system-state" aria-label="System state">
          <span><i /> GRAPH ONLINE</span>
          <b>53,983 <small>NODES</small></b>
          <button className="command-key" type="button" aria-label="Open command palette"><Icon name="command" /> K</button>
        </div>
      </header>

      <aside className="sidebar">
        <div className="side-rail-label">LUNARBIT / INTELLIGENCE OS</div>
        <nav aria-label="Primary navigation">
          {navigation.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                className={`nav-item${active ? " active" : ""}`}
                href={`${item.href}${query}`}
                key={item.href}
              >
                <span className="nav-index">{item.index}</span>
                <Icon name={item.icon} />
                <span>{item.label}</span>
                {active && <i className="nav-signal" />}
              </Link>
            );
          })}
        </nav>
        <div className="side-meta">
          <span>ACTIVE MATRIX</span>
          <b>{dataProfile.handle}</b>
          <small>{visualProfile.name}</small>
          <div className="side-code">PFI / 128.6<br />EVID / VERIFIED<br />PRIV / SYNTHETIC</div>
        </div>
      </aside>

      <main className="main-stage" key={`${dataProfile.id}:${visualProfile.id}`}>
        <div className="stage-grid" aria-hidden="true" />
        {children}
      </main>
    </div>
  );
}
