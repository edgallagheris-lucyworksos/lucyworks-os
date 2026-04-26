import Link from "next/link";

const links = [
  ["/system", "System Map"],
  ["/product", "Product"],
  ["/login", "Access"],
  ["/pulse", "Pulse"],
  ["/ethics", "Ethics"],
  ["/command", "Command"],
  ["/triage", "Triage"],
  ["/admissions", "Admissions"],
  ["/schedule", "Schedule"],
  ["/rota", "Rota"],
  ["/discharge", "Discharge"],
  ["/pharmacy", "Pharmacy"],
  ["/stock", "Stock"],
  ["/episodes", "Episodes"],
  ["/staff", "Staff"],
  ["/conflicts", "Conflicts"],
  ["/rooms", "Rooms"],
  ["/results", "Results"],
  ["/mail", "Mail Ops"],
  ["/consult", "Consult"],
  ["/ward", "Ward / ICU"],
  ["/theatre", "Theatre / Recovery"],
  ["/queues", "Queues"],
  ["/audit", "Audit"],
];

export default function HomePage() {
  return (
    <main style={{ minHeight: "100vh", padding: 24, background: "#020617" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gap: 24 }}>
        <section style={{ border: "1px solid #1f2937", borderRadius: 28, padding: 32, background: "#0f172a" }}>
          <div style={{ color: "#14b8a6", fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase" }}>Hospital Operations Engine</div>
          <h1 style={{ fontSize: 52, lineHeight: 1, margin: "14px 0 0", letterSpacing: "-0.04em" }}>LucyWorks OS</h1>
          <p style={{ marginTop: 16, color: "#cbd5e1", fontSize: 20, maxWidth: 820 }}>Run the hospital. Not just the schedule.</p>
          <p style={{ marginTop: 10, color: "#94a3b8", maxWidth: 900 }}>
            Case-driven operational control for specialist veterinary hospitals: Pulse, Ethics, triage, admissions, episodes, rooms, schedule blocks, rota, discharge, pharmacy, stock, conflicts, results, comms, work ownership, staff availability, and audit trail.
          </p>
          <div style={{ marginTop: 24, display: "flex", gap: 12, flexWrap: "wrap" }}>
            <Link href="/pulse" style={{ background: "#14b8a6", color: "#020617", padding: "12px 16px", borderRadius: 12, fontWeight: 700 }}>Open Pulse</Link>
            <Link href="/ethics" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>Open Ethics</Link>
            <Link href="/command" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>Open Command</Link>
            <Link href="/system" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>Open System Map</Link>
            <Link href="/episodes/EP-1042" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>Open Example Case</Link>
          </div>
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          {[
            ["Pulse", "Whole-hospital pressure, risk, capacity, staffing and execution state."],
            ["Ethics", "Welfare, consent, owner communication, financial constraint and escalation risk."],
            ["Triage", "Front-door routing, red flags, urgent inputs and escalation."],
            ["Admissions", "Admitted patient flow, inpatient ownership and current ward/ICU load."],
            ["Schedule", "Prep → anaesthesia → procedure → recovery → cleaning as operational blocks."],
            ["Rota", "Shift coverage, staff pressure and assigned block warnings."],
            ["Conflicts", "Room, chain, handoff, and review problems surfaced as action."],
            ["Audit", "Every action becomes a traceable operational record."],
          ].map(([title, text]) => (
            <div key={title} style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 18, background: "#0f172a" }}>
              <strong>{title}</strong>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
            </div>
          ))}
        </section>

        <section style={{ border: "1px solid #1f2937", borderRadius: 22, padding: 20, background: "#0f172a" }}>
          <h2 style={{ marginTop: 0 }}>Control surfaces</h2>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {links.map(([href, label]) => (
              <Link key={href} href={href} style={{ border: "1px solid #334155", padding: "10px 12px", borderRadius: 12 }}>{label}</Link>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
