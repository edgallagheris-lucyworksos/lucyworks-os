"use client";

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
  system_risk_level: string;
};

function border(value: number) {
  if (value >= 5) return "1px solid #7f1d1d";
  if (value >= 2) return "1px solid #78350f";
  return "1px solid #14532d";
}

export default function PulsePage() {
  const [pulse, setPulse] = useState<Pulse | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/pulse`, { cache: "no-store" });
      setPulse(await res.json());
    }
    load();
  }, []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Lucy Pulse" subtitle="Whole-hospital pressure and operational risk">
          {!pulse ? <p>Loading pulse...</p> : null}
          {pulse ? (
            <div style={{ display: "grid", gap: 18 }}>
              <section style={{ border: "1px solid #1f2937", borderRadius: 22, padding: 20, background: "#0f172a" }}>
                <div style={{ color: "#94a3b8" }}>System risk</div>
                <div style={{ fontSize: 42, marginTop: 8, textTransform: "uppercase" }}>{pulse.system_risk_level}</div>
                <div style={{ color: "#94a3b8", marginTop: 8 }}>Detected conflicts: {pulse.conflict_count}</div>
              </section>

              <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                {[
                  ["Case pressure", pulse.case_pressure, "Open active case work."],
                  ["Resource pressure", pulse.resource_pressure, "Occupied rooms plus resource conflicts."],
                  ["Staff pressure", pulse.staff_pressure, "Open clinician/nurse-owned work."],
                  ["Capacity pressure", pulse.capacity_pressure, "Ward/ICU active pressure."],
                  ["Execution pressure", pulse.execution_pressure, "Unacknowledged handovers and pending results."],
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
