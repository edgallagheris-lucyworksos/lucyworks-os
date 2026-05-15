import Link from "next/link";

const modules = [
  ["Command", "Whole-hospital pressure, priority work, red alerts and section load."],
  ["Episodes", "One case spine for patient, owner, room, schedule, results, messages and work."],
  ["Schedule", "Prep, anaesthesia, procedure, recovery and cleaning as operational blocks."],
  ["Rooms", "Live room state across consults, wards, ICU, theatre, recovery and diagnostics."],
  ["Staff", "Shift status, current load and assigned schedule blocks."],
  ["Conflicts", "Room, staff, handover, result and cleaning chain failures surfaced as action."],
  ["Mail Ops", "Owner and clinical communications linked back to live episodes."],
  ["Audit", "Traceable operational record for actions, changes and responsibility."],
];

export default function ProductPage() {
  return (
    <main style={{ minHeight: "100vh", background: "#020617", padding: 24 }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gap: 24 }}>
        <section style={{ border: "1px solid #1f2937", borderRadius: 28, padding: 32, background: "#0f172a" }}>
          <div style={{ color: "#14b8a6", fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase" }}>LucyWorks OS</div>
          <h1 style={{ fontSize: 56, lineHeight: 1, margin: "14px 0 0", letterSpacing: "-0.05em" }}>Run the hospital. Not just the schedule.</h1>
          <p style={{ color: "#cbd5e1", fontSize: 20, maxWidth: 860, marginTop: 18 }}>
            LucyWorks OS is a hospital operations engine for specialist veterinary teams: a live command layer that connects cases, rooms, staff, results, owner comms, conflicts and audit into one operational spine.
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 24 }}>
            <Link href="/command" style={{ background: "#14b8a6", color: "#020617", padding: "12px 16px", borderRadius: 12, fontWeight: 800 }}>Open demo command</Link>
            <Link href="/episodes/EP-1042" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>Open example episode</Link>
            <Link href="/" style={{ border: "1px solid #334155", padding: "12px 16px", borderRadius: 12 }}>Home</Link>
          </div>
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
          {[
            ["Problem", "Specialist hospitals run on fractured calls, boards, messages, memory and pressure."],
            ["Control layer", "LucyWorks turns every live issue into visible ownership, timing and escalation."],
            ["Operational proof", "The demo flow links one episode to staff, room, schedule, result, conflict, work and audit."],
          ].map(([title, text]) => (
            <div key={title} style={{ border: "1px solid #1f2937", borderRadius: 20, padding: 20, background: "#0f172a" }}>
              <strong style={{ fontSize: 20 }}>{title}</strong>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
            </div>
          ))}
        </section>

        <section style={{ border: "1px solid #1f2937", borderRadius: 24, padding: 24, background: "#0f172a" }}>
          <h2 style={{ marginTop: 0 }}>System loop</h2>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {["Episode", "Schedule", "Rooms", "Staff", "Conflicts", "Results", "Messages", "Work", "Audit"].map((step) => (
              <span key={step} style={{ border: "1px solid #334155", borderRadius: 999, padding: "10px 12px" }}>{step}</span>
            ))}
          </div>
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
          {modules.map(([title, text]) => (
            <div key={title} style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 18, background: "#0f172a" }}>
              <strong>{title}</strong>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>{text}</p>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
