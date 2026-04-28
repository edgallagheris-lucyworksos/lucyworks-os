"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type TriageAssessment = {
  id: number;
  episode_id?: number | null;
  species: string;
  presenting_signs: string;
  urgency: string;
  route: string;
  confidence: number;
  reasoning: string;
  red_flags: string;
  advice_mode: string;
  handoff_required: boolean;
  ethics_triggered: boolean;
  owner_contact_required: boolean;
  decision_required: boolean;
  assigned_owner_role: string;
  status: string;
};

export default function TriagePage() {
  const [items, setItems] = useState<TriageAssessment[]>([]);
  const [species, setSpecies] = useState("dog");
  const [episodeId, setEpisodeId] = useState("");
  const [signs, setSigns] = useState("");
  const [status, setStatus] = useState("");

  async function load() {
    const res = await fetch(`${API_BASE}/api/lucyflow/triage`, { cache: "no-store" });
    setItems(await res.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function createAssessment() {
    if (!signs.trim()) return;
    setStatus("LucyFlow is assessing intake...");
    const payload: Record<string, unknown> = { species, presenting_signs: signs };
    if (episodeId.trim()) payload.episode_id = Number(episodeId);
    const res = await fetch(`${API_BASE}/api/lucyflow/triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    setStatus(`Routed ${body.triage.urgency.toUpperCase()} → ${body.triage.route}. Work and decision created.`);
    setSigns("");
    await load();
  }

  async function resolve(id: number) {
    setStatus("Resolving triage assessment...");
    await fetch(`${API_BASE}/api/lucyflow/triage/${id}/resolve?note=${encodeURIComponent("Resolved from LucyFlow")}`, { method: "POST" });
    setStatus("Triage assessment resolved.");
    await load();
  }

  const red = items.filter((x) => x.urgency === "red" && x.status !== "resolved");
  const handoff = items.filter((x) => x.handoff_required && x.status !== "resolved");
  const ethics = items.filter((x) => x.ethics_triggered && x.status !== "resolved");

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="LucyFlow" subtitle="Triage, red flags, routing and handoff control">
          {status ? <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, marginBottom: 16, background: "#0f172a" }}>{status}</div> : null}

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a", marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>New intake assessment</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
              <label>Species<br /><input value={species} onChange={(e) => setSpecies(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Episode ID optional<br /><input value={episodeId} onChange={(e) => setEpisodeId(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
            </div>
            <label style={{ display: "block", marginTop: 12 }}>Presenting signs / owner wording<br />
              <textarea value={signs} onChange={(e) => setSigns(e.target.value)} rows={4} style={{ width: "100%", padding: 10, borderRadius: 10 }} placeholder="e.g. collapsed, breathing difficulty, painful, owner worried about cost" />
            </label>
            <button onClick={createAssessment} style={{ marginTop: 12, background: "#14b8a6", color: "#020617", border: 0, borderRadius: 10, padding: "10px 14px", fontWeight: 800 }}>Run LucyFlow</button>
          </section>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Red live</div><div style={{ fontSize: 34 }}>{red.length}</div></section>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Needs handoff</div><div style={{ fontSize: 34 }}>{handoff.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Ethics triggered</div><div style={{ fontSize: 34 }}>{ethics.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>LucyFlow assessments</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{item.species} • {item.urgency.toUpperCase()} → {item.route}</strong>
                  <span>{item.status} • confidence {Math.round(item.confidence * 100)}%</span>
                </div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.presenting_signs}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.reasoning}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>red flags: {item.red_flags || "none"} • owner {item.assigned_owner_role} • handoff {item.handoff_required ? "yes" : "no"} • ethics {item.ethics_triggered ? "yes" : "no"}</div>
                {item.status !== "resolved" ? <button onClick={() => resolve(item.id)} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Resolve</button> : null}
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No LucyFlow assessments yet.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
