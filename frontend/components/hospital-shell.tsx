"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { clearSession, getSession, type SessionUser } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type AlertSummary = {
  total_alerts: number;
  high_alerts: number;
};

const roleLinks: Record<string, { href: string; label: string }[]> = {
  ops_manager: [
    { href: "/command", label: "Command" },
    { href: "/schedule", label: "Schedule" },
    { href: "/conflicts", label: "Conflicts" },
    { href: "/episodes", label: "Episodes" },
    { href: "/rooms", label: "Rooms" },
    { href: "/results", label: "Results" },
    { href: "/mail", label: "Mail Ops" },
    { href: "/consult", label: "Consult" },
    { href: "/ward", label: "Ward" },
    { href: "/theatre", label: "Theatre" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
  ],
  clinician: [
    { href: "/command", label: "Command" },
    { href: "/schedule", label: "Schedule" },
    { href: "/conflicts", label: "Conflicts" },
    { href: "/episodes", label: "Episodes" },
    { href: "/results", label: "Results" },
    { href: "/mail", label: "Mail Ops" },
    { href: "/consult", label: "Consult" },
    { href: "/ward", label: "Ward" },
    { href: "/theatre", label: "Theatre" },
    { href: "/queues", label: "Queues" },
    { href: "/alerts", label: "Alerts" },
  ],
  nurse: [
    { href: "/episodes", label: "Episodes" },
    { href: "/schedule", label: "Schedule" },
    { href: "/conflicts", label: "Conflicts" },
    { href: "/rooms", label: "Rooms" },
    { href: "/ward", label: "Ward" },
    { href: "/theatre", label: "Theatre" },
    { href: "/queues", label: "Queues" },
    { href: "/alerts", label: "Alerts" },
    { href: "/input", label: "Input" },
  ],
  admin: [
    { href: "/episodes", label: "Episodes" },
    { href: "/mail", label: "Mail Ops" },
    { href: "/consult", label: "Consult" },
    { href: "/queues", label: "Queues" },
    { href: "/alerts", label: "Alerts" },
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
    <main style={{ minHeight: "100vh", background: "#020617" }}>
      <div style={{ borderBottom: "1px solid #1f2937", background: "#0f172a" }}>
        <div style={{ maxWidth: 1320, margin: "0 auto", padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em" }}>LucyWorks OS</div>
              <div style={{ color: "#94a3b8", marginTop: 4 }}>{title} • {subtitle}</div>
            </div>
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              {user ? <span style={{ color: "#94a3b8" }}>{user.name} • {user.role}</span> : null}
              <Link href="/alerts" style={{ border: "1px solid #334155", borderRadius: 999, padding: "8px 12px" }}>
                Alerts {alerts.total_alerts} / high {alerts.high_alerts}
              </Link>
              <button onClick={() => { clearSession(); window.location.href = "/login"; }} style={{ borderRadius: 10, padding: "8px 12px" }}>
                Sign out
              </button>
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 14 }}>
            {(roleLinks[user?.role || ""] || []).map((item) => (
              <Link key={item.href} href={item.href} style={{ border: "1px solid #334155", borderRadius: 10, padding: "8px 12px" }}>
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
      <div style={{ maxWidth: 1320, margin: "0 auto", padding: 24 }}>{children}</div>
    </main>
  );
}
