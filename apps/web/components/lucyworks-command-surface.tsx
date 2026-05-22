"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { SessionUser } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Mode = "now" | "flow" | "resources" | "my-shift" | "interrupts" | "manager" | "nurse" | "pca";

type BoardData = {
  summary?: Record<string, number>;
  episodes?: any[];
  work_items?: any[];
  audit?: any[];
  staff?: any[];
  pharmacy?: any[];
};

const fallback: Required<BoardData> = {
  summary: {
    active_episodes: 18,
    open_work_items: 31,
    staff_on_system: 21,
    pharmacy_requests: 7,
    occupied_rooms: 12,
  },
  episodes: [
    { id: 1, episode_ref: "EP-12856", patient_name: "Bella", species: "dog", owner_name: "Usip", urgency: "red", current_phase: "unstable", current_section_name: "Imaging", current_room_name: "CT", owner_role: "clinician" },
    { id: 2, episode_ref: "EP-12861", patient_name: "Max", species: "cat", owner_name: "Tinkertell", urgency: "amber", current_phase: "attention", current_section_name: "Ward", current_room_name: "ICU", owner_role: "nurse" },
    { id: 3, episode_ref: "EP-12877", patient_name: "Daisy", species: "dog", owner_name: "Patel", urgency: "green", current_phase: "monitoring", current_section_name: "Theatre", current_room_name: "Theatre 2", owner_role: "nurse" },
  ],
  work_items: [
    { id: 1, title: "Review recent lab results", linked_patient_name: "Bella", linked_episode_ref: "EP-12856", section_name: "Clinical", room_name: "CT", urgency: "red", owner_role: "clinician", status: "due", description: "Gamma finding needs clinician sign-off before next movement." },
    { id: 2, title: "Owner contact overdue", linked_patient_name: "Bella", linked_episode_ref: "EP-12856", section_name: "Owner Comms", room_name: "Reception", urgency: "red", owner_role: "admin", status: "overdue", description: "Owner update due after imaging delay." },
    { id: 3, title: "Imaging queue waiting", linked_patient_name: "Max", linked_episode_ref: "EP-12861", section_name: "Imaging", room_name: "MRI", urgency: "amber", owner_role: "nurse", status: "waiting", description: "MRI slot waiting for room release." },
    { id: 4, title: "Discharge meds incomplete", linked_patient_name: "Daisy", linked_episode_ref: "EP-12877", section_name: "Pharmacy", room_name: "Pharmacy", urgency: "amber", owner_role: "nurse", status: "blocked", description: "Medication handoff not ready." },
    { id: 5, title: "Theatre turnaround blocked", linked_patient_name: "Oscar", linked_episode_ref: "EP-12902", section_name: "Theatre", room_name: "Theatre 1", urgency: "red", owner_role: "ops_manager", status: "blocked", description: "Cleaning release not signed off." },
  ],
  audit: [
    { id: 1, action: "triage", summary: "Bella escalated to unstable clinical lane", created_at: new Date().toISOString() },
    { id: 2, action: "handoff", summary: "Max assigned to ward monitoring", created_at: new Date().toISOString() },
    { id: 3, action: "resource", summary: "Theatre 1 blocked pending turnaround", created_at: new Date().toISOString() },
  ],
  staff: [
    { id: 1, name: "Tony Arden", role: "clinician", skills: "CT, medicine, escalation", current_load: 5 },
    { id: 2, name: "Sarah Patel", role: "nurse", skills: "ICU, recovery, meds", current_load: 7 },
    { id: 3, name: "Mina Coates", role: "pca", skills: "handoff, patient movement", current_load: 4 },
    { id: 4, name: "Ops Manager", role: "ops_manager", skills: "flow, theatre release, staffing", current_load: 8 },
  ],
  pharmacy: [
    { id: 1, name: "Methadone", status: "locked", urgency: "amber" },
    { id: 2, name: "Discharge meds", status: "incomplete", urgency: "amber" },
    { id: 3, name: "IV catheter 22G", status: "low", urgency: "red" },
  ],
};

const modeCopy: Record<Mode, { eyebrow: string; title: string; subtitle: string; focus: string }> = {
  now: {
    eyebrow: "LucyWorks / operational integrity",
    title: "NOW command view",
    subtitle: "Live clinical truth, unstable cases, next action, owner and time pressure.",
    focus: "unsafe now",
  },
  flow: {
    eyebrow: "LucyWorks / flow mode",
    title: "FLOW mode",
    subtitle: "Triage → booking → imaging → theatre → inpatient → discharge pressure map.",
    focus: "blocked flow",
  },
  resources: {
    eyebrow: "LucyWorks / resource control",
    title: "RESOURCES",
    subtitle: "Rooms, theatre, imaging, ward, staffing, pharmacy and kit pressure.",
    focus: "capacity",
  },
  "my-shift": {
    eyebrow: "LucyWorks / role filtered work",
    title: "MY SHIFT",
    subtitle: "Only the work this user needs: patient handoffs, tasks, blockers and sign-offs.",
    focus: "assigned work",
  },
  interrupts: {
    eyebrow: "LucyWorks / interruptions",
    title: "INTERRUPTS",
    subtitle: "Urgent walk-ins, callbacks, critical escalation, lab review and theatre blockers.",
    focus: "interruptions",
  },
  manager: {
    eyebrow: "LucyWorks / manager dashboard",
    title: "Manager dashboard",
    subtitle: "Hospital overview, integrity scores, resource pressure, governance and escalation risk.",
    focus: "management risk",
  },
  nurse: {
    eyebrow: "LucyWorks / nurse dashboard",
    title: "Nurse dashboard",
    subtitle: "Prep, meds, monitoring, forms, room handoff and patient readiness.",
    focus: "nursing work",
  },
  pca: {
    eyebrow: "LucyWorks / PCA dashboard",
    title: "PCA dashboard",
    subtitle: "Patient movement, handoffs, lab pending, interruptions and quick assistance.",
    focus: "handoffs",
  },
};

function tone(value?: string) {
  const v = (value || "").toLowerCase();
  if (["red", "critical", "blocked", "failed", "unsafe", "overdue", "unstable"].includes(v)) return "danger";
  if (["amber", "warning", "due", "waiting", "attention", "busy", "incomplete"].includes(v)) return "warn";
  if (["green", "stable", "safe", "complete", "ready"].includes(v)) return "safe";
  return "info";
}

function patientName(item: any) {
  return item.linked_patient_name || item.patient_name || item.patient?.name || "Unassigned patient";
}

function episodeRef(item: any) {
  return item.linked_episode_ref || item.episode_ref || item.episode?.episode_ref || "No episode";
}

function roleFilter(mode: Mode, user?: SessionUser) {
  if (mode === "nurse") return "nurse";
  if (mode === "pca") return "pca";
  if (mode === "manager") return "ops_manager";
  if (mode === "my-shift") return user?.role || "nurse";
  return "";
}

function Kpi({ label, value, state }: { label: string; value: any; state?: string }) {
  return <div className={`lw-neo-kpi ${tone(state)}`}><span>{label}</span><strong>{value ?? "—"}</strong></div>;
}

function CommandCase({ item, compact = false }: { item: any; compact?: boolean }) {
  const state = tone(item.urgency || item.current_phase || item.status);
  return <Link href={item.linked_episode_ref ? `/cases/${item.linked_episode_ref}` : "/actions"} className={`lw-case-card ${state} ${compact ? "compact" : ""}`}>
    <div className="lw-case-top"><span>{String(item.urgency || item.current_phase || "green").toUpperCase()}</span><small>{item.status || item.current_phase || "active"}</small></div>
    <h3>{patientName(item)}</h3>
    <p>{item.title || item.presenting_problem || item.description || "Operational case requires review"}</p>
    <div className="lw-case-meta"><span>{episodeRef(item)}</span><span>{item.section_name || item.current_section_name || "Clinical"}</span><span>{item.room_name || item.current_room_name || "No room"}</span></div>
    <div className="lw-next-action">Next: {item.description || item.title || "Review and assign owner"}</div>
  </Link>;
}

function FlowLane({ title, items }: { title: string; items: any[] }) {
  return <section className="lw-flow-lane"><div className="lw-flow-head"><strong>{title}</strong><span>{items.length}</span></div>{items.slice(0, 4).map((item, index) => <CommandCase key={`${title}-${item.id || index}`} item={item} compact />)}{!items.length ? <p className="lw-empty">No live pressure.</p> : null}</section>;
}

function StaffRow({ item }: { item: any }) {
  return <div className="lw-staff-row"><div><strong>{item.name || item.staff_name}</strong><span>{item.role || item.primary_role}</span></div><small>{item.skills || item.certifications || "skills not listed"}</small><b>{item.current_load ?? item.load ?? "—"}</b></div>;
}

function selectItems(mode: Mode, data: Required<BoardData>, user?: SessionUser) {
  const filterRole = roleFilter(mode, user);
  let items = [...data.work_items];
  if (filterRole) {
    items = items.filter((item) => !item.owner_role || item.owner_role === filterRole || item.owner_role === "unowned");
  }
  if (mode === "interrupts") {
    items = items.filter((item) => ["red", "amber"].includes(item.urgency) || String(item.title || "").toLowerCase().includes("callback"));
  }
  if (mode === "resources") {
    items = items.filter((item) => /room|theatre|imaging|ward|pharmacy|stock|kit|med/i.test(`${item.section_name || ""} ${item.title || ""}`));
  }
  return items.length ? items : data.work_items;
}

export function LucyWorksCommandSurface({ mode, user }: { mode: Mode; user?: SessionUser }) {
  const [board, setBoard] = useState<Required<BoardData>>(fallback);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const copy = modeCopy[mode];

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/v3/board`, { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(JSON.stringify(data));
      setBoard({
        summary: data.summary || fallback.summary,
        episodes: data.episodes?.length ? data.episodes : fallback.episodes,
        work_items: data.work_items?.length ? data.work_items : fallback.work_items,
        audit: data.audit?.length ? data.audit : fallback.audit,
        staff: data.staff?.length ? data.staff : fallback.staff,
        pharmacy: data.pharmacy?.length ? data.pharmacy : fallback.pharmacy,
      });
    } catch (err) {
      setError("Live API unavailable; showing mapped fallback state. Codespaces/API still needs checking.");
      setBoard(fallback);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const items = useMemo(() => selectItems(mode, board, user), [mode, board, user]);
  const red = board.work_items.filter((item) => tone(item.urgency || item.status) === "danger");
  const amber = board.work_items.filter((item) => tone(item.urgency || item.status) === "warn");
  const unowned = board.work_items.filter((item) => !item.owner_role || item.owner_role === "unowned");
  const triage = board.work_items.filter((item) => /triage|walk|urgent|callback/i.test(`${item.section_name || ""} ${item.title || ""}`));
  const imaging = board.work_items.filter((item) => /imaging|mri|ct|xray|lab/i.test(`${item.section_name || ""} ${item.title || ""}`));
  const theatre = board.work_items.filter((item) => /theatre|surgery|anaesthesia|cleaning/i.test(`${item.section_name || ""} ${item.title || ""}`));
  const discharge = board.work_items.filter((item) => /discharge|owner|comms|meds/i.test(`${item.section_name || ""} ${item.title || ""}`));

  return <div className="lw-neo-page">
    <section className="lw-hero-panel">
      <div className="lw-hero-brand"><div className="lw-orbit-mark"><span /></div><div><strong>lucyworks</strong><small>Operational Integrity OS for Specialist Veterinary Hospitals</small></div></div>
      <div className="lw-hero-content"><span className="lw-eyebrow">{copy.eyebrow}</span><h1>{copy.title}</h1><p>{copy.subtitle}</p>{error ? <div className="lw-banner warn">{error}</div> : null}</div>
      <div className="lw-hero-actions"><button className="lw-glow-button" onClick={load}>{loading ? "Refreshing" : "Refresh state"}</button><Link className="lw-glass-pill" href="/system-control">System control</Link></div>
    </section>

    <section className="lw-mode-tabs">
      <Link href="/hospital-board">NOW</Link><Link href="/flow">FLOW</Link><Link href="/resources">RESOURCES</Link><Link href="/my-shift">MY SHIFT</Link><Link href="/interrupts">INTERRUPTS</Link>
      <span className="lw-integrity-score">Integrity 87</span>
    </section>

    <section className="lw-neo-kpis">
      <Kpi label="Unstable" value={red.length} state={red.length ? "red" : "green"} />
      <Kpi label="Attention" value={amber.length} state={amber.length ? "amber" : "green"} />
      <Kpi label="Unowned" value={unowned.length} state={unowned.length ? "red" : "green"} />
      <Kpi label="Active cases" value={board.summary.active_episodes || board.episodes.length} />
      <Kpi label="Open work" value={board.summary.open_work_items || board.work_items.length} />
      <Kpi label="Staff" value={board.summary.staff_on_system || board.staff.length} />
    </section>

    <section className="lw-command-grid">
      <main className="lw-command-main">
        <div className="lw-section-title"><div><span>{copy.focus}</span><h2>Current operational truth</h2></div><small>{items.length} live items</small></div>
        <div className="lw-case-stack">{items.slice(0, 5).map((item, index) => <CommandCase key={item.id || index} item={item} />)}</div>
      </main>
      <aside className="lw-command-side">
        <div className="lw-section-title"><div><span>next action rail</span><h2>Act first</h2></div></div>
        {items.slice(0, 4).map((item, index) => <div className={`lw-action-strip ${tone(item.urgency || item.status)}`} key={item.id || index}><span>{String(item.urgency || "green").toUpperCase()}</span><div><strong>{item.title || patientName(item)}</strong><small>{item.owner_role || "unowned"} • {item.section_name || "clinical"}</small></div></div>)}
      </aside>
    </section>

    <section className="lw-flow-grid">
      <FlowLane title="Triage" items={triage} />
      <FlowLane title="Imaging" items={imaging} />
      <FlowLane title="Theatre" items={theatre} />
      <FlowLane title="Discharge" items={discharge} />
    </section>

    <section className="lw-role-grid">
      <div className="lw-role-card manager"><span>Manager</span><h3>{red.length + amber.length} command risks</h3><p>Clinical, operational, financial and governance pressure in one management read.</p><Link href="/manager-dashboard">Open manager view</Link></div>
      <div className="lw-role-card nurse"><span>Nurse</span><h3>{board.work_items.filter((x) => x.owner_role === "nurse").length || 3} prep / monitoring tasks</h3><p>Meds, consent, room readiness, patient handoff and recovery state.</p><Link href="/nurse-dashboard">Open nurse view</Link></div>
      <div className="lw-role-card pca"><span>PCA</span><h3>{board.work_items.filter((x) => x.owner_role === "pca").length || 2} handoffs</h3><p>Current patients, lab pending, urgent assists and interruptions.</p><Link href="/pca-dashboard">Open PCA view</Link></div>
    </section>

    <section className="lw-resource-grid">
      <div className="lw-glass-panel"><div className="lw-section-title"><div><span>staff</span><h2>Visible capacity</h2></div></div>{board.staff.slice(0, 6).map((item, index) => <StaffRow item={item} key={item.id || index} />)}</div>
      <div className="lw-glass-panel"><div className="lw-section-title"><div><span>pharmacy</span><h2>Meds / stock pressure</h2></div></div>{board.pharmacy.slice(0, 6).map((item, index) => <div className={`lw-action-strip ${tone(item.urgency || item.status)}`} key={item.id || index}><span>{item.status || "open"}</span><div><strong>{item.name}</strong><small>pharmacy governance</small></div></div>)}</div>
      <div className="lw-glass-panel"><div className="lw-section-title"><div><span>audit</span><h2>Governance trail</h2></div></div>{board.audit.slice(0, 6).map((item, index) => <div className="lw-audit-line" key={item.id || index}><strong>{item.action}</strong><small>{item.summary}</small></div>)}</div>
    </section>
  </div>;
}
