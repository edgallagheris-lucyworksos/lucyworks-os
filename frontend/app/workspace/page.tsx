"use client";

import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { clearSession } from "@/lib/session";

const coreLinks = [
  { href: "/system", label: "System Map", text: "Operating spine and system map." },
  { href: "/operating-model", label: "Operating Model", text: "Departments, rooms, specialisms, procedure timings, pharmacy and compliance guardrails." },
  { href: "/pulse", label: "Lucy Pulse", text: "Hospital pressure, risk and next action." },
  { href: "/command", label: "Clinical Director / Command", text: "Priority board, section pressure and accountable ownership." },
  { href: "/episodes/EP-1042", label: "Seeded Episode Command", text: "Case intelligence, blockers, readiness and next owner." },
];

const roleLinks: Record<string, { href: string; label: string }[]> = {
  ops_manager: [
    { href: "/triage", label: "LucyFlow" },
    { href: "/ethics", label: "Lucy Ethics" },
    { href: "/discharge", label: "Discharge" },
    { href: "/pharmacy", label: "Pharmacy" },
    { href: "/stock", label: "Stock" },
    { href: "/consult", label: "Consult Rooms" },
    { href: "/ward", label: "Ward / ICU" },
    { href: "/theatre", label: "Theatre / Recovery" },
    { href: "/schedule", label: "Schedule" },
    { href: "/staff", label: "Staff" },
    { href: "/rooms", label: "Rooms" },
    { href: "/conflicts", label: "Conflicts" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
    { href: "/input", label: "New input" },
  ],
  clinician: [
    { href: "/triage", label: "LucyFlow" },
    { href: "/ethics", label: "Lucy Ethics" },
    { href: "/discharge", label: "Discharge" },
    { href: "/pharmacy", label: "Pharmacy" },
    { href: "/consult", label: "Consult Rooms" },
    { href: "/ward", label: "Ward / ICU" },
    { href: "/theatre", label: "Theatre / Recovery" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
  ],
  nurse: [
    { href: "/triage", label: "LucyFlow" },
    { href: "/discharge", label: "Discharge" },
    { href: "/pharmacy", label: "Pharmacy" },
    { href: "/stock", label: "Stock" },
    { href: "/ward", label: "Ward / ICU" },
    { href: "/theatre", label: "Theatre / Recovery" },
    { href: "/rooms", label: "Rooms" },
    { href: "/queues", label: "Queues" },
    { href: "/input", label: "New input" },
  ],
  admin: [
    { href: "/discharge", label: "Discharge" },
    { href: "/stock", label: "Stock" },
    { href: "/consult", label: "Consult Rooms" },
    { href: "/input", label: "New input" },
    { href: "/queues", label: "Queues" },
    { href: "/audit", label: "Audit" },
  ],
};

export default function WorkspacePage() {
  return (
    <AuthGuard>
      {(user) => (
        <main className="lw-shell">
          <div className="lw-main" style={{ display: "grid", gap: 22 }}>
            <section className="lw-card" style={{ padding: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                <div>
                  <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Workspace</div>
                  <h1 style={{ margin: "8px 0 0", fontSize: 42, letterSpacing: "-0.05em" }}>LucyWorks OS operating console</h1>
                  <p style={{ color: "#94a3b8" }}>Logged in as {user.name} • {user.role}</p>
                </div>
                <button onClick={() => { clearSession(); window.location.href = "/login"; }} className="lw-pill">Sign out</button>
              </div>
            </section>

            <section className="lw-card" style={{ padding: 20 }}>
              <h2 style={{ marginTop: 0 }}>Core operating surfaces</h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
                {coreLinks.map((item) => (
                  <Link key={item.href} href={item.href} className="lw-card" style={{ padding: 16, display: "block" }}>
                    <strong>{item.label}</strong>
                    <p style={{ color: "#94a3b8", marginBottom: 0 }}>{item.text}</p>
                  </Link>
                ))}
              </div>
            </section>

            <section>
              <h2>Role surfaces</h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                {(roleLinks[user.role] || []).map((item) => (
                  <Link key={item.href} href={item.href} className="lw-card" style={{ padding: 18 }}>
                    <strong>{item.label}</strong>
                    <div style={{ color: "#94a3b8", marginTop: 8 }}>{item.href}</div>
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </main>
      )}
    </AuthGuard>
  );
}
