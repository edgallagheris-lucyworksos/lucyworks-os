"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { clearSession, getSession, type SessionUser } from "@/lib/session";

type AlertSummary = { total_alerts?: number; high_alerts?: number; totalAlerts?: number; highAlerts?: number };

const primary = [
  { href: "/workspace", label: "Patients" },
  { href: "/hospital-board", label: "Hospital today" },
  { href: "/referral-intake", label: "Referrals" },
  { href: "/input", label: "Quick input" },
  { href: "/my-shift", label: "My work" },
];

const more = [
  { href: "/clinical-execution", label: "Patient work" },
  { href: "/patient-record", label: "Patient record" },
  { href: "/resources", label: "Resources" },
  { href: "/workforce-rota", label: "Rota" },
  { href: "/control-plane", label: "Safety control" },
  { href: "/system-control", label: "System tools" },
];

export function HospitalShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [alerts, setAlerts] = useState({ total: 0, high: 0 });

  useEffect(() => {
    setUser(getSession()?.user || null);
    async function loadAlerts() {
      try {
        const data = await apiGet<AlertSummary>("/api/alerts");
        setAlerts({ total: data.total_alerts ?? data.totalAlerts ?? 0, high: data.high_alerts ?? data.highAlerts ?? 0 });
      } catch {
        setAlerts({ total: 0, high: 0 });
      }
    }
    void loadAlerts();
  }, []);

  return <main className="lw-shell lw-cinematic-bg">
    <div className="lw-topbar lw-glass-topbar">
      <div className="lw-wrap">
        <div className="lw-brand-row">
          <Link href="/workspace" className="lw-brand-title lw-wordmark-link">
            <span className="lw-orbit-mark small"><span /></span>
            <span><span className="lw-product lw-wordmark">lucyworks</span><span className="lw-subtitle">{title} · {subtitle}</span></span>
          </Link>
          <div className="lw-actions">
            {user ? <span className="lw-pill">{user.name} · {user.role}</span> : <Link className="lw-pill" href="/login">Login</Link>}
            <Link href="/alerts" className={alerts.high ? "lw-pill lw-alert-pill" : "lw-pill"}>Alerts {alerts.total}{alerts.high ? ` · ${alerts.high} high` : ""}</Link>
            <button onClick={() => { clearSession(); window.location.href = "/login"; }} className="lw-pill">Sign out</button>
          </div>
        </div>
        <nav className="lw-nav lw-primary-nav" aria-label="Primary hospital navigation">
          {primary.map(item => <Link key={item.href} href={item.href}>{item.label}</Link>)}
        </nav>
        <details style={{ marginTop: 7 }}>
          <summary className="lw-pill" style={{ width: "max-content", cursor: "pointer" }}>More tools</summary>
          <nav className="lw-nav lw-secondary-nav" aria-label="Additional hospital tools">
            {more.map(item => <Link key={item.href} href={item.href}>{item.label}</Link>)}
          </nav>
        </details>
      </div>
    </div>
    <div className="lw-main">{children}</div>
  </main>;
}
