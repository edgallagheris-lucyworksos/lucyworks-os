"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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

export default function PulsePage() {
  const [pulse, setPulse] = useState<Pulse | null>(null);

  async function load() {
    const res = await fetch(`${API_BASE}/api/pulse`, { cache: "no-store" });
    setPulse(await res.json());
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Lucy Pulse" subtitle="Whole-hospital pressure and operational risk">
          {!pulse ? <p>Loading pulse...</p> : null}
          {pulse ? (
            <div style={{ display: "grid", gap: 18 }}>
              <section style={{ border: riskBorder(pulse.system_risk_level), borderRadius: 22, padding: 20, background: "#0f172a" }}>
                <div style={{ color: "#94a3b8" }}>System risk</div>
                <div style={{ fontSize: 46, marginTop: 8, textTransform: "uppercase" }}>{pulse.system_risk_level}</div>
                <div style={{ color: "#94a3b8", marginTop: 8 }}>
                  conflicts {pulse.conflict_count} • ethics {pulse.ethics_pressure} • triage {pulse.triage_pressure} • care {pulse.lucy_care_pressure} • owner comms {pulse.owner_comms_pressure}
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 14 }}>
                  <Link href="/command" style={{ border: "1px solid #334155", borderRadius: 12, padding: "8px 10px" }}>Command</Link>
                  <Link href="/triage" style={{ border: "1px solid #334155", borderRadius: 12, padding: "8px 10px" }}>LucyFlow</Link>
                  <Link href="/ethics" style={{ border: "1px solid #334155", borderRadius: 12, padding: "8px 10px" }}>Lucy Ethics</Link>
                  <Link href="/ward" style={{ border: "1px solid #334155", borderRadius: 12, padding: "8px 10px" }}>Ward / ICU</Link>
                  <Link href="/theatre" style={{ border: "1px solid #334155", borderRadius: 12, padding: "8px 10px" }}>Theatre</Link>
                </div>
              </section>

              <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                {[
                  ["Case pressure", pulse.case_pressure, "Open active case work and unresolved operational items."],
                  ["Resource pressure", pulse.resource_pressure, "Conflicts plus blockers affecting rooms, flow and capacity."],
                  ["Staff pressure", pulse.staff_pressure, "Open Lucy Care tasks and unresolved decisions needing people."],
                  ["Capacity pressure", pulse.capacity_pressure, "Active admissions and inpatient load."],
                  ["Execution pressure", pulse.execution_pressure, "Decisions, owner comms and pending result reviews."],
                  ["Ethics pressure", pulse.ethics_pressure, "Open Lucy Ethics welfare, consent and escalation flags."],
                  ["Triage pressure", pulse.triage_pressure, "Open LucyFlow red/amber intake and routing pressure."],
                  ["Lucy Care pressure", pulse.lucy_care_pressure, "Open care tasks, observations, medication and continuity work."],
                  ["Owner comms pressure", pulse.owner_comms_pressure, "Owner updates and communication requirements still due."],
                  ["Conflict count", pulse.conflict_count, "Detected live room, staff, result and handover conflicts."],
                ].map(([label, value, text]) => (
                  <div key={String(label)} style={{ border: border(Number(value)), borderRadius: 18, padding: 16, background: "#0f172a" }}>
                    <div style={{ color: "#94a3b8" }}>{label}</div>
                    <div style={{ fontSize: 36, marginTop: 8 }}>{value}</div>
                    <div style={{ color: "#94a3b8", marginTop: 8 }}>{text}</div>
                  </div>
                ))}
              </section>
            </div>
          ) : null}
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
