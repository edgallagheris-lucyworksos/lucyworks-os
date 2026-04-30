"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Pulse = {
  case_pressure: number;
  resource_pressure: number;
  staff_pressure: number;
  capacity_pressure: number;
  execution_pressure: number;
  conflict_count: number;
  ethics_pressure: number;
  triage_pressure: number;
  lucy_care_pressure: number;
  owner_comms_pressure: number;
  system_risk_level: string;
};

function border(value: number) {
  if (value >= 5) return "1px solid #7f1d1d";
  if (value >= 2) return "1px solid #78350f";
  return "1px solid #14532d";
}

function riskBorder(risk: string) {
  if (risk === "red") return "1px solid #7f1d1d";
  if (risk === "amber") return "1px solid #78350f";
  return "1px solid #14532d";
}

function strongestPressure(pulse: Pulse) {
  const rows = [
    ["case pressure", pulse.case_pressure, "/queues"],
    ["resource pressure", pulse.resource_pressure, "/conflicts"],
    ["staff pressure", pulse.staff_pressure, "/staff"],
    ["capacity pressure", pulse.capacity_pressure, "/admissions"],
    ["execution pressure", pulse.execution_pressure, "/command"],
    ["ethics pressure", pulse.ethics_pressure, "/ethics"],
    ["triage pressure", pulse.triage_pressure, "/triage"],
    ["Lucy Care pressure", pulse.lucy_care_pressure, "/ward"],
    ["owner comms pressure", pulse.owner_comms_pressure, "/mail"],
  ] as const;
  return [...rows].sort((a, b) => b[1] - a[1])[0];
}

function interpretation(pulse: Pulse) {
  const [name, value, href] = strongestPressure(pulse);
  if (pulse.system_risk_level === "red") {
    return { tone: "Critical", href, title: `Dominant pressure: ${name}`, body: `The system is red because unresolved pressure is high enough to threaten safe flow. Start with ${name} (${value}), then clear hard blockers before moving cases.` };
  }
  if (pulse.system_risk_level === "amber") {
    return { tone: "Watch", href, title: `Main pressure: ${name}`, body: `The system is amber. It is still controllable, but delays will compound if ${name} (${value}) is left unmanaged.` };
  }
  return { tone: "Stable", href, title: `Main pressure: ${name}`, body: `The system is stable. Keep the live queues moving and clear small blockers before they become red work.` };
}

export default function PulsePage() {
  const [pulse, setPulse] = useState<Pulse | null>(null);

  async function load() {
    const res = await fetch(`${API_BASE}/api/pulse`, { cache: "no-store" });
    setPulse(await res.json());
  }

  useEffect(() => { load(); }, []);
  const read = useMemo(() => pulse ? interpretation(pulse) : null, [pulse]);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => (
      <HospitalShell title="Lucy Pulse" subtitle="Whole-hospital pressure, cause and next action">
        {!pulse ? <p>Loading pulse...</p> : null}
        {pulse && read ? <div style={{ display: "grid", gap: 18 }}>
          <section className="lw-card" style={{ border: riskBorder(pulse.system_risk_level), padding: 22 }}>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Live interpretation</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 18, alignItems: "end", marginTop: 10 }}>
              <div>
                <div style={{ fontSize: 48, fontWeight: 950, letterSpacing: "-0.05em", textTransform: "uppercase" }}>{pulse.system_risk_level}</div>
                <h2 style={{ margin: "8px 0 0" }}>{read.title}</h2>
                <p style={{ color: "#94a3b8", maxWidth: 850 }}>{read.body}</p>
              </div>
              <Link href={read.href} className="lw-btn-primary" style={{ borderRadius: 14, padding: "12px 14px" }}>Open pressure source</Link>
            </div>
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            {[
              ["Case pressure", pulse.case_pressure, "Open active case work and unresolved operational items.", "/queues"],
              ["Resource pressure", pulse.resource_pressure, "Conflicts plus blockers affecting rooms, flow and capacity.", "/conflicts"],
              ["Staff pressure", pulse.staff_pressure, "Open care tasks and unresolved decisions needing people.", "/staff"],
              ["Capacity pressure", pulse.capacity_pressure, "Active admissions and inpatient load.", "/admissions"],
              ["Execution pressure", pulse.execution_pressure, "Decisions, owner comms and pending result reviews.", "/command"],
              ["Ethics pressure", pulse.ethics_pressure, "Open welfare, consent and escalation flags.", "/ethics"],
              ["Triage pressure", pulse.triage_pressure, "Open LucyFlow red/amber intake and routing pressure.", "/triage"],
              ["Lucy Care pressure", pulse.lucy_care_pressure, "Open care, observation, medication and continuity work.", "/ward"],
              ["Owner comms pressure", pulse.owner_comms_pressure, "Owner updates and communication requirements still due.", "/mail"],
              ["Conflict count", pulse.conflict_count, "Detected room, staff, result and handover conflicts.", "/conflicts"],
            ].map(([label, value, text, href]) => (
              <Link key={String(label)} href={String(href)} className="lw-card" style={{ border: border(Number(value)), padding: 16, display: "block" }}>
                <div style={{ color: "#94a3b8" }}>{label}</div>
                <div style={{ fontSize: 36, fontWeight: 900, marginTop: 8 }}>{value}</div>
                <div style={{ color: "#94a3b8", marginTop: 8 }}>{text}</div>
              </Link>
            ))}
          </section>

          <section className="lw-card" style={{ padding: 18 }}>
            <h3 style={{ marginTop: 0 }}>Operational rule</h3>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>Pulse is not a dashboard score. It is the hospital pressure layer: find the dominant pressure, open the owner surface, clear the unsafe blocker, then verify the episode is ready for flow.</p>
          </section>
        </div> : null}
      </HospitalShell>
    )}</AuthGuard>
  );
}
