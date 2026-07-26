"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";
import { apiPost } from "@/lib/api";

const sections = ["Reception / Intake", "Triage / Consult", "Imaging", "Surgery / Theatre", "ICU", "Ward", "Pharmacy", "Owner Comms", "Insurance"];
const urgencies = ["green", "amber", "red"];
const owners = ["ops_manager", "clinician", "nurse", "admin", "theatre_staff", "ward_staff", "imaging_staff", "stock_controller"];

type CaptureResponse = {
  work_item?: { id?: number };
};

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

  async function submit() {
    if (!title.trim() && !description.trim()) {
      setError("Enter a title or operational note.");
      return;
    }
    setBusy(true);
    setStatus("");
    setError("");
    try {
      const data = await apiPost<CaptureResponse>("/api/input/capture", {
        title: title || description.slice(0, 80) || "Mobile capture",
        description,
        section_name: sectionName,
        urgency,
        owner_role: ownerRole,
        linked_patient_name: patient || null,
        linked_episode_ref: episode || null,
        room_name: room || null,
        actor_name: "Authenticated mobile capture",
      });
      setStatus(`Captured work item #${data.work_item?.id || "new"}. It is now in the hospital work queue.`);
      setTitle("");
      setDescription("");
      setPatient("");
      setEpisode("");
      setRoom("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Capture failed");
    } finally {
      setBusy(false);
    }
  }

  return <HospitalShell title="Mobile Input" subtitle="Capture operational information into the live hospital work queue">
    <div style={{ display: "grid", gap: 12 }}>
      <section className="lw-command-panel">
        <div className="lw-command-header">
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Operational capture</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.05em" }}>Type it once. Create owned work.</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>Use this on phone for intake notes, blockers, owner communications, room problems, case updates or tasks.</p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Link href="/hospital-board" className="lw-pill lw-btn-primary">Hospital board</Link>
            <Link href="/referral-intake" className="lw-pill">Referral intake</Link>
            <Link href="/workspace" className="lw-pill">Work queue</Link>
          </div>
        </div>
      </section>

      <section className="lw-command-panel" style={{ padding: 12, display: "grid", gap: 10 }}>
        <label>Title<input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. MRI owner update overdue" /></label>
        <label>Details<textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Type the operational note here..." rows={7} /></label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
          <label>Section<select value={sectionName} onChange={(e) => setSectionName(e.target.value)}>{sections.map((s) => <option key={s}>{s}</option>)}</select></label>
          <label>Urgency<select value={urgency} onChange={(e) => setUrgency(e.target.value)}>{urgencies.map((u) => <option key={u}>{u}</option>)}</select></label>
          <label>Owner role<select value={ownerRole} onChange={(e) => setOwnerRole(e.target.value)}>{owners.map((o) => <option key={o}>{o}</option>)}</select></label>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
          <label>Patient<input value={patient} onChange={(e) => setPatient(e.target.value)} placeholder="optional" /></label>
          <label>Episode ref<input value={episode} onChange={(e) => setEpisode(e.target.value)} placeholder="optional" /></label>
          <label>Room<input value={room} onChange={(e) => setRoom(e.target.value)} placeholder="MRI / ICU Bay 1 optional" /></label>
        </div>
        <button className="lw-pill lw-btn-primary" style={{ minHeight: 48 }} onClick={() => void submit()} disabled={busy}>{busy ? "Capturing..." : "Create owned work item"}</button>
        {status ? <p style={{ color: "#86efac", margin: 0 }}>{status}</p> : null}
        {error ? <p style={{ color: "#fca5a5", margin: 0 }}>{error}</p> : null}
      </section>
    </div>
  </HospitalShell>;
}

export default function InputPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <InputInner />}</AuthGuard>;
}
