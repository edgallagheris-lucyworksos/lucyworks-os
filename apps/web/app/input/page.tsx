"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { apiPost } from "@/lib/api";

const sections = ["Reception / Intake", "Triage / Consult", "Imaging", "Surgery / Theatre", "ICU", "Ward", "Pharmacy", "Owner Comms", "Insurance"];
const urgencies = ["green", "amber", "red"];
const owners = ["ops_manager", "clinician", "nurse", "admin", "theatre_staff", "ward_staff", "imaging_staff", "stock_controller"];

type CaptureResponse = { ok: boolean; work_item?: { id?: number; title?: string } };

function InputInner() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [sectionName, setSectionName] = useState("Reception / Intake");
  const [urgency, setUrgency] = useState("amber");
  const [ownerRole, setOwnerRole] = useState("ops_manager");
  const [patient, setPatient] = useState("");
  const [episode, setEpisode] = useState("");
  const [room, setRoom] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const hasOperationalText = Boolean(title.trim() || description.trim());

  async function submit() {
    if (!hasOperationalText) {
      setStatus("");
      setError("Enter a title or operational note before creating work.");
      return;
    }
    setBusy(true); setStatus(""); setError("");
    try {
      const data = await apiPost<CaptureResponse>("/api/input/capture", {
        title: title.trim() || description.trim().slice(0, 80) || "Mobile capture",
        description: description.trim(),
        section_name: sectionName,
        urgency,
        owner_role: ownerRole,
        linked_patient_name: patient.trim() || null,
        linked_episode_ref: episode.trim() || null,
        room_name: room.trim() || null,
      });
      setStatus(episode.trim()
        ? `Work item #${data.work_item?.id || "new"} created and linked to ${episode.trim()}. Open Patient Command to continue.`
        : `Work item #${data.work_item?.id || "new"} created as unlinked operational work. Link it to an episode before treating it as live patient care.`);
      setTitle(""); setDescription(""); setPatient(""); setEpisode(""); setRoom("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Capture failed");
    } finally { setBusy(false); }
  }

  return <HospitalShell title="Quick Input" subtitle="capture an operational problem once and give it clear ownership">
    <div style={{ display: "grid", gap: 12 }}>
      <section className="lw-command-panel">
        <div className="lw-command-header">
          <div><div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Operational capture</div><h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.05em" }}>Type it once. Create owned work.</h1><p style={{ color: "#94a3b8", marginBottom: 0 }}>Record the problem, patient, place, urgency and accountable role. Clinical judgement and consent remain in the governed patient workflow.</p></div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Link href="/workspace" className="lw-pill">Patient Command</Link><Link href="/hospital-board" className="lw-pill">Hospital Today</Link><Link href="/referral-intake" className="lw-pill">Referrals</Link></div>
        </div>
      </section>

      <section className="lw-command-panel" style={{ padding: 12, display: "grid", gap: 10 }}>
        <label>What needs attention<input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. MRI owner update overdue" maxLength={200} /></label>
        <label>What happened and what is needed<textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Record the facts, required action and relevant context." rows={7} maxLength={10000} /></label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
          <label>Where / service<select value={sectionName} onChange={e => setSectionName(e.target.value)}>{sections.map(value => <option key={value}>{value}</option>)}</select></label>
          <label>Urgency<select value={urgency} onChange={e => setUrgency(e.target.value)}>{urgencies.map(value => <option key={value}>{value}</option>)}</select></label>
          <label>Who owns the next action<select value={ownerRole} onChange={e => setOwnerRole(e.target.value)}>{owners.map(value => <option key={value}>{value}</option>)}</select></label>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
          <label>Patient<input value={patient} onChange={e => setPatient(e.target.value)} placeholder="Optional patient name" /></label>
          <label>Episode reference<input value={episode} onChange={e => setEpisode(e.target.value)} placeholder="Use EP-... when known" /></label>
          <label>Exact room / location<input value={room} onChange={e => setRoom(e.target.value)} placeholder="MRI / ICU Bay 1" /></label>
        </div>
        {!episode.trim() ? <p style={{ margin: 0, padding: 9, border: "1px solid #f59e0b", borderRadius: 9, background: "#fffbeb", color: "#92400e" }}>Without an episode reference this remains clearly separated legacy/unlinked work until reviewed.</p> : null}
        <button className="lw-pill lw-btn-primary" style={{ minHeight: 48 }} onClick={() => void submit()} disabled={busy || !hasOperationalText}>{busy ? "Creating…" : "Create owned work"}</button>
        <div aria-live="polite">{status ? <p style={{ color: "#86efac", margin: 0 }}>{status}</p> : null}{error ? <p style={{ color: "#fca5a5", margin: 0 }}>{error}</p> : null}</div>
      </section>
    </div>
  </HospitalShell>;
}

export default function InputPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <InputInner />}</AuthGuard>;
}
