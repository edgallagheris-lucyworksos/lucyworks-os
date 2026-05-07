"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Board = {
  summary: Record<string, number>;
  episodes: any[];
  work_items: any[];
  audit: any[];
  staff: any[];
  pharmacy: any[];
};

type CaseForm = {
  patient_name: string;
  species: string;
  owner_name: string;
  presenting_problem: string;
  symptoms_text: string;
  pain_score: string;
  repeat_sedation_6mo: string;
  consent_obtained: boolean;
  financial_constraint: boolean;
};

const defaultCaseForm: CaseForm = {
  patient_name: "",
  species: "dog",
  owner_name: "",
  presenting_problem: "",
  symptoms_text: "",
  pain_score: "",
  repeat_sedation_6mo: "0",
  consent_obtained: true,
  financial_constraint: false,
};

function toneClass(value?: string) {
  const v = (value || "").toLowerCase();
  if (["red", "critical", "blocked", "failed", "unsafe"].includes(v)) return "lw-red";
  if (["amber", "warning", "due", "new", "requested"].includes(v)) return "lw-amber";
  return "lw-green";
}

function formatTime(value?: string) {
  if (!value) return "—";
  try { return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch { return "—"; }
}

function Kpi({ label, value, tone }: { label: string; value: any; tone?: string }) {
  return <div className={`lw-kpi ${tone ? toneClass(tone) : ""}`}>
    <div className="lw-kpi-label">{label}</div>
    <div className="lw-kpi-value">{value ?? "—"}</div>
  </div>;
}

function EventRow({ item }: { item: any }) {
  return <div className="ops-row">
    <div className="ops-time">{formatTime(item.created_at)}</div>
    <div className="ops-main">
      <strong>{item.title}</strong>
      <span>{item.linked_patient_name || "No patient"} {item.linked_episode_ref ? `• ${item.linked_episode_ref}` : ""}</span>
    </div>
    <div className="ops-location">{item.section_name || "Unassigned section"}<br /><span>{item.room_name || "No room"}</span></div>
    <div className="ops-owner">{item.owner_role || "unowned"}</div>
    <div className="ops-status"><span className={`lw-pill ${toneClass(item.urgency)}`}>{item.urgency || "—"}</span><span className="lw-pill">{item.status}</span></div>
    <div className="ops-action"><Link className="lw-pill" href={item.linked_episode_ref ? `/cases/${item.linked_episode_ref}` : "/actions"}>Open</Link></div>
  </div>;
}

function StaffRow({ staff }: { staff: any }) {
  return <div className="ops-row compact">
    <div className="ops-main"><strong>{staff.name}</strong><span>{staff.role}</span></div>
    <div className="ops-location">Skills<br /><span>{staff.skills || "—"}</span></div>
    <div className="ops-owner">{staff.active ? "active" : "off"}</div>
    <div className="ops-status"><span className="lw-pill lw-info">staff</span></div>
  </div>;
}

function AuditRow({ audit }: { audit: any }) {
  return <div className="ops-row compact">
    <div className="ops-time">{formatTime(audit.created_at)}</div>
    <div className="ops-main"><strong>{audit.action}</strong><span>{audit.summary}</span></div>
    <div className="ops-owner">{audit.actor_name}</div>
    <div className="ops-status"><span className="lw-pill lw-info">audit</span></div>
  </div>;
}

function BoardInner() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<CaseForm>(defaultCaseForm);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/v3/board`, { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(JSON.stringify(data));
      setBoard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hospital board failed to load");
    } finally {
      setLoading(false);
    }
  }

  async function seed() {
    setNotice("Seeding hospital system...");
    await fetch(`${API_BASE}/api/admin/first-run`, { method: "POST" }).catch(() => null);
    await load();
    setNotice("System seeded/refreshed.");
  }

  async function createCase() {
    setError("");
    setNotice("");
    try {
      const payload = {
        ...form,
        owner_name: form.owner_name || "Unknown owner",
        pain_score: form.pain_score ? Number(form.pain_score) : null,
        repeat_sedation_6mo: Number(form.repeat_sedation_6mo || 0),
        actor_name: "Hospital Board",
      };
      const res = await fetch(`${API_BASE}/api/v3/cases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(JSON.stringify(data));
      setNotice(`Created ${data.episode?.episode_ref}: ${data.triage?.urgency?.toUpperCase()} / handoff ${data.triage?.handoff}`);
      setForm(defaultCaseForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create case failed");
    }
  }

  useEffect(() => { load(); }, []);

  const work = board?.work_items || [];
  const red = work.filter((w) => w.urgency === "red");
  const amber = work.filter((w) => w.urgency === "amber");
  const unowned = work.filter((w) => !w.owner_role || w.owner_role === "unowned");
  const hospitalState = red.length ? "red" : amber.length ? "amber" : "green";
  const nowItems = useMemo(() => work.slice(0, 12), [work]);

  return <HospitalShell title="Hospital Board" subtitle="One serious operational surface: intake, triage, ownership, audit, pharmacy and work control">
    <div className="ops-board">
      <section className="ops-header">
        <div>
          <div className="ops-eyebrow">LucyWorksOS / live hospital operations</div>
          <h1>Day-running board</h1>
          <p>Not a marketing dashboard. This is the working surface: what is happening, who owns it, where it is, what is blocked, and what must happen next.</p>
        </div>
        <div className="ops-header-actions">
          <span className={`lw-pill ${toneClass(hospitalState)}`}>STATE {hospitalState.toUpperCase()}</span>
          <button className="lw-pill lw-btn-primary" onClick={load} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</button>
          <button className="lw-pill" onClick={seed}>First Run / Seed</button>
          <Link className="lw-pill" href="/system-control">System</Link>
        </div>
      </section>

      {notice ? <div className="ops-notice ok">{notice}</div> : null}
      {error ? <div className="ops-notice fail">{error}</div> : null}

      <section className="lw-kpi-strip">
        <Kpi label="Active cases" value={board?.summary?.active_episodes ?? "—"} />
        <Kpi label="Open work" value={board?.summary?.open_work_items ?? "—"} />
        <Kpi label="Red" value={red.length} tone={red.length ? "red" : "green"} />
        <Kpi label="Amber" value={amber.length} tone={amber.length ? "amber" : "green"} />
        <Kpi label="Unowned" value={unowned.length} tone={unowned.length ? "red" : "green"} />
        <Kpi label="Staff" value={board?.summary?.staff_on_system ?? "—"} />
        <Kpi label="Pharmacy" value={board?.summary?.pharmacy_requests ?? "—"} />
      </section>

      <div className="ops-grid">
        <section className="ops-panel main">
          <div className="ops-panel-head"><h2>Now / priority worklist</h2><span>time → event → location → owner → status → action</span></div>
          <div className="ops-table-head"><span>Time</span><span>What</span><span>Where</span><span>Owner</span><span>Status</span><span>Action</span></div>
          {nowItems.map((item) => <EventRow key={item.id} item={item} />)}
          {!nowItems.length ? <p className="ops-empty">No live work items. Press First Run or create a case.</p> : null}
        </section>

        <section className="ops-panel side">
          <div className="ops-panel-head"><h2>Create case / intake</h2><span>v3 working pattern</span></div>
          <div className="ops-form">
            <label>Patient<input value={form.patient_name} onChange={(e) => setForm({ ...form, patient_name: e.target.value })} placeholder="Bella" /></label>
            <label>Species<select value={form.species} onChange={(e) => setForm({ ...form, species: e.target.value })}><option>dog</option><option>cat</option><option>rabbit</option><option>exotic</option></select></label>
            <label>Owner<input value={form.owner_name} onChange={(e) => setForm({ ...form, owner_name: e.target.value })} placeholder="Owner name" /></label>
            <label>Presenting problem<input value={form.presenting_problem} onChange={(e) => setForm({ ...form, presenting_problem: e.target.value })} placeholder="collapse / blocked / vomiting..." /></label>
            <label>Symptoms<textarea rows={4} value={form.symptoms_text} onChange={(e) => setForm({ ...form, symptoms_text: e.target.value })} placeholder="Free text owner/referral notes" /></label>
            <div className="ops-form-two"><label>Pain<input value={form.pain_score} onChange={(e) => setForm({ ...form, pain_score: e.target.value })} type="number" min="0" max="10" /></label><label>Sedations 6mo<input value={form.repeat_sedation_6mo} onChange={(e) => setForm({ ...form, repeat_sedation_6mo: e.target.value })} type="number" min="0" /></label></div>
            <label className="ops-check"><input type="checkbox" checked={form.consent_obtained} onChange={(e) => setForm({ ...form, consent_obtained: e.target.checked })} /> Consent obtained</label>
            <label className="ops-check"><input type="checkbox" checked={form.financial_constraint} onChange={(e) => setForm({ ...form, financial_constraint: e.target.checked })} /> Financial constraint</label>
            <button className="lw-pill lw-btn-primary" onClick={createCase}>Create + triage + audit</button>
          </div>
        </section>
      </div>

      <div className="ops-grid lower">
        <section className="ops-panel"><div className="ops-panel-head"><h2>Specialists / staff capacity</h2><span>skills and ownership</span></div>{(board?.staff || []).map((s) => <StaffRow key={s.id} staff={s} />)}</section>
        <section className="ops-panel"><div className="ops-panel-head"><h2>Audit / governance trail</h2><span>who did what, when, why</span></div>{(board?.audit || []).slice(0, 12).map((a) => <AuditRow key={a.id} audit={a} />)}</section>
      </div>
    </div>
  </HospitalShell>;
}

export default function HospitalBoardPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <BoardInner />}</AuthGuard>;
}
