"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type DischargeReadiness = {
  id: number;
  episode_id: number;
  clinician_signoff: boolean;
  medication_ready: boolean;
  owner_updated: boolean;
  admin_ready: boolean;
  results_reviewed: boolean;
  care_instructions_ready: boolean;
  blocker_summary: string;
  readiness_state: string;
  owner_role: string;
  urgency: string;
  status: string;
};

export default function DischargePage() {
  const [items, setItems] = useState<DischargeReadiness[]>([]);
  const [episodeId, setEpisodeId] = useState("");
  const [blocker, setBlocker] = useState("Medication/results/owner update not ready");
  const [status, setStatus] = useState("");

  async function load() {
    const res = await fetch(`${API_BASE}/api/discharge-readiness`, { cache: "no-store" });
    setItems(await res.json());
  }

  useEffect(() => { load(); }, []);

  async function createReadiness() {
    if (!episodeId.trim()) return;
    setStatus("Creating discharge readiness record...");
    await fetch(`${API_BASE}/api/discharge-readiness`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: Number(episodeId), blocker_summary: blocker, urgency: "amber", owner_role: "clinician" }),
    });
    setStatus("Discharge readiness created. Blocker/work generated if incomplete.");
    await load();
  }

  async function markReady(id: number) {
    setStatus("Completing discharge readiness...");
    await fetch(`${API_BASE}/api/discharge-readiness/${id}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clinician_signoff: true, medication_ready: true, owner_updated: true, admin_ready: true, results_reviewed: true, care_instructions_ready: true }),
    });
    setStatus("Discharge marked ready.");
    await load();
  }

  const blocked = items.filter((x) => x.readiness_state !== "ready");
  const ready = items.filter((x) => x.readiness_state === "ready");
  const urgent = items.filter((x) => x.urgency === "red" || x.urgency === "amber");

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Discharge" subtitle="Readiness, blockers, owner update, medication and sign-off">
          {status ? <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, marginBottom: 16, background: "#0f172a" }}>{status}</div> : null}

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a", marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Create discharge readiness</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
              <label>Episode ID<br /><input value={episodeId} onChange={(e) => setEpisodeId(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Blocker summary<br /><input value={blocker} onChange={(e) => setBlocker(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
            </div>
            <button onClick={createReadiness} style={{ marginTop: 12, background: "#14b8a6", color: "#020617", border: 0, borderRadius: 10, padding: "10px 14px", fontWeight: 800 }}>Create discharge readiness</button>
          </section>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Blocked</div><div style={{ fontSize: 34 }}>{blocked.length}</div></section>
            <section style={{ border: "1px solid #14532d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Ready</div><div style={{ fontSize: 34 }}>{ready.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Urgent</div><div style={{ fontSize: 34 }}>{urgent.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Discharge readiness records</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>Episode #{item.episode_id} • {item.readiness_state}</strong><span>{item.urgency} • {item.status}</span></div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.blocker_summary || "No blocker summary"}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>signoff {item.clinician_signoff ? "yes" : "no"} • meds {item.medication_ready ? "yes" : "no"} • owner {item.owner_updated ? "yes" : "no"} • admin {item.admin_ready ? "yes" : "no"} • results {item.results_reviewed ? "yes" : "no"} • instructions {item.care_instructions_ready ? "yes" : "no"}</div>
                {item.readiness_state !== "ready" ? <button onClick={() => markReady(item.id)} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Mark ready</button> : null}
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No discharge readiness records yet.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
