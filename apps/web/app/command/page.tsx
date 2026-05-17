"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ApiState<T> = { ok: boolean; data: T | null; error?: string };
type DirectorCard = { key: string; label: string; value: number; tone: string };
type SectionPressure = { section_name: string; live: number; red: number; unowned: number };
type WorkItem = { id: number; title: string; urgency: string; owner_role: string; status: string; section_name?: string | null; room_name?: string | null; patient_location_label?: string | null; linked_patient_name?: string | null; linked_episode_ref?: string | null };
type DirectorBoard = { cards: DirectorCard[]; section_pressure: SectionPressure[]; priority_items: WorkItem[] };
type DepartmentPayload = { department: any; roles: any[]; entities: any[]; states: any[]; conflicts: any[]; dashboard_needs: any[] };
type Departments = { summary: { departments: number }; departments: DepartmentPayload[] };
type Workspace = { summary: Record<string, number>; queues: Record<string, any[]> };
type Forecast = { summary: Record<string, number>; groups: Record<string, any>; slots: any[]; next_actions: string[] };
type FlowState = { summary: Record<string, number>; queues?: Record<string, any[]> };

async function getJson<T>(url: string): Promise<ApiState<T>> {
  try {
    const res = await fetch(`${API_BASE}${url}`, { cache: "no-store" });
    const data = await res.json().catch(() => null);
    if (!res.ok) return { ok: false, data: null, error: `${res.status} ${JSON.stringify(data).slice(0, 120)}` };
    return { ok: true, data };
  } catch (err) {
    return { ok: false, data: null, error: err instanceof Error ? err.message : "offline" };
  }
}

function riskClass(value?: string) {
  if (["red", "critical", "CRITICAL", "HIGH", "blocked"].includes(value || "")) return "lw-red";
  if (["amber", "warning", "MODERATE", "MED", "partial"].includes(value || "")) return "lw-amber";
  return "lw-green";
}

function Kpi({ label, value, tone = "green" }: { label: string; value: string | number; tone?: string }) {
  return <div className={`lw-kpi ${riskClass(tone)}`}><div className="lw-kpi-label">{label}</div><div className="lw-kpi-value">{value}</div></div>;
}

function compactNumber(value: any) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "-";
  return Number(value);
}

function DepartmentLane({ dept, sectionPressure }: { dept: DepartmentPayload; sectionPressure?: SectionPressure }) {
  const redConflicts = dept.conflicts.filter((x) => x.severity_default === "red").length;
  const live = sectionPressure?.live ?? 0;
  const red = sectionPressure?.red ?? 0;
  const tone = red || redConflicts ? "red" : live ? "amber" : "green";
  return <article className="lw-command-panel" style={{ overflow: "hidden" }}>
    <div className="lw-command-header" style={{ padding: 12 }}>
      <div>
        <div style={{ color: "#14b8a6", fontSize: 12, fontWeight: 900, textTransform: "uppercase" }}>{dept.department.lucy_module}</div>
        <h3 className="lw-section-title">{dept.department.name}</h3>
      </div>
      <span className={`lw-pill ${riskClass(tone)}`}>{tone.toUpperCase()}</span>
    </div>
    <div className="lw-status-row">
      <div className="lw-status-title">Flow</div>
      <div className="lw-status-meta">live {live} / red {red}</div>
      <div className="lw-status-detail">{dept.department.purpose}</div>
      <Link href="/departments" className="lw-pill">Open</Link>
    </div>
    <div className="lw-status-row">
      <div className="lw-status-title">States</div>
      <div className="lw-status-meta">{dept.states.length}</div>
      <div className="lw-status-detail">{dept.states.slice(0, 4).map((x) => x.state_name).join(" → ")}</div>
      <span className="lw-status-meta">...</span>
    </div>
    <div className="lw-status-row">
      <div className="lw-status-title">Conflicts</div>
      <div className="lw-status-meta">{dept.conflicts.length}</div>
      <div className="lw-status-detail">{dept.conflicts.slice(0, 3).map((x) => x.conflict_name).join(" • ")}</div>
      <span className={`lw-pill ${redConflicts ? "lw-red" : "lw-amber"}`}>{redConflicts} red</span>
    </div>
  </article>;
}

function WorkRow({ item }: { item: WorkItem }) {
  return <div className="lw-status-row">
    <div className="lw-status-title">{item.title}</div>
    <span className={`lw-pill ${riskClass(item.urgency)}`}>{item.urgency}/{item.status}</span>
    <div className="lw-status-detail">{item.section_name || "No section"} • {item.room_name || "No room"} • owner {item.owner_role}</div>
    {item.linked_episode_ref ? <Link className="lw-pill" href={`/episodes/${item.linked_episode_ref}`}>{item.linked_episode_ref}</Link> : <Link className="lw-pill" href="/actions">Action</Link>}
  </div>;
}

function CommandInner() {
  const [board, setBoard] = useState<ApiState<DirectorBoard>>({ ok: false, data: null });
  const [departments, setDepartments] = useState<ApiState<Departments>>({ ok: false, data: null });
  const [workspace, setWorkspace] = useState<ApiState<Workspace>>({ ok: false, data: null });
  const [forecast, setForecast] = useState<ApiState<Forecast>>({ ok: false, data: null });
  const [flow, setFlow] = useState<ApiState<FlowState>>({ ok: false, data: null });
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    const [b, d, w, f, fl] = await Promise.all([
      getJson<DirectorBoard>("/api/director-board"),
      getJson<Departments>("/api/departments"),
      getJson<Workspace>("/api/workspace?role=ops_manager"),
      getJson<Forecast>("/api/forecast/hospital?hours=12&slot_minutes=60"),
      getJson<FlowState>("/api/flow-state"),
    ]);
    setBoard(b); setDepartments(d); setWorkspace(w); setForecast(f); setFlow(fl);
    setLoading(false);
  }

  async function firstRun() {
    setNotice("Seeding hospital system...");
    await fetch(`${API_BASE}/api/admin/first-run`, { method: "POST" }).catch(() => null);
    setNotice("Seed complete. Reloading command overview...");
    await load();
    setNotice("Command overview refreshed.");
  }

  useEffect(() => { load(); }, []);

  const pressureBySection = useMemo(() => {
    const map: Record<string, SectionPressure> = {};
    (board.data?.section_pressure || []).forEach((s) => { map[s.section_name.toLowerCase()] = s; });
    return map;
  }, [board.data]);

  const workspaceTotal = Object.values(workspace.data?.summary || {}).reduce((a: any, b: any) => Number(a) + Number(b), 0);
  const redItems = board.data?.priority_items?.filter((x) => x.urgency === "red" && x.status !== "done").length || 0;
  const redSlots = forecast.data?.summary?.red_slots || 0;
  const amberSlots = forecast.data?.summary?.amber_slots || 0;
  const openBlockers = flow.data?.summary?.open_discharge_blockers ?? flow.data?.summary?.discharge_blockers ?? "-";
  const hospitalTone = redItems || redSlots ? "red" : amberSlots ? "amber" : "green";

  return <HospitalShell title="Hospital Overview" subtitle="Whole-hospital command board: departments, flow, people, rooms, risk and next actions">
    <div style={{ display: "grid", gap: 12 }}>
      <section className="lw-command-panel">
        <div className="lw-command-header">
          <div>
            <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Lucy Command / Hospital overview</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, letterSpacing: "-0.05em" }}>One screen for the hospital, not a pile of module cards.</h1>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>Reception, triage, imaging, theatre, ICU/ward, staff, blockers, forecast and actions on one operational board.</p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span className={`lw-pill ${riskClass(hospitalTone)}`}>STATE {hospitalTone.toUpperCase()}</span>
            <button className="lw-pill lw-btn-primary" onClick={load} disabled={loading}>{loading ? "Loading..." : "Refresh"}</button>
            <button className="lw-pill" onClick={firstRun}>First Run</button>
            <Link href="/actions" className="lw-pill">Actions</Link>
            <Link href="/system-control" className="lw-pill">System</Link>
          </div>
        </div>
        {notice ? <div style={{ padding: "0 14px 12px", color: "#86efac" }}>{notice}</div> : null}
      </section>

      <section className="lw-kpi-strip">
        <Kpi label="Red priority" value={redItems} tone={redItems ? "red" : "green"} />
        <Kpi label="Forecast red slots" value={compactNumber(redSlots)} tone={redSlots ? "red" : amberSlots ? "amber" : "green"} />
        <Kpi label="Forecast amber" value={compactNumber(amberSlots)} tone={amberSlots ? "amber" : "green"} />
        <Kpi label="Workspace load" value={workspaceTotal || "-"} tone={workspaceTotal > 20 ? "amber" : "green"} />
        <Kpi label="Flow blockers" value={openBlockers} tone={Number(openBlockers) ? "red" : "green"} />
        <Kpi label="Departments" value={departments.data?.summary?.departments || 0} tone={departments.data?.summary?.departments ? "green" : "red"} />
      </section>

      {(!departments.ok || !board.ok || !workspace.ok || !forecast.ok || !flow.ok) ? <section className="lw-command-panel">
        <div className="lw-command-header"><h2 className="lw-section-title">Broken / not connected</h2><button className="lw-pill lw-btn-primary" onClick={firstRun}>Seed and retry</button></div>
        {[['Director board', board], ['Departments', departments], ['Workspace', workspace], ['Forecast', forecast], ['Flow state', flow]].map(([label, state]: any) => !state.ok ? <div key={label} className="lw-status-row"><div className="lw-status-title">{label}</div><span className="lw-pill lw-red">FAIL</span><div className="lw-status-detail">{state.error || 'Not connected'}</div><span className="lw-status-meta">needs backend/seed</span></div> : null)}
      </section> : null}

      <section className="lw-command-panel">
        <div className="lw-command-header"><h2 className="lw-section-title">Department command lanes</h2><span className="lw-status-meta">Reception → triage → diagnostics → theatre → ICU/ward</span></div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 10, padding: 10 }}>
          {(departments.data?.departments || []).map((dept) => {
            const key = dept.department.name.toLowerCase().split(" /")[0];
            const pressure = pressureBySection[key] || pressureBySection[dept.department.name.toLowerCase()] || pressureBySection[dept.department.code?.replaceAll('_', ' ')];
            return <DepartmentLane key={dept.department.code} dept={dept} sectionPressure={pressure} />;
          })}
        </div>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.25fr) minmax(320px, 0.75fr)", gap: 12 }}>
        <section className="lw-command-panel">
          <div className="lw-command-header"><h2 className="lw-section-title">Priority actions</h2><Link href="/actions" className="lw-pill">Open Actions</Link></div>
          <div>{(board.data?.priority_items || []).slice(0, 12).map((item) => <WorkRow key={item.id} item={item} />)}</div>
        </section>

        <section className="lw-command-panel">
          <div className="lw-command-header"><h2 className="lw-section-title">Forecast pressure</h2><Link href="/pulse" className="lw-pill">Lucy Pulse</Link></div>
          <div>
            {Object.entries(forecast.data?.groups || {}).slice(0, 8).map(([group, row]: any) => <div key={group} className="lw-status-row">
              <div className="lw-status-title">{group}</div>
              <span className={`lw-pill ${riskClass(row.risk)}`}>{row.risk}</span>
              <div className="lw-status-detail">load {row.load_blocks} / capacity {row.capacity}</div>
              <span className="lw-status-meta">12h</span>
            </div>)}
            {(forecast.data?.next_actions || []).slice(0, 5).map((action) => <div key={action} className="lw-status-row"><div className="lw-status-title">Next</div><span className="lw-pill lw-info">ACTION</span><div className="lw-status-detail">{action}</div><Link href="/actions" className="lw-pill">Open</Link></div>)}
          </div>
        </section>
      </div>

      <section className="lw-mobile-actionbar">
        <Link href="/system-control" className="lw-pill">System</Link>
        <Link href="/departments" className="lw-pill">Departments</Link>
        <Link href="/workspace" className="lw-pill">Workspace</Link>
        <Link href="/actions" className="lw-pill">Actions</Link>
        <Link href="/flow-state" className="lw-pill">Flow</Link>
        <Link href="/overnight" className="lw-pill">Care</Link>
      </section>
    </div>
  </HospitalShell>;
}

export default function CommandPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <CommandInner />}</AuthGuard>;
}
