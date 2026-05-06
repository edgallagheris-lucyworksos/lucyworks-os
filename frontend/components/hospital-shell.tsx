"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { clearSession, getSession, type SessionUser } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type AlertSummary = {
  total_alerts: number;
  high_alerts: number;
};

const sharedCore = [
  { href: "/command", label: "Lucy Command" },
  { href: "/pulse", label: "Lucy Pulse" },
  { href: "/triage", label: "Lucy Flow" },
  { href: "/ethics", label: "Lucy Ethics" },
  { href: "/overnight", label: "Lucy Care" },
  { href: "/hr", label: "LucyRota" },
  { href: "/schedule", label: "Lucy Theatre" },
  { href: "/ward", label: "Lucy Ward" },
  { href: "/catalogues", label: "Lucy Diagnostics" },
  { href: "/pharmacy", label: "Lucy Pharmacy" },
  { href: "/mail", label: "Lucy Comms" },
  { href: "/audit", label: "LucyTrace" },
  { href: "/workspace", label: "My Workspace" },
  { href: "/actions", label: "Actions" },
  { href: "/readiness", label: "Readiness" },
];

const supportLinks = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/flow-state", label: "Flow State" },
  { href: "/stock", label: "Stock" },
  { href: "/discharge", label: "Discharge" },
  { href: "/rooms", label: "Rooms" },
  { href: "/staff", label: "Staff" },
  { href: "/system", label: "System" },
  { href: "/operating-model", label: "Operating Model" },
  { href: "/episodes/EP-1042", label: "Seeded Case" },
];

const roleLinks: Record<string, { href: string; label: string }[]> = {
  ops_manager: [
    ...sharedCore,
    ...supportLinks,
    { href: "/conflicts", label: "Conflicts" },
    { href: "/queues", label: "Queues" },
  ],
  clinician: [
    ...sharedCore,
    { href: "/dashboard", label: "Dashboard" },
    { href: "/flow-state", label: "Flow State" },
    { href: "/discharge", label: "Discharge" },
    { href: "/theatre", label: "Theatre" },
    { href: "/queues", label: "Queues" },
  ],
  nurse: [
    ...sharedCore,
    { href: "/dashboard", label: "Dashboard" },
    { href: "/flow-state", label: "Flow State" },
    { href: "/stock", label: "Stock" },
    { href: "/rooms", label: "Rooms" },
    { href: "/queues", label: "Queues" },
  ],
  admin: [
    ...sharedCore,
    { href: "/dashboard", label: "Dashboard" },
    { href: "/flow-state", label: "Flow State" },
    { href: "/discharge", label: "Discharge" },
    { href: "/stock", label: "Stock" },
    { href: "/consult", label: "Consult" },
    { href: "/input", label: "Input" },
  ],
};

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
    <main className="lw-shell">
      <div className="lw-topbar">
        <div className="lw-wrap">
          <div className="lw-brand-row">
            <div className="lw-brand-title">
              <Link href="/command" className="lw-brand-mark">L</Link>
              <div>
                <div className="lw-product">LucyWorks OS</div>
                <div className="lw-subtitle">{title} • {subtitle}</div>
              </div>
            </div>
            <div className="lw-actions">
              {user ? <span className="lw-pill">{user.name} • {user.role}</span> : <Link className="lw-pill" href="/login">Login</Link>}
              <Link href="/alerts" className={alerts.high_alerts ? "lw-pill lw-alert-pill" : "lw-pill"}>
                Alerts {alerts.total_alerts} / high {alerts.high_alerts}
              </Link>
              <button onClick={() => { clearSession(); window.location.href = "/login"; }} className="lw-pill">
                Sign out
              </button>
            </div>
          </div>
          <div className="lw-nav">
            {(roleLinks[user?.role || "ops_manager"] || roleLinks.ops_manager).map((item) => (
              <Link key={`${item.href}-${item.label}`} href={item.href}>{item.label}</Link>
            ))}
          </div>
        </div>
      </div>
      <div className="lw-main">{children}</div>
    </main>
  );
}
