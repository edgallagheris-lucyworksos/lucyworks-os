"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { getSession } from "@/lib/session";

type WorkItem = {
  id: number;
  title: string;
  description: string;
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
  conflictCount: number;
};

type PatientFlow = {
  episodeRef: string;
  patientName: string;
  urgency: string;
  phase: string;
  ownerRole: string;
  currentAreaRef?: string | null;
  currentAreaName?: string | null;
  nextAction: string;
  scheduled: boolean;
  attention: string[];
  taskCount: number;
  redTaskCount: number;
  overdueTaskCount: number;
  schedule: ScheduleItem[];
  links: { episode: string; patientRecord: string; clinicalExecution: string };
};

type Workspace = {
  generatedAt: string;
  operationalDate: string;
  requestedBy: { name: string; role: string };
  summary: {
    activePatients: number;
    scheduledPatients: number;
    unscheduledPatients: number;
    boardBlocks: number;
    unlinkedTasks: number;
  };
  patientFlow: PatientFlow[];
  tasks: WorkItem[];
  unlinkedTasks: WorkItem[];
  conflicts: Array<{ severity: string; explanation: string }>;
  consistency: { message: string };
};

type View = "patients" | "attention" | "unlinked";
type Action = "start" | "complete" | "block" | "return_to_queue";

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function clock(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function deadline(value?: string | null) {
  if (!value) return "No deadline recorded";
  return new Date(value).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "blocked", "overdue", "emergency"].includes(normal)) return "red";
  if (["amber", "urgent", "in_progress", "pending"].includes(normal)) return "amber";
  return "green";
}

export function OperationalWorkspaceV15() {
  const [data, setData] = useState<Workspace | null>(null);
  const [operationalDate, setOperationalDate] = useState(() => localOperationalDate());
  const [view, setView] = useState<View>("patients");
  const [status, setStatus] = useState("Loading patient command");
  const [busyId, setBusyId] = useState<number | null>(null);
  const role = getSession()?.user.role || "unknown";

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
    const timer = window.setInterval(() => void refresh(), 15_000);
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [refresh]);

  async function act(item: WorkItem, action: Action) {
    setBusyId(item.id);
    setStatus(`${label(action)}: ${item.title}`);
    try {
      await apiPost(`/api/v14/operational-workspace/work-items/${item.id}/action`, {
        action,
        expectedStatus: item.status,
        note: `${label(action)} from patient command`,
      });
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  const criticalTasks = useMemo(() => (data?.tasks || []).filter(item => item.urgency === "red" || item.overdue || item.status === "blocked"), [data]);
  const attentionTasks = useMemo(() => {
    const rows = (data?.tasks || []).filter(item => criticalTasks.includes(item) || item.ownerRole === role);
    return rows.sort((a, b) => Number(b.overdue) - Number(a.overdue) || Number(b.urgency === "red") - Number(a.urgency === "red"));
  }, [criticalTasks, data, role]);
  const sortedPatients = useMemo(() => [...(data?.patientFlow || [])].sort((a, b) => b.attention.length - a.attention.length || b.redTaskCount - a.redTaskCount || a.patientName.localeCompare(b.patientName)), [data]);
  const redConflicts = useMemo(() => (data?.conflicts || []).filter(item => item.severity === "red").length, [data]);
  const criticalNow = criticalTasks.length + redConflicts;
  const overdueNow = (data?.tasks || []).filter(item => item.overdue).length;

  if (!data) return <main className="pc loading"><style>{css}</style>{status}</main>;

  const visibleTasks = view === "unlinked" ? data.unlinkedTasks : attentionTasks;

  return <main className="pc">
    <style>{css}</style>
    <header className="hero">
      <div><span>LucyWorks OS · patient command v15</span><h1>Patient command</h1><p>One live view of each patient, their next safe action, owner, place, deadline and evidence gates.</p></div>
      <nav><Link href="/referral-intake">New referral</Link><Link href="/input">Quick input</Link><Link href="/hospital-board">Hospital board</Link><Link href="/system-control">System control</Link></nav>
    </header>

    <section className="toolbar">
      <label>Operating date<input type="date" value={operationalDate} onChange={event => setOperationalDate(event.target.value)} /></label>
      <button onClick={() => setOperationalDate(localOperationalDate())}>Today</button>
      <button onClick={() => void refresh()}>Refresh</button>
      <strong aria-live="polite">{status}</strong>
    </section>

    <section className="kpis">
      <article><b>{data.summary.activePatients}</b><small>active patients</small></article>
      <article><b>{data.summary.scheduledPatients}</b><small>scheduled today</small></article>
      <article className={data.summary.unscheduledPatients ? "amber" : "green"}><b>{data.summary.unscheduledPatients}</b><small>need scheduling</small></article>
      <article className={criticalNow ? "red" : "green"}><b>{criticalNow}</b><small>critical now</small></article>
      <article className={overdueNow ? "red" : "green"}><b>{overdueNow}</b><small>overdue linked tasks</small></article>
      <article className={data.unlinkedTasks.length ? "amber" : "green"}><b>{data.unlinkedTasks.length}</b><small>legacy tasks unlinked</small></article>
    </section>

    {data.unlinkedTasks.length ? <section className="integrity amber"><div><b>Legacy work is separated</b><p>{data.unlinkedTasks.length} old or manually captured task{data.unlinkedTasks.length === 1 ? " is" : "s are"} not counted as live patient care until linked to a canonical episode.</p></div><button onClick={() => setView("unlinked")}>Review legacy work</button></section> : <section className="integrity green"><div><b>One operational truth</b><p>{data.consistency.message}</p></div></section>}

    <nav className="tabs" aria-label="Patient command views">
      <button className={view === "patients" ? "active" : ""} onClick={() => setView("patients")}>Patients <span>{data.patientFlow.length}</span></button>
      <button className={view === "attention" ? "active" : ""} onClick={() => setView("attention")}>My attention <span>{attentionTasks.length}</span></button>
      <button className={view === "unlinked" ? "active" : ""} onClick={() => setView("unlinked")}>Unlinked legacy <span>{data.unlinkedTasks.length}</span></button>
    </nav>

    {view === "patients" ? <section className="patients">
      <div className="sectionHead"><div><span>CONTINUITY OF CARE</span><h2>Every patient and the next safe action</h2></div><small>{sortedPatients.length} active</small></div>
      {sortedPatients.length ? sortedPatients.map(patient => <article className={`patient ${patient.attention.length ? "attention" : ""}`} key={patient.episodeRef}>
        <header><div><span>{patient.episodeRef}</span><h3>{patient.patientName}</h3><p>{label(patient.phase)} · owner {label(patient.ownerRole)}</p></div><span className={`pill ${tone(patient.urgency)}`}>{patient.urgency.toUpperCase()}</span></header>
        <section className="next"><small>NEXT SAFE ACTION</small><b>{patient.nextAction}</b></section>
        <dl><div><dt>Area</dt><dd>{patient.currentAreaName || patient.currentAreaRef || "Not placed"}</dd></div><div><dt>Schedule</dt><dd>{patient.scheduled ? `${patient.schedule.length} block${patient.schedule.length === 1 ? "" : "s"}` : "Not scheduled"}</dd></div><div><dt>Tasks</dt><dd>{patient.taskCount}</dd></div><div><dt>Safety gaps</dt><dd>{patient.attention.length}</dd></div></dl>
        {patient.schedule.length ? <div className="schedule">{patient.schedule.map(block => <div className={tone(block.riskLevel)} key={block.blockRef}><time>{clock(block.startsAt)}–{clock(block.endsAt)}</time><b>{block.procedureName}</b><span>{block.areaName}</span><small>{block.leadStaffName || "Lead not assigned"}{block.conflictCount ? ` · ${block.conflictCount} conflict` : ""}</small></div>)}</div> : <div className="unscheduled"><b>No care block today.</b><span>The patient is accepted but has no governed room, staff and time allocation.</span><Link href="/hospital-board">Schedule on board</Link></div>}
        {patient.attention.length ? <div className="issues"><b>Resolve or acknowledge</b>{patient.attention.slice(0, 6).map(item => <span key={item}>{item}</span>)}</div> : <div className="clear"><b>No current red or overdue evidence gaps.</b></div>}
        <footer><Link href={patient.links.episode}>Episode command</Link><Link href={patient.links.patientRecord}>Patient record</Link><Link href={patient.links.clinicalExecution}>Clinical execution</Link></footer>
      </article>) : <article className="onboarding"><span>SAFE TEST FLOW</span><h3>No canonical patients yet</h3><p>The ten visible legacy tasks are deliberately excluded. Create one synthetic referral, complete triage, accept it and confirm its proposed block appears on the board.</p><ol><li>Create a referral using a clearly synthetic patient.</li><li>Acknowledge and complete clinical triage.</li><li>Accept the referral and open the hospital board.</li></ol><Link href="/referral-intake">Start synthetic referral →</Link></article>}
    </section> : <section className="tasks">
      <div className="sectionHead"><div><span>{view === "unlinked" ? "DATA QUALITY" : "ACTION QUEUE"}</span><h2>{view === "unlinked" ? "Legacy work awaiting patient linkage" : "Do the next safe thing"}</h2></div><small>{visibleTasks.length} item{visibleTasks.length === 1 ? "" : "s"}</small></div>
      {visibleTasks.length ? visibleTasks.map(item => <article className={`task ${tone(item.overdue ? "overdue" : item.urgency)}`} key={item.id}>
        <div><div className="meta"><span className={`pill ${tone(item.urgency)}`}>{item.overdue ? "OVERDUE" : item.urgency.toUpperCase()}</span><span>{label(item.status)}</span><span>{label(item.ownerRole)}</span></div><h3>{item.title}</h3><p>{item.description || "No explanatory note recorded."}</p><dl><div><dt>Patient</dt><dd>{item.patientName || "Not linked"}</dd></div><div><dt>Episode</dt><dd>{item.episodeRef || "Not linked"}</dd></div><div><dt>Area</dt><dd>{item.roomName || item.sectionName || "Not recorded"}</dd></div><div><dt>Due</dt><dd>{deadline(item.dueAt)}</dd></div></dl><footer>{item.links.episode ? <Link href={item.links.episode}>Open episode</Link> : <Link href="/referral-intake">Find or create episode</Link>}{item.links.patientRecord ? <Link href={item.links.patientRecord}>Patient record</Link> : null}</footer></div>
        {view !== "unlinked" ? <aside>{item.status === "new" ? <button disabled={busyId === item.id} onClick={() => void act(item, "start")}>Start</button> : null}{item.status === "in_progress" ? <button disabled={busyId === item.id} onClick={() => void act(item, "complete")}>Complete</button> : null}{["new", "in_progress"].includes(item.status) ? <button className="secondary" disabled={busyId === item.id} onClick={() => void act(item, "block")}>Block</button> : null}{item.status === "blocked" ? <button disabled={busyId === item.id} onClick={() => void act(item, "return_to_queue")}>Return</button> : null}{item.status === "blocked" ? <button className="secondary" disabled={busyId === item.id} onClick={() => void act(item, "complete")}>Resolve</button> : null}</aside> : null}
      </article>) : <article className="empty"><b>No work in this view.</b><p>Patient care is clear for the selected scope and date.</p></article>}
    </section>}
  </main>;
}

const css = `
.pc{min-height:100vh;background:#e9eef5;color:#0f172a;padding:10px;font-family:Inter,system-ui,sans-serif}.pc *{box-sizing:border-box}.pc.loading{display:grid;place-items:center;background:#071019;color:white;font-weight:900}.hero{display:flex;justify-content:space-between;gap:16px;background:#071019;color:white;border-radius:18px;padding:18px}.hero>div{max-width:790px}.hero>div>span,.sectionHead span,.onboarding>span{color:#2dd4bf;font-size:11px;font-weight:950;letter-spacing:.13em}.hero h1{font-size:clamp(38px,7vw,72px);line-height:.92;margin:7px 0}.hero p{margin:0;color:#b6c2d1}.hero nav{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}.hero a,.toolbar button,.integrity button,.task aside button{border:1px solid #334155;border-radius:999px;padding:10px 13px;background:#0f172a;color:white;text-decoration:none;font-weight:900}.toolbar{display:flex;gap:8px;align-items:end;flex-wrap:wrap;background:white;border:1px solid #cbd5e1;border-radius:14px;padding:10px;margin:10px 0}.toolbar label{display:grid;gap:3px;color:#475569;font-size:11px;font-weight:900}.toolbar input{min-height:43px;border:1px solid #94a3b8;border-radius:9px;padding:7px;font-size:16px}.toolbar strong{margin-left:auto;color:#475569}.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.kpis article{background:white;border:1px solid #cbd5e1;border-top:5px solid #64748b;border-radius:13px;padding:11px}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{display:block;font-size:29px}.kpis small{color:#64748b}.integrity{display:flex;justify-content:space-between;align-items:center;gap:10px;background:white;border:1px solid #cbd5e1;border-left:7px solid #16a34a;border-radius:13px;padding:11px;margin-top:9px}.integrity.amber{border-left-color:#f59e0b}.integrity p{margin:3px 0;color:#475569}.tabs{display:flex;gap:7px;overflow:auto;padding:11px 0}.tabs button{flex:0 0 auto;border:1px solid #cbd5e1;border-radius:999px;background:white;padding:10px 13px;font-weight:900}.tabs button.active{background:#0f172a;color:white}.tabs span{display:inline-grid;place-items:center;min-width:22px;height:22px;margin-left:4px;border-radius:999px;background:#e2e8f0;color:#0f172a}.patients,.tasks{display:grid;gap:10px}.sectionHead{display:flex;justify-content:space-between;align-items:end;gap:8px}.sectionHead h2{font-size:clamp(27px,5vw,42px);line-height:1;margin:4px 0}.sectionHead small{color:#64748b;font-weight:900}.patient,.task,.onboarding,.empty{background:white;border:1px solid #cbd5e1;border-radius:15px;padding:14px}.patient.attention{border-left:7px solid #dc2626}.patient>header{display:flex;justify-content:space-between;gap:9px}.patient header>div>span{font-size:11px;color:#64748b;font-weight:900}.patient h3,.task h3,.onboarding h3{font-size:26px;margin:3px 0}.patient header p,.task p,.onboarding p,.empty p{margin:0;color:#475569}.pill{display:inline-flex;height:max-content;border-radius:999px;padding:5px 8px;background:#dcfce7;color:#166534;font-size:10px;font-weight:950}.pill.red{background:#fee2e2;color:#991b1b}.pill.amber{background:#fef3c7;color:#92400e}.next{display:grid;gap:3px;background:#071019;color:white;border-radius:10px;padding:11px;margin-top:11px}.next small{color:#2dd4bf;font-weight:950}.patient dl,.task dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:10px 0}.patient dl div,.task dl div{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:7px}.patient dt,.task dt{font-size:9px;font-weight:950;color:#64748b;text-transform:uppercase}.patient dd,.task dd{margin:3px 0 0;font-weight:850;overflow-wrap:anywhere}.schedule{display:flex;gap:7px;overflow:auto;padding-bottom:8px}.schedule>div{display:grid;gap:2px;min-width:190px;border:1px solid #cbd5e1;border-left:6px solid #16a34a;border-radius:9px;padding:8px;background:#f8fafc}.schedule>div.red{border-left-color:#dc2626}.schedule>div.amber{border-left-color:#f59e0b}.schedule time{font-weight:950}.schedule span,.schedule small{color:#64748b}.unscheduled{display:flex;gap:8px;align-items:center;flex-wrap:wrap;border:1px solid #f59e0b;background:#fffbeb;border-radius:9px;padding:9px}.issues,.clear{display:grid;gap:4px;border-radius:9px;padding:9px;margin:4px 0 10px}.issues{border:1px solid #fecaca;background:#fff1f2}.issues span:before{content:"• ";font-weight:900}.clear{border:1px solid #bbf7d0;background:#f0fdf4;color:#166534}.patient footer,.task footer{display:flex;gap:12px;flex-wrap:wrap}.patient footer a,.task footer a,.unscheduled a,.onboarding a{color:#1d4ed8;font-weight:900}.onboarding ol{padding-left:20px;color:#334155}.task{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;border-left:7px solid #16a34a}.task.red{border-left-color:#dc2626}.task.amber{border-left-color:#f59e0b}.meta{display:flex;gap:7px;align-items:center;flex-wrap:wrap;color:#64748b;font-size:12px;font-weight:850}.task aside{display:flex;flex-direction:column;gap:7px;justify-content:center;min-width:120px}.task aside .secondary{background:white;color:#0f172a;border-color:#94a3b8}.task aside button:disabled{opacity:.45}@media(max-width:900px){.hero{display:grid}.kpis{grid-template-columns:repeat(3,1fr)}.patient dl,.task dl{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.pc{padding:6px}.hero h1{font-size:44px}.hero nav a{flex:1;text-align:center}.toolbar strong{width:100%;order:4}.kpis{grid-template-columns:repeat(2,1fr)}.integrity{display:grid}.task{grid-template-columns:1fr}.task aside{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.task aside button{min-height:46px}.patient dl,.task dl{grid-template-columns:repeat(2,minmax(0,1fr))}}
`;
