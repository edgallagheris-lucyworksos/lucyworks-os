import Link from "next/link";
import { DomainAutomationPanel } from "@/components/domain-automation-panel";
import { DomainPressurePanel } from "@/components/domain-pressure-panel";

const spine = [
  ["Patient", "The living case context: species, owner, current episode and clinical state."],
  ["Owner", "Consent, cost, communication, expectations and safeguarding pressure."],
  ["Episode", "The single operational truth record linking location, phase, staff, decisions and blockers."],
  ["Location", "Room, ward, ICU, theatre, recovery or discharge state."],
  ["Team", "Specialist, clinician, nurse, admin or ops owner responsible for the next step."],
  ["Decision", "Clinical, operational, ethical or owner-facing decision that must be resolved."],
  ["Action", "Concrete work item, comms, pharmacy request, stock order, result review or care task."],
  ["Escalation", "Red flags and unresolved risk moved to the right accountable role."],
  ["Audit", "Every material action recorded so the hospital can see what happened and why."],
];

const modules = [
  ["Lucy Pulse", "/pulse", "Interprets whole-hospital pressure and identifies the dominant source of risk."],
  ["Command", "/command", "Turns pressure into owner-led next action across sections and cases."],
  ["Episode Command", "/episodes/EP-1042", "Case brain: patient, owner, decisions, blockers, readiness, timeline and audit."],
  ["LucyFlow", "/triage", "Front-door triage signal, route, red flags and handoff trigger."],
  ["Lucy Ethics", "/ethics", "Welfare, consent, financial constraint and escalation risk."],
  ["Discharge", "/discharge", "Safe leave chain: signoff, medication, owner update, results and instructions."],
  ["Pharmacy", "/pharmacy", "Medication requests, compliance flags and patient-linked pharmacy blockers."],
  ["Stock", "/stock", "Ordering pressure, missing items and consumable blockers."],
  ["Schedule", "/schedule", "Procedure chain: prep, anaesthesia, procedure, recovery and cleaning."],
  ["Rooms", "/rooms", "Room state control across consults, wards, ICU, theatre, recovery and diagnostics."],
  ["Mail Ops", "/mail", "Owner updates and clinical messages linked to live episodes."],
  ["Conflicts", "/conflicts", "Operational failures converted into work and tracked through resolution."],
  ["Queues", "/queues", "Role-owned work queues by urgency, owner and status."],
  ["Audit", "/audit", "Action history and operational traceability."],
];

export default function SystemPage() {
  return (
    <main className="lw-shell">
      <div className="lw-main" style={{ display: "grid", gap: 24 }}>
        <section className="lw-card" style={{ padding: 28 }}>
          <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyWorks OS / LucyVet OS</div>
          <h1 style={{ margin: "12px 0 0", fontSize: 48, letterSpacing: "-0.05em" }}>Hospital command system, not a checklist app.</h1>
          <p style={{ color: "#94a3b8", maxWidth: 920, fontSize: 18, lineHeight: 1.55 }}>The system is built around the operational chain that actually matters in a specialist hospital: a case enters, pressure appears, ownership is assigned, blockers are cleared, flow-readiness is checked, and every material decision is auditable.</p>
          <div style={{ marginTop: 18, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Link href="/pulse" className="lw-btn-primary" style={{ padding: "10px 14px", borderRadius: 12 }}>Open Pulse</Link>
            <Link href="/command" className="lw-pill">Open Command</Link>
            <Link href="/episodes/EP-1042" className="lw-pill">Open Demo Episode</Link>
            <Link href="/workspace" className="lw-pill">Workspace</Link>
          </div>
        </section>

        <section className="lw-card" style={{ padding: 20 }}>
          <h2 style={{ marginTop: 0 }}>Operating spine</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
            {spine.map(([name, text], index) => (
              <div key={name} style={{ border: "1px solid #1f2937", borderRadius: 16, padding: 14, background: "rgba(15,23,42,0.74)" }}>
                <div style={{ color: "#14b8a6", fontWeight: 900 }}>0{index + 1}</div>
                <strong>{name}</strong>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
              </div>
            ))}
          </div>
        </section>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          <DomainAutomationPanel />
          <DomainPressurePanel />
        </div>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
          {modules.map(([name, href, text]) => (
            <Link key={href} href={href} className="lw-card" style={{ padding: 18, display: "block" }}>
              <strong>{name}</strong>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
            </Link>
          ))}
        </section>
      </div>
    </main>
  );
}
