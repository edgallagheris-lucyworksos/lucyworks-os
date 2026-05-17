"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const LANES = [
  "Reception / Intake",
  "Triage / Consult",
  "Imaging",
  "Surgery / Theatre",
  "ICU / Ward",
  "Pharmacy",
  "Discharge / Owner Comms",
];

const TIMES = ["08:00", "08:15", "08:30", "08:45", "09:00", "09:15", "09:30", "09:45", "10:00", "10:15", "10:30", "10:45"];

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
  if (["red", "critical", "blocked", "failed", "unsafe", "overdue"].includes(v)) return "lw-red";
  if (["amber", "warning", "due", "new", "requested", "busy"].includes(v)) return "lw-amber";
  return "lw-green";
}

function formatTime(value?: string) {
  if (!value) return "—";
  try { return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch { return "—"; }
}

function laneFor(item: any) {
  const text = `${item.section_name || ""} ${item.category || ""} ${item.title || ""}`.toLowerCase();
  if (text.includes("surgery") || text.includes("theatre") || text.includes("anaesthesia")) return "Surgery / Theatre";
  if (text.includes("imaging") || text.includes("mri") || text.includes("xray") || text.includes("ct")) return "Imaging";
  if (text.includes("icu") || text.includes("ward") || text.includes("inpatient")) return "ICU / Ward";
  if (text.includes("pharmacy") || text.includes("drug") || text.includes("medication")) return "Pharmacy";
  if (text.includes("discharge") || text.includes("owner") || text.includes("comms")) return "Discharge / Owner Comms";
  if (text.includes("triage") || text.includes("consult")) return "Triage / Consult";
  return item.section_name || "Reception / Intake";
}

function slotFor(index: number) { return TIMES[index % TIMES.length]; }

function Kpi({ label, value, tone }: { label: string; value: any; tone?: string }) {
  return <div className={`lw-kpi ${tone ? toneClass(tone) : ""}`}>
    <div className="lw-kpi-label">{label}</div>
    <div className="lw-kpi-value">{value ?? "—"}</div>
  </div>;
}

function GridEvent({ item }: { item: any }) {
  return <Link href={item.linked_episode_ref ? `/cases/${item.linked_episode_ref}` : "/actions"} className={`mission-event ${toneClass(item.urgency)}`}>
    <div className="mission-event-top"><strong>{(item.urgency || "green").toUpperCase()}</strong><span>{item.status || "new"}</span></div>
    <div className="mission-event-title">{item.title}</div>
    <div className="mission-event-meta">{item.linked_patient_name || "No patient"} {item.linked_episode_ref ? `• ${item.linked_episode_ref}` : ""}</div>
    <div className="mission-event-meta">Owner: {item.owner_role || "UNOWNED"}</div>
  </Link>;
}

function ActionRow({ item }: { item: any }) {
  return <div className="mission-action-row">
    <span className={`lw-pill ${toneClass(item.urgency)}`}>{item.urgency || "green"}</span>
    <div><strong>{item.title}</strong><small>{item.linked_patient_name || "No patient"} • {item.section_name || laneFor(item)} • {item.owner_role || "UNOWNED"}</small></div>
    <Link href={item.linked_episode_ref ? `/cases/${item.linked_episode_ref}` : "/actions"} className="lw-pill">Open</Link>
  </div>;
}

function StaffLoad({ staff }: { staff: any }) {
  return <div className="staff-load-row">
    <strong>{staff.name}</strong>
    <span>{staff.role}</span>
    <small>{staff.skills || "No skills listed"}</small>
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
    setNotice("Seeding hospital operating system...");
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
  const priority = useMemo(() => [...red, ...amber, ...work.filter((w) => !["red", "amber"].includes(w.urgency))].slice(0, 10), [work, red, amber]);
  const byLane = useMemo(() => {
    const map: Record<string, any[]> = {};
    LANES.forEach((lane) => { map[lane] = []; });
    work.forEach((item, index) => {
      const lane = laneFor(item);
      const bucket = LANES.includes(lane) ? lane : "Reception / Intake";
      map[bucket].push({ ...item, __slot: slotFor(index) });
    });
    return map;
  }, [work]);

  return <HospitalShell title="Hospital Board" subtitle="15-minute operational control grid for the whole hospital">
    <div className="mission-board">
      <section className="mission-header">
        <div>
          <div className="ops-eyebrow">LucyWorksOS / hospital operating layer</div>
          <h1>Live hospital control board</h1>
          <p>Single system view: time, department, room/section, patient, owner role, urgency, blocker and next action.</p>
        </div>
        <div className="ops-header-actions">
          <span className={`lw-pill ${toneClass(hospitalState)}`}>HOSPITAL {hospitalState.toUpperCase()}</span>
          <button className="lw-pill lw-btn-primary" onClick={load} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</button>
          <button className="lw-pill" onClick={seed}>Seed / reset live data</button>
          <Link className="lw-pill" href="/api/v3/board">API</Link>
        </div>
      </section>

      {notice ? <div className="ops-notice ok">{notice}</div> : null}
      {error ? <div className="ops-notice fail">{error}</div> : null}

      <section className="mission-kpis">
        <Kpi label="Active cases" value={board?.summary?.active_episodes ?? "—"} />
        <Kpi label="Open work" value={board?.summary?.open_work_items ?? "—"} />
        <Kpi label="Red blockers" value={red.length} tone={red.length ? "red" : "green"} />
        <Kpi label="Amber pressure" value={amber.length} tone={amber.length ? "amber" : "green"} />
        <Kpi label="Unowned" value={unowned.length} tone={unowned.length ? "red" : "green"} />
        <Kpi label="Staff visible" value={board?.summary?.staff_on_system ?? "—"} />
        <Kpi label="Pharmacy" value={board?.summary?.pharmacy_requests ?? "—"} />
      </section>

      <section className="mission-layout">
        <div className="mission-main">
          <div className="mission-panel-head"><h2>15-minute operational grid</h2><span>department lanes × live work/state</span></div>
          <div className="mission-grid-scroll">
            <div className="mission-time-head">
              <div className="mission-lane-title">Lane</div>
              {TIMES.map((time) => <div key={time} className="mission-time-cell">{time}</div>)}
            </div>
            {LANES.map((lane) => <div key={lane} className="mission-lane-row">
              <div className="mission-lane-title"><strong>{lane}</strong><span>{byLane[lane]?.length || 0} active</span></div>
              {TIMES.map((time) => {
                const items = (byLane[lane] || []).filter((item) => item.__slot === time).slice(0, 2);
                return <div key={`${lane}-${time}`} className="mission-slot">
                  {items.map((item) => <GridEvent key={`${item.id}-${time}`} item={item} />)}
                </div>;
              })}
            </div>)}
          </div>
        </div>

        <aside className="mission-side">
          <div className="mission-panel-head"><h2>Command rail</h2><span>act first</span></div>
          <div className="mission-rail-section"><h3>Priority actions</h3>{priority.map((item) => <ActionRow key={item.id} item={item} />)}{!priority.length ? <p className="ops-empty">No active work. Seed data or create case.</p> : null}</div>
          <div className="mission-rail-section"><h3>Staff / specialist visibility</h3>{(board?.staff || []).slice(0, 8).map((s) => <StaffLoad key={s.id} staff={s} />)}</div>
        </aside>
      </section>

      <section className="mission-bottom">
        <div className="mission-intake">
          <div className="mission-panel-head"><h2>Live intake</h2><span>creates case → triage → audit → work item</span></div>
          <div className="ops-form horizontal">
            <label>Patient<input value={form.patient_name} onChange={(e) => setForm({ ...form, patient_name: e.target.value })} placeholder="Patient" /></label>
            <label>Species<select value={form.species} onChange={(e) => setForm({ ...form, species: e.target.value })}><option>dog</option><option>cat</option><option>rabbit</option><option>exotic</option></select></label>
            <label>Owner<input value={form.owner_name} onChange={(e) => setForm({ ...form, owner_name: e.target.value })} placeholder="Owner" /></label>
            <label>Problem<input value={form.presenting_problem} onChange={(e) => setForm({ ...form, presenting_problem: e.target.value })} placeholder="collapse / blocked / vomiting" /></label>
            <label>Symptoms<textarea rows={2} value={form.symptoms_text} onChange={(e) => setForm({ ...form, symptoms_text: e.target.value })} placeholder="Referral / owner notes" /></label>
            <label>Pain<input value={form.pain_score} onChange={(e) => setForm({ ...form, pain_score: e.target.value })} type="number" min="0" max="10" /></label>
            <label className="ops-check"><input type="checkbox" checked={form.consent_obtained} onChange={(e) => setForm({ ...form, consent_obtained: e.target.checked })} /> Consent</label>
            <label className="ops-check"><input type="checkbox" checked={form.financial_constraint} onChange={(e) => setForm({ ...form, financial_constraint: e.target.checked })} /> Finance flag</label>
            <button className="lw-pill lw-btn-primary" onClick={createCase}>Create operational case</button>
          </div>
        </div>
        <div className="mission-audit">
          <div className="mission-panel-head"><h2>Audit / governance</h2><span>latest 12</span></div>
          {(board?.audit || []).slice(0, 12).map((a) => <div className="audit-line" key={a.id}><span>{formatTime(a.created_at)}</span><strong>{a.action}</strong><small>{a.summary}</small></div>)}
        </div>
      </section>
    </div>
  </HospitalShell>;
}

export default function HospitalBoardPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <BoardInner />}</AuthGuard>;
}
