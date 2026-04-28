"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type PharmacyRequest = {
  id: number;
  episode_id?: number | null;
  medication_name: string;
  request_type: string;
  controlled_or_legal_status: string;
  authorised_supplier_required: boolean;
  quantity?: string | null;
  urgency: string;
  owner_role: string;
  status: string;
  compliance_note: string;
};

export default function PharmacyPage() {
  const [items, setItems] = useState<PharmacyRequest[]>([]);
  const [episodeId, setEpisodeId] = useState("");
  const [medication, setMedication] = useState("");
  const [quantity, setQuantity] = useState("");
  const [legalStatus, setLegalStatus] = useState("standard");
  const [urgency, setUrgency] = useState("amber");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("");

  async function load() {
    const res = await fetch(`${API_BASE}/api/pharmacy-requests`, { cache: "no-store" });
    setItems(await res.json());
  }

  useEffect(() => { load(); }, []);

  async function createRequest() {
    if (!medication.trim()) return;
    setStatus("Creating pharmacy request...");
    const payload: Record<string, unknown> = {
      medication_name: medication,
      request_type: "dispense",
      controlled_or_legal_status: legalStatus,
      authorised_supplier_required: true,
      quantity,
      urgency,
      owner_role: "nurse",
      compliance_note: note || "Authorised veterinary supply route required if applicable.",
    };
    if (episodeId.trim()) payload.episode_id = Number(episodeId);
    await fetch(`${API_BASE}/api/pharmacy-requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setStatus("Pharmacy request created and linked work generated.");
    setMedication(""); setQuantity(""); setNote("");
    await load();
  }

  async function completeRequest(id: number) {
    setStatus("Completing pharmacy request...");
    await fetch(`${API_BASE}/api/pharmacy-requests/${id}/complete`, { method: "POST" });
    setStatus("Pharmacy request completed.");
    await load();
  }

  const open = items.filter((x) => x.status !== "complete");
  const urgent = open.filter((x) => x.urgency === "red" || x.urgency === "amber");
  const controlled = open.filter((x) => x.controlled_or_legal_status !== "standard");

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Pharmacy" subtitle="Medication requests, legal status, supply route and handoff control">
          {status ? <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, marginBottom: 16, background: "#0f172a" }}>{status}</div> : null}

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a", marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Create pharmacy request</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10 }}>
              <label>Episode ID optional<br /><input value={episodeId} onChange={(e) => setEpisodeId(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Medication<br /><input value={medication} onChange={(e) => setMedication(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Quantity<br /><input value={quantity} onChange={(e) => setQuantity(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Legal/status<br /><input value={legalStatus} onChange={(e) => setLegalStatus(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Urgency<br /><select value={urgency} onChange={(e) => setUrgency(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }}><option value="red">red</option><option value="amber">amber</option><option value="green">green</option></select></label>
            </div>
            <label style={{ display: "block", marginTop: 12 }}>Compliance note<br /><textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} style={{ width: "100%", padding: 10, borderRadius: 10 }} placeholder="e.g. cascade, controlled drug, authorised supplier, written script" /></label>
            <button onClick={createRequest} style={{ marginTop: 12, background: "#14b8a6", color: "#020617", border: 0, borderRadius: 10, padding: "10px 14px", fontWeight: 800 }}>Create pharmacy request</button>
          </section>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Urgent/open</div><div style={{ fontSize: 34 }}>{urgent.length}</div></section>
            <section style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Legal / controlled</div><div style={{ fontSize: 34 }}>{controlled.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Open requests</div><div style={{ fontSize: 34 }}>{open.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Pharmacy requests</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{item.medication_name}</strong><span>{item.urgency} • {item.status}</span></div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.request_type} • {item.quantity || "no quantity"} • {item.controlled_or_legal_status}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>authorised supplier required: {item.authorised_supplier_required ? "yes" : "no"} • owner {item.owner_role}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.compliance_note || "No compliance note"}</div>
                {item.status !== "complete" ? <button onClick={() => completeRequest(item.id)} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Complete</button> : null}
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No pharmacy requests yet.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
