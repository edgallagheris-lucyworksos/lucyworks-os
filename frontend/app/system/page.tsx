import Link from "next/link";

const modules = [
  ["Access / Login", "/login", "Role-based demo access for ops, clinician, nurse and admin views."],
  ["Lucy Pulse", "/pulse", "Whole-hospital pressure, risk level, staff pressure, capacity pressure and execution pressure."],
  ["Lucy Ethics", "/ethics", "Welfare, consent, financial constraint, owner communication and escalation risk."],
  ["Command", "/command", "Whole-hospital pressure, section load, red alerts and priority work."],
  ["Triage", "/triage", "Front-door routing, red flags, urgent inputs and escalation."],
  ["Admissions", "/admissions", "Admitted patient flow, inpatient ownership and current ward/ICU load."],
  ["Episodes", "/episodes", "Case spine linking patient, owner, room, phase, results, messages and work."],
  ["Schedule", "/schedule", "Procedure blocks: prep, anaesthesia, procedure, recovery and cleaning."],
  ["Rota", "/rota", "Shift coverage, role pressure and staff load warnings."],
  ["Staff", "/staff", "Live staff load, shift state and assigned schedule blocks."],
  ["Rooms", "/rooms", "Room states across consults, wards, ICU, theatre, recovery and diagnostics."],
  ["Conflicts", "/conflicts", "Operational failures turned into work and tracked through resolution."],
  ["Results", "/results", "Pending clinical result review and action state."],
  ["Discharge", "/discharge", "Blockers, owner update readiness, medication readiness and sign-off pressure."],
  ["Pharmacy", "/pharmacy", "Medication work, legal/compliance flags and patient-linked pharmacy blockers."],
  ["Stock", "/stock", "Ordering pressure, missing items and operational stock blockers."],
  ["Mail Ops", "/mail", "Owner updates and clinical messages linked to live episodes."],
  ["Consult", "/consult", "Consult room workload and follow-up pressure."],
  ["Ward / ICU", "/ward", "Inpatient pressure, blockers, medication and handover work."],
  ["Theatre / Recovery", "/theatre", "Theatre prep, procedure pressure and recovery handoffs."],
  ["Queues", "/queues", "Work queues by ownership and urgency."],
  ["Audit", "/audit", "Action history and operational traceability."],
  ["Product", "/product", "Pitch surface, module map and demo narrative."],
];

export default function SystemPage() {
  return (
    <main style={{ minHeight: "100vh", padding: 24, background: "#020617" }}>
      <div style={{ maxWidth: 1220, margin: "0 auto", display: "grid", gap: 24 }}>
        <section style={{ border: "1px solid #1f2937", borderRadius: 26, padding: 28, background: "#0f172a" }}>
          <div style={{ color: "#14b8a6", fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase" }}>Full system map</div>
          <h1 style={{ margin: "12px 0 0", fontSize: 44, letterSpacing: "-0.04em" }}>LucyWorks OS operating model</h1>
          <p style={{ color: "#94a3b8", maxWidth: 850 }}>A single map of the current demo system: what exists, where it lives, and what each surface is meant to control.</p>
          <div style={{ marginTop: 18, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Link href="/pulse" style={{ background: "#14b8a6", color: "#020617", padding: "10px 14px", borderRadius: 12, fontWeight: 800 }}>Open Pulse</Link>
            <Link href="/ethics" style={{ border: "1px solid #334155", padding: "10px 14px", borderRadius: 12 }}>Open Ethics</Link>
            <Link href="/command" style={{ border: "1px solid #334155", padding: "10px 14px", borderRadius: 12 }}>Open Command</Link>
            <Link href="/episodes/EP-1042" style={{ border: "1px solid #334155", padding: "10px 14px", borderRadius: 12 }}>Open Demo Episode</Link>
          </div>
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
          {modules.map(([name, href, text]) => (
            <Link key={href} href={href} style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 18, background: "#0f172a", display: "block" }}>
              <strong>{name}</strong>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
            </Link>
          ))}
        </section>
      </div>
    </main>
  );
}
