"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { clearSession, getSession, type SessionUser } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type AlertSummary = { total_alerts: number; high_alerts: number };

const primaryNav = [
  { href: "/hospital-board", label: "NOW" },
  { href: "/flow", label: "FLOW" },
  { href: "/resources", label: "RESOURCES" },
  { href: "/my-shift", label: "MY SHIFT" },
  { href: "/interrupts", label: "INTERRUPTS" },
  { href: "/cases", label: "CASES" },
  { href: "/audit", label: "GOVERNANCE" },
];

const secondaryNav = [
  { href: "/manager-dashboard", label: "Manager" },
  { href: "/nurse-dashboard", label: "Nurse" },
  { href: "/pca-dashboard", label: "PCA" },
  { href: "/system-control", label: "System" },
  { href: "/pharmacy", label: "Pharmacy" },
  { href: "/mail", label: "Comms" },
];

export function HospitalShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [alerts, setAlerts] = useState<AlertSummary>({ total_alerts: 0, high_alerts: 0 });

  useEffect(() => {
    const session = getSession();
    setUser(session?.user || null);
    async function loadAlerts() {
      try {
        const res = await fetch(`${API_BASE}/api/alerts`, { cache: "no-store" });
        const data = await res.json();
        setAlerts({ total_alerts: data.total_alerts || 0, high_alerts: data.high_alerts || 0 });
      } catch {
        setAlerts({ total_alerts: 0, high_alerts: 0 });
      }
    }
    loadAlerts();
  }, []);

  return (
    <main className="lw-shell lw-cinematic-bg">
      <div className="lw-topbar lw-glass-topbar">
        <div className="lw-wrap">
          <div className="lw-brand-row">
            <Link href="/hospital-board" className="lw-brand-title lw-wordmark-link">
              <span className="lw-orbit-mark small"><span /></span>
              <span>
                <span className="lw-product lw-wordmark">lucyworks</span>
                <span className="lw-subtitle">Operational Integrity OS • {title} • {subtitle}</span>
              </span>
            </Link>
            <div className="lw-actions">
              {user ? <span className="lw-pill">{user.name} • {user.role}</span> : <Link className="lw-pill" href="/login">Login</Link>}
              <Link href="/alerts" className={alerts.high_alerts ? "lw-pill lw-alert-pill" : "lw-pill"}>Alerts {alerts.total_alerts} / high {alerts.high_alerts}</Link>
              <button onClick={() => { clearSession(); window.location.href = "/login"; }} className="lw-pill">Sign out</button>
            </div>
          </div>
          <div className="lw-nav lw-primary-nav">
            {primaryNav.map((item) => <Link key={item.href} href={item.href}>{item.label}</Link>)}
          </div>
          <div className="lw-nav lw-secondary-nav">
            {secondaryNav.map((item) => <Link key={item.href} href={item.href}>{item.label}</Link>)}
          </div>
        </div>
      </div>
      <div className="lw-main">{children}</div>
    </main>
  );
}
