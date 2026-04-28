"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type EthicsFlag = {
  id: number;
  episode_id?: number | null;
  flag_type: string;
  severity: string;
  detail: string;
  clinical_reasoning: string;
  owner_state: string;
  decision_required: string;
  escalation_path: string;
  owner_role: string;
  status: string;
  escalation_required: boolean;
};

export default function EthicsPage() {
  const [items, setItems] = useState<EthicsFlag[]>([]);
  const [episodeId, setEpisodeId] = useState("");
  const [flagType, setFlagType] = useState("consent_delay");
  const [severity, setSeverity] = useState("high");
  const [detail, setDetail] = useState("");
  const [clinicalReasoning, setClinicalReasoning] = useState("");
  const [ownerState, setOwnerState] = useState("unknown");
  const [status, setStatus] = useState("");

  async function load() {
    const res = await fetch(`${API_BASE}/api/lucy-ethics`, { cache: "no-store" });
    setItems(await res.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function createFlag() {
    if (!detail.trim()) return;
    setStatus("Creating Lucy Ethics flag...");
    const payload: Record<string, unknown> = {
      flag_type: flagType,
      severity,
      detail,
      clinical_reasoning: clinicalReasoning || detail,
      owner_state: ownerState,
      decision_required: "senior clinician review",
      escalation_path: "clinician_to_ops_manager",
      owner_role: "clinician",
      escalation_required: true,
    };
    if (episodeId.trim()) payload.episode_id = Number(episodeId);
    const res = await fetch(`${API_BASE}/api/lucy-ethics`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    setStatus(`Ethics flag created and work item linked #${body.work_item.id}.`);
    setDetail("");
    setClinicalReasoning("");
    await load();
  }

  async function resolve(id: number) {
    setStatus("Resolving Lucy Ethics flag...");
    await fetch(`${API_BASE}/api/lucy-ethics/${id}/resolve?note=${encodeURIComponent("Resolved from Lucy Ethics")}`, { method: "POST" });
    setStatus("Lucy Ethics flag resolved.");
    await load();
  }

  const red = items.filter((x) => x.severity === "high" && x.status !== "resolved");
  const open = items.filter((x) => x.status !== "resolved");
  const consent = items.filter((x) => x.flag_type.includes("consent") && x.status !== "resolved");

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Lucy Ethics" subtitle="Welfare, consent, owner communication and escalation risk">
          {status ? <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, marginBottom: 16, background: "#0f172a" }}>{status}</div> : null}

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a", marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Create ethics flag</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
              <label>Episode ID optional<br /><input value={episodeId} onChange={(e) => setEpisodeId(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Flag type<br /><input value={flagType} onChange={(e) => setFlagType(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Severity<br /><select value={severity} onChange={(e) => setSeverity(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }}><option value="high">high</option><option value="medium">medium</option><option value="low">low</option></select></label>
              <label>Owner state<br /><input value={ownerState} onChange={(e) => setOwnerState(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
            </div>
            <label style={{ display: "block", marginTop: 12 }}>Detail<br /><textarea value={detail} onChange={(e) => setDetail(e.target.value)} rows={3} style={{ width: "100%", padding: 10, borderRadius: 10 }} placeholder="e.g. owner consent delayed while patient remains painful" /></label>
            <label style={{ display: "block", marginTop: 12 }}>Clinical reasoning<br /><textarea value={clinicalReasoning} onChange={(e) => setClinicalReasoning(e.target.value)} rows={3} style={{ width: "100%", padding: 10, borderRadius: 10 }} placeholder="why this matters clinically / operationally" /></label>
            <button onClick={createFlag} style={{ marginTop: 12, background: "#14b8a6", color: "#020617", border: 0, borderRadius: 10, padding: "10px 14px", fontWeight: 800 }}>Create Lucy Ethics flag</button>
          </section>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>High ethics flags</div><div style={{ fontSize: 34 }}>{red.length}</div></section>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Open flags</div><div style={{ fontSize: 34 }}>{open.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Consent related</div><div style={{ fontSize: 34 }}>{consent.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Lucy Ethics flags</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{item.flag_type}</strong><span>{item.severity.toUpperCase()} • {item.status}</span></div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.detail}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.clinical_reasoning}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>owner state {item.owner_state} • decision {item.decision_required} • escalation {item.escalation_path}</div>
                {item.status !== "resolved" ? <button onClick={() => resolve(item.id)} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Resolve</button> : null}
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No Lucy Ethics flags yet.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
