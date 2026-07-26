"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { getSession } from "@/lib/session";

type WorkItem = {
  id: number;
  title: string;
  description: string;
  category: string;
  source: string;
  urgency: string;
  status: string;
  ownerRole: string;
  patientName?: string | null;
  episodeRef?: string | null;
  linkedToCanonicalEpisode: boolean;
  sectionName?: string | null;
  roomName?: string | null;
  dueAt?: string | null;
  overdue: boolean;
  links: { episode?: string | null; patientRecord?: string | null };
};

type ScheduleItem = {
  blockRef: string;
  procedureName: string;
  areaName: string;
  startsAt: string;
  endsAt: string;
  status: string;
  riskLevel: string;
  leadStaffName?: string | null;
  blockerCount: number;
  conflictCount: number;
};

type PatientFlow = {
  episodeRef: string;
  patientName: string;
  serviceLine: string;
  urgency: string;
  phase: string;
  ownerRole: string;
  ownerSubject?: string | null;
  currentAreaRef?: string | null;
  currentAreaName?: string | null;
  nextAction: string;
  scheduled: boolean;
  attention: string[];
  gates: Record<string, unknown>;
  flags: string[];
  taskCount: number;
  redTaskCount: number;
  overdueTaskCount: number;
  schedule: ScheduleItem[];
  links: { episode: string; patientRecord: string; clinicalExecution: string };
};

type Workspace = {
  workspaceVersion: string;
  generatedAt: string;
  operationalDate: string;
  premises: { name: string };
  requestedBy: { name: string; role: string };
  summary: {
    activePatients: number;
    scheduledPatients: number;
    unscheduledPatients: number;
    boardBlocks: number;
    redAttention: number;
    overdueTasks: number;
    blockedTasks: number;
    unlinkedTasks: number;
  };
  patientFlow: PatientFlow[];
  tasks: WorkItem[];
  unlinkedTasks: WorkItem[];
  conflicts: Array<{ severity: string; explanation: string }>;
  consistency: { message: string };
};

type View = "attention" | "patients" | "unlinked";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function displayTime(value?: string | null) {
  if (!value) return "No deadline";
  return new Date(value).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function displayClock(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "blocked", "overdue", "emergency"].includes(normal)) return "red";
  if (["amber", "urgent", "in_progress", "pending"].includes(normal)) return "amber";
  return "green";
}

export function OperationalWorkspaceV14() {
  const [data, setData] = useState<Workspace | null>(null);
  const [operationalDate, setOperationalDate] = useState(today());
  const [view, setView] = useState<View>("attention");
  const [status, setStatus] = useState("Loading patient command");
  const [busyId, setBusyId] = useState<number | null>(null);
  const session = getSession();
  const role = session?.user.role || "unknown";

  const refresh = useCallback(async () => {
    try {
      const result = await apiGet<Workspace>(`/api/v14/operational-workspace?operational_date=${operationalDate}`);
      setData(result);
      setStatus(`Live · updated ${new Date(result.generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Patient command unavailable");
    }
  }, [operationalDate]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [refresh]);

  async function act(item: WorkItem, action: "start" | "complete" | "block" | "return_to_queue") {
    setBusyId(item.id);
    setStatus(`${label(action)}: ${item.title}`);
    try {
      await apiPost(`/api/v14/operational-workspace/work-items/${item.id}/action`, {
        action,
        expectedStatus: item.status,
        note: `${label(action)} from patient-centred workspace`,
      });
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  const attentionTasks = useMemo(() => {
    if (!data) return [];
    return data.tasks
      .filter(item => item.urgency === "red" || item.overdue || item.status === "blocked" || item.ownerRole === role)
      .sort((a, b) => Number(b.overdue) - Number(a.overdue) || (a.urgency === "red" ? -1 : 1));
  }, [data, role]);

  const sortedPatients = useMemo(() => {
    if (!data) return [];
    return [...data.patientFlow].sort((a, b) => b.attention.length - a.attention.length || b.redTaskCount - a.redTaskCount || a.patientName.localeCompare(b.patientName));
  }, [data]);

  if (!data) return <main className="pwLoading"><style>{css}</style>{status}</main>;

  const visibleTasks = view === "unlinked" ? data.unlinkedTasks : attentionTasks;

  return <main className="pw">
    <style>{css}</style>
    <header className="hero">
      <div>
        <span>LucyWorks OS · patient-centred command v14</span>
        <h1>Patient command</h1>
        <p>Who needs what, by when, from whom — without losing consent, records, handovers or accountability.</p>
      </div>
      <nav>
        <Link href="/referral-intake">New referral</Link>
        <Link href="/input">Quick input</Link>
        <Link href="/hospital-board">Hospital board</Link>
        <Link href="/system-control">System control</Link>
      </nav>
    </header>

    <section className="toolbar">
      <label>Operating date<input type="date" value={operationalDate} onChange={event => setOperationalDate(event.target.value)} /></label>
      <strong aria-live="polite">{status}</strong>
      <button onClick={() => void refresh()}>Refresh</button>
    </section>

    <section className="kpis">
      <article><b>{data.summary.activePatients}</b><small>active patients</small></article>
      <article><b>{data.summary.scheduledPatients}</b><small>scheduled today</small></article>
      <article className={data.summary.unscheduledPatients ? "amber" : "green"}><b>{data.summary.unscheduledPatients}</b><small>need scheduling</small></article>
      <article className={data.summary.redAttention ? "red" : "green"}><b>{data.summary.redAttention}</b><small>red attention</small></article>
      <article className={data.summary.overdueTasks ? "red" : "green"}><b>{data.summary.overdueTasks}</b><small>overdue tasks</small></article>
      <article className={data.summary.unlinkedTasks ? "amber" : "green"}><b>{data.summary.unlinkedTasks}</b><small>tasks need linking</small></article>
    </section>

    {data.summary.unlinkedTasks ? <section className="integrity amber">
      <div><b>Patient-linking gap</b><p>{data.summary.unlinkedTasks} operational task{data.summary.unlinkedTasks === 1 ? "" : "s"} cannot yet change the canonical patient flow because no matching episode is linked.</p></div>
      <button onClick={() => setView("unlinked")}>Review unlinked work</button>
    </section> : <section className="integrity green"><div><b>One operational truth</b><p>{data.consistency.message}</p></div></section>}

    <nav className="viewTabs" aria-label="Workspace views">
      <button className={view === "attention" ? "active" : ""} onClick={() => setView("attention")}>Attention now <span>{attentionTasks.length}</span></button>
      <button className={view === "patients" ? "active" : ""} onClick={() => setView("patients")}>Patient flow <span>{data.patientFlow.length}</span></button>
      <button className={view === "unlinked" ? "active" : ""} onClick={() => setView("unlinked")}>Needs linking <span>{data.unlinkedTasks.length}</span></button>
    </nav>

    {view !== "patients" ? <section className="taskList">
      <div className="sectionHead"><div><span>{view === "unlinked" ? "DATA QUALITY" : "ACTION QUEUE"}</span><h2>{view === "unlinked" ? "Link work before it is treated as patient care" : "Do the next safe thing"}</h2></div><small>{visibleTasks.length} item{visibleTasks.length === 1 ? "" : "s"}</small></div>
      {visibleTasks.length ? visibleTasks.map(item => <article className={`task ${tone(item.overdue ? "overdue" : item.urgency)}`} key={item.id}>
        <div className="taskMain">
          <div className="taskMeta">
            <span className={`pill ${tone(item.urgency)}`}>{item.overdue ? "OVERDUE" : item.urgency.toUpperCase()}</span>
            <span>{label(item.status)}</span>
            <span>{label(item.ownerRole)}</span>
          </div>
          <h3>{item.title}</h3>
          <p>{item.description || "No explanatory note recorded."}</p>
          <dl>
            <div><dt>Patient</dt><dd>{item.patientName || "Not linked"}</dd></div>
            <div><dt>Episode</dt><dd>{item.episodeRef || "Not linked"}</dd></div>
            <div><dt>Area</dt><dd>{item.roomName || item.sectionName || "Not recorded"}</dd></div>
            <div><dt>Due</dt><dd>{displayTime(item.dueAt)}</dd></div>
          </dl>
          <div className="deepLinks">
            {item.links.episode ? <Link href={item.links.episode}>Open episode</Link> : <Link href="/referral-intake">Find or create episode</Link>}
            {item.links.patientRecord ? <Link href={item.links.patientRecord}>Patient record</Link> : null}
          </div>
        </div>
        <div className="taskActions">
          {item.status === "new" ? <button disabled={busyId === item.id} onClick={() => void act(item, "start")}>Start</button> : null}
          {item.status === "in_progress" ? <button disabled={busyId === item.id} onClick={() => void act(item, "complete")}>Complete</button> : null}
          {["new", "in_progress"].includes(item.status) ? <button className="secondary" disabled={busyId === item.id} onClick={() => void act(item, "block")}>Block</button> : null}
          {item.status === "blocked" ? <button disabled={busyId === item.id} onClick={() => void act(item, "return_to_queue")}>Return to queue</button> : null}
          {item.status === "blocked" ? <button className="secondary" disabled={busyId === item.id} onClick={() => void act(item, "complete")}>Resolve</button> : null}
        </div>
      </article>) : <article className="empty"><b>No items in this view.</b><p>Use Patient flow to review active care, or Quick input to record a new operational problem.</p></article>}
    </section> : <section className="patientList">
      <div className="sectionHead"><div><span>CONTINUITY OF CARE</span><h2>Every active patient, next action and safety gate</h2></div><small>{sortedPatients.length} active</small></div>
      {sortedPatients.length ? sortedPatients.map(patient => <article className={`patient ${patient.attention.length ? "attention" : ""}`} key={patient.episodeRef}>
        <header>
          <div><span>{patient.episodeRef}</span><h3>{patient.patientName}</h3><p>{label(patient.phase)} · owner {label(patient.ownerRole)}</p></div>
          <span className={`pill ${tone(patient.urgency)}`}>{patient.urgency.toUpperCase()}</span>
        </header>
        <section className="nextAction"><small>NEXT SAFE ACTION</small><b>{patient.nextAction}</b></section>
        <dl>
          <div><dt>Current area</dt><dd>{patient.currentAreaName || patient.currentAreaRef || "Not placed"}</dd></div>
          <div><dt>Schedule</dt><dd>{patient.scheduled ? `${patient.schedule.length} block${patient.schedule.length === 1 ? "" : "s"}` : "Not scheduled"}</dd></div>
          <div><dt>Open tasks</dt><dd>{patient.taskCount}</dd></div>
          <div><dt>Flags</dt><dd>{patient.attention.length}</dd></div>
        </dl>
        {patient.schedule.length ? <div className="scheduleStrip">{patient.schedule.map(block => <button key={block.blockRef} className={tone(block.riskLevel)}>
          <time>{displayClock(block.startsAt)}–{displayClock(block.endsAt)}</time><b>{block.procedureName}</b><span>{block.areaName}</span><small>{block.leadStaffName || "Lead not assigned"}{block.conflictCount ? ` · ${block.conflictCount} conflict` : ""}</small>
        </button>)}</div> : <div className="unscheduled"><b>No operational block today.</b><span>Acceptance alone does not allocate a room, staff or time.</span><Link href="/hospital-board">Open board</Link></div>}
        {patient.attention.length ? <div className="attentionList"><b>Must be resolved or acknowledged</b>{patient.attention.slice(0, 6).map(item => <span key={item}>{item}</span>)}</div> : <div className="clear"><b>No current red or overdue evidence gaps.</b></div>}
        <footer><Link href={patient.links.episode}>Episode command</Link><Link href={patient.links.patientRecord}>Patient record</Link><Link href={patient.links.clinicalExecution}>Clinical execution</Link></footer>
      </article>) : <article className="empty"><b>No canonical active patients.</b><p>Create a governed referral intake. Legacy seed records are deliberately not counted as live patient care.</p><Link href="/referral-intake">Create referral</Link></article>}
    </section>}
  </main>;
}

const css = `
.pwLoading{min-height:100vh;display:grid;place-items:center;background:#071019;color:#e2e8f0;font:800 18px system-ui}.pw{min-height:100vh;background:#e9eef5;color:#0f172a;padding:10px;font-family:Inter,system-ui,sans-serif}.pw *{box-sizing:border-box}.hero{display:flex;justify-content:space-between;gap:18px;background:#071019;color:white;border-radius:18px;padding:18px}.hero>div{max-width:780px}.hero span,.sectionHead span{color:#2dd4bf;font-size:11px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.hero h1{font-size:clamp(38px,7vw,72px);line-height:.92;margin:7px 0}.hero p{margin:0;color:#b6c2d1;font-size:16px}.hero nav{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}.hero a,.toolbar button,.integrity button,.taskActions button{border:1px solid #334155;border-radius:999px;padding:10px 13px;background:#0f172a;color:white;text-decoration:none;font-weight:850;cursor:pointer}.toolbar{display:flex;gap:10px;align-items:end;flex-wrap:wrap;background:white;border:1px solid #cbd5e1;border-radius:14px;padding:10px;margin:10px 0}.toolbar label{display:grid;gap:4px;font-size:12px;font-weight:850;color:#475569}.toolbar input{min-height:42px;border:1px solid #94a3b8;border-radius:9px;padding:8px;font-size:16px}.toolbar strong{margin-left:auto;color:#475569}.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.kpis article{background:white;border:1px solid #cbd5e1;border-top:5px solid #64748b;border-radius:13px;padding:11px}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{display:block;font-size:30px;line-height:1}.kpis small{display:block;color:#64748b;margin-top:5px}.integrity{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid #cbd5e1;border-left:7px solid #16a34a;background:white;border-radius:14px;padding:12px;margin-top:10px}.integrity.amber{border-left-color:#f59e0b}.integrity b{font-size:18px}.integrity p{margin:3px 0;color:#475569}.viewTabs{display:flex;gap:8px;overflow:auto;padding:12px 0 9px}.viewTabs button{flex:0 0 auto;border:1px solid #cbd5e1;border-radius:999px;background:white;padding:10px 14px;font-weight:900;color:#334155}.viewTabs button.active{background:#0f172a;color:white;border-color:#0f172a}.viewTabs span{display:inline-grid;place-items:center;min-width:22px;height:22px;margin-left:5px;border-radius:999px;background:#e2e8f0;color:#0f172a}.sectionHead{display:flex;justify-content:space-between;align-items:end;gap:10px;margin:8px 0}.sectionHead h2{font-size:clamp(26px,5vw,42px);line-height:1;margin:5px 0 0}.sectionHead small{color:#64748b;font-weight:800}.taskList,.patientList{display:grid;gap:10px}.task{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;background:white;border:1px solid #cbd5e1;border-left:7px solid #16a34a;border-radius:15px;padding:14px}.task.red{border-left-color:#dc2626}.task.amber{border-left-color:#f59e0b}.taskMeta{display:flex;gap:7px;flex-wrap:wrap;align-items:center;color:#64748b;font-size:12px;font-weight:800}.pill{display:inline-flex;width:max-content;border-radius:999px;padding:5px 8px;background:#e2e8f0;color:#334155;font-size:11px;font-weight:950}.pill.red{background:#fee2e2;color:#991b1b}.pill.amber{background:#fef3c7;color:#92400e}.pill.green{background:#dcfce7;color:#166534}.task h3{font-size:22px;margin:8px 0 4px}.task p{margin:0;color:#475569}.task dl,.patient dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}.task dl div,.patient dl div{background:#f8fafc;border:1px solid #e2e8f0;border-radius:9px;padding:8px}.task dt,.patient dt{font-size:10px;font-weight:900;color:#64748b;text-transform:uppercase;letter-spacing:.08em}.task dd,.patient dd{margin:3px 0 0;font-weight:800;overflow-wrap:anywhere}.deepLinks,.patient footer{display:flex;gap:12px;flex-wrap:wrap}.deepLinks a,.patient footer a,.unscheduled a,.empty a{color:#1d4ed8;font-weight:900}.taskActions{display:flex;flex-direction:column;gap:7px;justify-content:center;min-width:130px}.taskActions .secondary{background:white;color:#0f172a;border-color:#94a3b8}.taskActions button:disabled{opacity:.45}.patient{background:white;border:1px solid #cbd5e1;border-radius:16px;padding:14px}.patient.attention{border-left:7px solid #dc2626}.patient>header{display:flex;justify-content:space-between;gap:10px}.patient header span{font-size:11px;color:#64748b;font-weight:850}.patient h3{font-size:28px;margin:3px 0}.patient header p{margin:0;color:#475569}.nextAction{display:grid;gap:3px;background:#071019;color:white;border-radius:11px;padding:12px;margin-top:12px}.nextAction small{color:#2dd4bf;font-weight:900;letter-spacing:.1em}.nextAction b{font-size:18px}.scheduleStrip{display:flex;gap:8px;overflow:auto;padding:2px 0 10px}.scheduleStrip button{display:grid;gap:3px;min-width:190px;text-align:left;border:1px solid #cbd5e1;border-left:6px solid #16a34a;background:#f8fafc;border-radius:10px;padding:9px}.scheduleStrip button.red{border-left-color:#dc2626}.scheduleStrip button.amber{border-left-color:#f59e0b}.scheduleStrip time{font-weight:900}.scheduleStrip span,.scheduleStrip small{color:#64748b}.unscheduled{display:flex;gap:9px;align-items:center;flex-wrap:wrap;border:1px solid #f59e0b;background:#fffbeb;border-radius:10px;padding:10px}.unscheduled span{color:#92400e}.attentionList,.clear{display:grid;gap:5px;border-radius:10px;padding:10px;margin:4px 0 12px}.attentionList{border:1px solid #fecaca;background:#fff1f2}.attentionList span:before{content:"• ";font-weight:900}.clear{border:1px solid #bbf7d0;background:#f0fdf4;color:#166534}.empty{background:white;border:1px solid #cbd5e1;border-radius:15px;padding:18px}.empty b{font-size:22px}.empty p{color:#475569}@media(max-width:900px){.hero{display:grid}.kpis{grid-template-columns:repeat(3,1fr)}.task dl,.patient dl{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.pw{padding:6px}.hero h1{font-size:45px}.hero nav a{flex:1;text-align:center}.toolbar strong{width:100%;order:3}.kpis{grid-template-columns:repeat(2,1fr)}.integrity{display:grid}.task{grid-template-columns:1fr}.taskActions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.taskActions button{min-height:46px}.task dl,.patient dl{grid-template-columns:repeat(2,minmax(0,1fr))}.patient h3{font-size:25px}}
`;
