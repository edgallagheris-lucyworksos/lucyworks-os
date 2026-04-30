import Link from "next/link";

const primaryPath = [
  ["/login", "1. Login", "Pick an operating role."],
  ["/dashboard", "2. Dashboard", "Main hospital control surface: 15-minute grid, pressure and action."],
  ["/command", "3. Command", "Priority board, section pressure and accountable owner."],
  ["/episodes/EP-1042", "4. Case", "Case intelligence, readiness, blockers and next owner."],
  ["/operating-model", "5. Operating Model", "Departments, rooms, procedures, anaesthesia, recovery, cleaning and compliance."],
  ["/system", "6. System Map", "Module structure feeding the dashboard."],
];

const surfaces = [
  ["/pulse", "Lucy Pulse", "Whole-hospital pressure feeding the dashboard."],
  ["/triage", "LucyFlow", "Front-door routing and red-flag handoff feeding command."],
  ["/ethics", "Lucy Ethics", "Welfare, consent, owner and financial-risk flags."],
  ["/discharge", "Discharge", "Safe leave chain feeding episode readiness."],
  ["/pharmacy", "Pharmacy", "Medication and compliance blockers feeding flow readiness."],
  ["/stock", "Stock", "Ordering pressure and missing-item blockers."],
  ["/schedule", "Schedule", "Procedure chain feeding the 15-minute dashboard grid."],
  ["/rooms", "Rooms", "Room state feeding the dashboard and conflicts."],
  ["/mail", "Mail Ops", "Owner/comms threads linked to cases and audit."],
  ["/conflicts", "Conflicts", "Operational failures converted to work."],
  ["/queues", "Queues", "Role-owned work by urgency and status."],
  ["/audit", "Audit", "Trace of material actions."],
  ["/staff", "Staff", "Shift/load visibility feeding assignment."],
];

export default function HomePage() {
  return (
    <main className="lw-shell">
      <div className="lw-main" style={{ display: "grid", gap: 24 }}>
        <section className="lw-card" style={{ padding: 32 }}>
          <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyWorks OS / LucyVet OS</div>
          <h1 style={{ fontSize: 58, lineHeight: 0.95, margin: "14px 0 0", letterSpacing: "-0.06em" }}>Dashboard-first hospital command system.</h1>
          <p style={{ marginTop: 18, color: "#cbd5e1", fontSize: 20, maxWidth: 920, lineHeight: 1.45 }}>Every module feeds the operational dashboard: pressure, ethics, triage, schedule, staff, rooms, owner comms, pharmacy, stock, discharge, conflicts and audit.</p>
          <div style={{ marginTop: 24, display: "flex", gap: 12, flexWrap: "wrap" }}>
            <Link href="/dashboard" className="lw-btn-primary" style={{ padding: "12px 16px", borderRadius: 14 }}>Open dashboard</Link>
            <Link href="/login" className="lw-pill">Login</Link>
            <Link href="/command" className="lw-pill">Command</Link>
            <Link href="/episodes/EP-1042" className="lw-pill">Seeded case</Link>
          </div>
        </section>

        <section className="lw-card" style={{ padding: 22 }}>
          <h2 style={{ marginTop: 0 }}>Main operating path</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 12 }}>
            {primaryPath.map(([href, label, text]) => (
              <Link key={href} href={href} style={{ border: "1px solid #1f2937", borderRadius: 16, padding: 16, background: "rgba(15,23,42,0.72)", display: "block" }}>
                <strong>{label}</strong>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
              </Link>
            ))}
          </div>
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
          {surfaces.map(([href, title, text]) => (
            <Link key={href} href={href} className="lw-card" style={{ padding: 18, display: "block" }}>
              <strong>{title}</strong>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
            </Link>
          ))}
        </section>
      </div>
    </main>
  );
}
