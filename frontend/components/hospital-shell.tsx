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
  { href: "/dashboard", label: "Dashboard" },
  { href: "/flow-state", label: "Flow State" },
  { href: "/overnight", label: "Overnight" },
  { href: "/system", label: "System" },
  { href: "/operating-model", label: "Operating Model" },
  { href: "/pulse", label: "Pulse" },
  { href: "/command", label: "Command" },
  { href: "/episodes/EP-1042", label: "Seeded Case" },
];

const roleLinks: Record<string, { href: string; label: string }[]> = {
  ops_manager: [
    ...sharedCore,
    { href: "/triage", label: "LucyFlow" },
    { href: "/ethics", label: "Ethics" },
    { href: "/discharge", label: "Discharge" },
    { href: "/pharmacy", label: "Pharmacy" },
    { href: "/stock", label: "Stock" },
    { href: "/schedule", label: "Schedule" },
    { href: "/rooms", label: "Rooms" },
    { href: "/staff", label: "Staff" },
    { href: "/mail", label: "Mail Ops" },
    { href: "/conflicts", label: "Conflicts" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
  ],
  clinician: [
    ...sharedCore,
    { href: "/triage", label: "LucyFlow" },
    { href: "/ethics", label: "Ethics" },
    { href: "/discharge", label: "Discharge" },
    { href: "/pharmacy", label: "Pharmacy" },
    { href: "/schedule", label: "Schedule" },
    { href: "/ward", label: "Ward" },
    { href: "/theatre", label: "Theatre" },
    { href: "/mail", label: "Mail Ops" },
    { href: "/queues", label: "Queues" },
  ],
  nurse: [
    ...sharedCore,
    { href: "/triage", label: "LucyFlow" },
    { href: "/discharge", label: "Discharge" },
    { href: "/pharmacy", label: "Pharmacy" },
    { href: "/stock", label: "Stock" },
    { href: "/schedule", label: "Schedule" },
    { href: "/ward", label: "Ward" },
    { href: "/theatre", label: "Theatre" },
    { href: "/rooms", label: "Rooms" },
    { href: "/queues", label: "Queues" },
  ],
  admin: [
    ...sharedCore,
    { href: "/discharge", label: "Discharge" },
    { href: "/stock", label: "Stock" },
    { href: "/mail", label: "Mail Ops" },
    { href: "/consult", label: "Consult" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
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
              <Link href="/dashboard" className="lw-brand-mark">L</Link>
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
              <Link key={item.href} href={item.href}>{item.label}</Link>
            ))}
          </div>
        </div>
      </div>
      <div className="lw-main">{children}</div>
    </main>
  );
}
