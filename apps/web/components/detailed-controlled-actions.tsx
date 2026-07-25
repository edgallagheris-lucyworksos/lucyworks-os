"use client";

import Link from "next/link";
import { useState } from "react";
import { apiJson } from "@/lib/api-client";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 16, padding: 15, boxShadow: "0 5px 18px rgba(15,23,42,.05)", display: "grid", gap: 9, minWidth: 0 };
const field: React.CSSProperties = { width: "100%", minHeight: 46, border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", fontSize: 16, boxSizing: "border-box", background: "white", color: "#0f172a" };
const button: React.CSSProperties = { minHeight: 46, border: 0, borderRadius: 9, padding: "10px 13px", background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };

function iso(value: string) {
  if (!value) return new Date().toISOString();
  return new Date(value).toISOString();
}

export function DetailedControlledActions() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [prescription, setPrescription] = useState({ episode: "", patient: "", review: "", medicine: "", frequency: "once", starts: "" });
  const [anaesthesia, setAnaesthesia] = useState({ chart: "", version: "1", status: "induced", recovery: "" });
  const [document, setDocument] = useState({ ref: "", version: "1", action: "approve", audience: "owner", channel: "email", recipient: "" });

  async function act(path: string, method: "POST" | "PATCH", body: unknown, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await apiJson(path, { method, body: JSON.stringify(body) }); setMessage(success); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Action failed"); }
    finally { setBusy(false); }
  }

  return <main style={{ minHeight: "100vh", background: "#e8eef4", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><div><small style={{ color: "#2dd4bf", fontWeight: 900, letterSpacing: ".12em" }}>CONTROLLED CLINICAL ACTIONS</small><h1 style={{ fontSize: "clamp(34px,7vw,68px)", lineHeight: .95, margin: "6px 0" }}>Review before action</h1></div><div style={{ display: "flex", gap: 12 }}><Link href="/patient-record" style={{ color: "white" }}>Patient record</Link><Link href="/system-control" style={{ color: "white" }}>System control</Link></div></div>
      <p style={{ color: "#94a3b8", maxWidth: 880 }}>These actions cannot bypass the recorded medication safety review, anaesthesia state machine or document approval state. Stale versions are rejected.</p>
    </header>
    {error && <div aria-live="assertive" style={{ ...panel, marginTop: 10, borderColor: "#ef4444", color: "#991b1b" }}>{error}</div>}
    {message && <div aria-live="polite" style={{ ...panel, marginTop: 10, borderColor: "#22c55e", color: "#166534" }}>{message}</div>}
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,320px),1fr))", gap: 10, marginTop: 10 }}>
      <article style={panel}>
        <h2 style={{ margin: 0 }}>Issue reviewed prescription</h2>
        <p style={{ color: "#475569" }}>The safety review must belong to the same patient and episode, must not be blocked, and the medicine must remain approved. Active interactions and contraindications are rechecked at issue time.</p>
        <input placeholder="Episode reference" value={prescription.episode} onChange={event => setPrescription({ ...prescription, episode: event.target.value })} style={field} />
        <input placeholder="Patient reference" value={prescription.patient} onChange={event => setPrescription({ ...prescription, patient: event.target.value })} style={field} />
        <input placeholder="Safety review reference" value={prescription.review} onChange={event => setPrescription({ ...prescription, review: event.target.value })} style={field} />
        <input placeholder="Display medicine name (optional)" value={prescription.medicine} onChange={event => setPrescription({ ...prescription, medicine: event.target.value })} style={field} />
        <input placeholder="Frequency" value={prescription.frequency} onChange={event => setPrescription({ ...prescription, frequency: event.target.value })} style={field} />
        <input type="datetime-local" aria-label="Prescription start time" value={prescription.starts} onChange={event => setPrescription({ ...prescription, starts: event.target.value })} style={field} />
        <button disabled={busy || !prescription.episode || !prescription.patient || !prescription.review} style={button} onClick={() => void act(`/api/v8/episodes/${encodeURIComponent(prescription.episode)}/medication-orders`, "POST", { patient_ref: prescription.patient, safety_review_ref: prescription.review, medication_name: prescription.medicine || null, frequency: prescription.frequency, starts_at: iso(prescription.starts), scheduled_times: [iso(prescription.starts)], reason: "Safety-reviewed prescription issued by verified clinician" }, "Prescription and first administration schedule created.")}>Issue prescription</button>
      </article>
      <article style={panel}>
        <h2 style={{ margin: 0 }}>Move anaesthesia stage</h2>
        <p style={{ color: "#475569" }}>Induction requires identity, consent, machine and airway gates. Completion requires a recovery score.</p>
        <input placeholder="Anaesthesia chart reference" value={anaesthesia.chart} onChange={event => setAnaesthesia({ ...anaesthesia, chart: event.target.value })} style={field} />
        <input type="number" min="1" placeholder="Expected version" value={anaesthesia.version} onChange={event => setAnaesthesia({ ...anaesthesia, version: event.target.value })} style={field} />
        <select value={anaesthesia.status} onChange={event => setAnaesthesia({ ...anaesthesia, status: event.target.value })} style={field}><option value="induced">Induced</option><option value="maintenance">Maintenance</option><option value="recovery">Recovery</option><option value="completed">Completed</option></select>
        <input placeholder="Recovery score / readiness (required to complete)" value={anaesthesia.recovery} onChange={event => setAnaesthesia({ ...anaesthesia, recovery: event.target.value })} style={field} />
        <button disabled={busy || !anaesthesia.chart || !anaesthesia.version} style={button} onClick={() => void act(`/api/v8/anaesthesia/charts/${encodeURIComponent(anaesthesia.chart)}/transition`, "PATCH", { expected_version: Number(anaesthesia.version), status: anaesthesia.status, recovery_score: anaesthesia.recovery || null, reason: `Anaesthesia moved to ${anaesthesia.status} by verified clinician` }, "Anaesthesia stage updated.")}>Apply transition</button>
      </article>
      <article style={panel}>
        <h2 style={{ margin: 0 }}>Approve or send document</h2>
        <p style={{ color: "#475569" }}>Only a non-empty draft can be approved. Only an approved document can be sent. Sending writes a communication event and attachment reference.</p>
        <input placeholder="Document reference" value={document.ref} onChange={event => setDocument({ ...document, ref: event.target.value })} style={field} />
        <input type="number" min="1" placeholder="Expected version" value={document.version} onChange={event => setDocument({ ...document, version: event.target.value })} style={field} />
        <select value={document.action} onChange={event => setDocument({ ...document, action: event.target.value })} style={field}><option value="approve">Approve</option><option value="send">Send</option></select>
        {document.action === "send" && <><select value={document.audience} onChange={event => setDocument({ ...document, audience: event.target.value })} style={field}><option value="owner">Owner</option><option value="referring_vet">Referring vet</option><option value="insurer">Insurer</option></select><select value={document.channel} onChange={event => setDocument({ ...document, channel: event.target.value })} style={field}><option value="email">Email</option><option value="portal">Portal</option><option value="letter">Letter</option><option value="in_person">In person</option></select><input placeholder="Recipient reference" value={document.recipient} onChange={event => setDocument({ ...document, recipient: event.target.value })} style={field} /></>}
        <button disabled={busy || !document.ref || !document.version} style={button} onClick={() => document.action === "approve" ? void act(`/api/v8/documents/${encodeURIComponent(document.ref)}/approve`, "PATCH", { expected_version: Number(document.version), reason: "Clinical document reviewed and approved" }, "Document approved.") : void act(`/api/v8/documents/${encodeURIComponent(document.ref)}/send`, "POST", { expected_version: Number(document.version), audience: document.audience, channel: document.channel, recipient_ref: document.recipient || null, reason: "Approved document sent by verified operator" }, "Document sent and communication recorded.")}>{document.action === "approve" ? "Approve document" : "Send approved document"}</button>
      </article>
    </section>
  </main>;
}
