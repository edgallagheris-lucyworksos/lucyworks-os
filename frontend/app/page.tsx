import Link from "next/link";

const mainPath = [
  ["/system-control", "1. System Control", "Check backend, readiness, workspace, flow-state, catalogues, HR and forecast."],
  ["/readiness", "2. Readiness", "Check what is working, partial or missing."],
  ["/command", "3. Lucy Command", "Open the hospital command surface."],
  ["/workspace", "4. My Workspace", "See the role-owned queue."],
  ["/actions", "5. Actions", "Acknowledge, review, resolve, approve and start work."],
  ["/flow-state", "6. Flow State", "Check live blockers, gates, occupancy and handovers."],
  ["/overnight", "7. Lucy Care", "Check inpatients, overnight carry-over and discharge pressure."],
];

const lucyModules = [
  ["/command", "Lucy Command", "Clinical director / ops command."],
  ["/pulse", "Lucy Pulse", "Operational pressure and risk radar."],
  ["/triage", "Lucy Flow", "Intake, triage, routing and escalation."],
  ["/ethics", "Lucy Ethics", "Welfare, consent and decision-risk."],
  ["/overnight", "Lucy Care", "Admission-to-discharge continuity."],
  ["/hr", "LucyRota", "Staffing, HR, skills and fatigue."],
  ["/schedule", "Lucy Theatre", "15-minute theatre/procedure chain."],
  ["/ward", "Lucy Ward", "Ward, ICU and inpatient board."],
  ["/catalogues", "Lucy Diagnostics", "Diagnostics/procedure/formulary source data."],
  ["/pharmacy", "Lucy Pharmacy", "Formulary, stock and pharmacy readiness."],
  ["/mail", "Lucy Comms", "Owner comms and internal coordination."],
  ["/audit", "LucyTrace", "Audit and governance trail."],
];

export default function HomePage() {
  return (
    <main className="lw-shell">
      <div className="lw-main" style={{ display: "grid", gap: 18 }}>
        <section className="lw-card" style={{ padding: 24 }}>
          <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyWorks OS / mobile launchpad</div>
          <h1 style={{ fontSize: 42, lineHeight: 0.98, margin: "12px 0 0", letterSpacing: "-0.055em" }}>One hospital system. One phone-friendly start point.</h1>
          <p style={{ marginTop: 16, color: "#cbd5e1", fontSize: 18, maxWidth: 920, lineHeight: 1.45 }}>Start at System Control. It checks whether the connected backend, readiness, workspace, flow-state, catalogues, HR and forecast layers are responding as one LucyWorks system.</p>
          <div style={{ marginTop: 20, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Link href="/system-control" className="lw-btn-primary" style={{ padding: "12px 16px", borderRadius: 14 }}>Start here</Link>
            <Link href="/readiness" className="lw-pill">Readiness</Link>
            <Link href="/command" className="lw-pill">Lucy Command</Link>
            <Link href="/actions" className="lw-pill">Actions</Link>
            <Link href="/workspace" className="lw-pill">My Workspace</Link>
          </div>
        </section>

        <section className="lw-card" style={{ padding: 18 }}>
          <h2 style={{ marginTop: 0 }}>Phone operating path</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10 }}>
            {mainPath.map(([href, label, text]) => (
              <Link key={href} href={href} style={{ border: "1px solid #1f2937", borderRadius: 16, padding: 14, background: "rgba(15,23,42,0.72)", display: "block" }}>
                <strong>{label}</strong>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="lw-card" style={{ padding: 18 }}>
          <h2 style={{ marginTop: 0 }}>Lucy module spine</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
            {lucyModules.map(([href, title, text]) => (
              <Link key={title} href={href} style={{ border: "1px solid #1f2937", borderRadius: 16, padding: 14, background: "rgba(15,23,42,0.72)", display: "block" }}>
                <strong>{title}</strong>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
