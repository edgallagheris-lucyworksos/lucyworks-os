"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { getSession } from "@/lib/session";

type Task = { id: number; title: string; description: string; urgency: string; status: string; ownerRole: string; patientName?: string | null; episodeRef?: string | null; sectionName?: string | null; roomName?: string | null; dueAt?: string | null; overdue: boolean; links: { episode?: string | null; patientRecord?: string | null } };
type Block = { blockRef: string; procedureName: string; areaName: string; startsAt: string; endsAt: string; riskLevel: string; leadStaffName?: string | null; conflictCount: number };
type Patient = { episodeRef: string; patientName: string; urgency: string; phase: string; ownerRole: string; currentAreaRef?: string | null; currentAreaName?: string | null; nextAction: string; scheduled: boolean; attention: string[]; taskCount: number; redTaskCount: number; overdueTaskCount: number; schedule: Block[] };
type Workspace = { generatedAt: string; summary: { activePatients: number; scheduledPatients: number; unscheduledPatients: number; unlinkedTasks: number }; patientFlow: Patient[]; tasks: Task[]; unlinkedTasks: Task[]; conflicts: Array<{ severity: string }>; consistency: { message: string } };
type View = "patients" | "attention" | "legacy";
type Action = "start" | "complete" | "block" | "return_to_queue";

function label(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()); }
function time(value?: string | null) { return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "Not recorded"; }
function clock(value: string) { return new Date(value).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }); }
function tone(value: string) { const v = value.toLowerCase(); return ["red", "blocked", "overdue", "emergency"].includes(v) ? "red" : ["amber", "urgent", "in_progress", "pending"].includes(v) ? "amber" : "green"; }

export function OperationalWorkspaceV16() {
  const [data, setData] = useState<Workspace | null>(null);
  const [date, setDate] = useState(() => localOperationalDate());
  const [view, setView] = useState<View>("patients");
  const [status, setStatus] = useState("Loading Patient Command");
  const [busy, setBusy] = useState<number | null>(null);
  const role = getSession()?.user.role || "unknown";

  const refresh = useCallback(async () => {
    try {
      const result = await apiGet<Workspace>(`/api/v14/operational-workspace?operational_date=${date}`);
      setData(result);
      setStatus(`Live · ${new Date(result.generatedAt).toLocaleTimeString("en-GB")}`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Patient Command unavailable"); }
  }, [date]);

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 15_000); return () => window.clearInterval(timer); }, [refresh]);

  async function act(item: Task, action: Action) {
    setBusy(item.id);
    try {
      await apiPost(`/api/v14/operational-workspace/work-items/${item.id}/action`, { action, expectedStatus: item.status, note: `${label(action)} from Patient Command` });
      await refresh();
    } catch (error) { setStatus(error instanceof Error ? error.message : "Action failed"); }
    finally { setBusy(null); }
  }

  const critical = useMemo(() => (data?.tasks || []).filter(item => item.urgency === "red" || item.overdue || item.status === "blocked"), [data]);
  const mine = useMemo(() => (data?.tasks || []).filter(item => critical.includes(item) || item.ownerRole === role).sort((a, b) => Number(b.overdue) - Number(a.overdue)), [critical, data, role]);
  const patients = useMemo(() => [...(data?.patientFlow || [])].sort((a, b) => b.attention.length - a.attention.length || a.patientName.localeCompare(b.patientName)), [data]);
  const redConflicts = (data?.conflicts || []).filter(item => item.severity === "red").length;

  if (!data) return <main className="pc loading"><style>{css}</style>{status}</main>;
  const visibleTasks = view === "legacy" ? data.unlinkedTasks : mine;

  return <main className="pc"><style>{css}</style>
    <header className="hero"><div><span>LUCYWORKS OS · PATIENT COMMAND V16</span><h1>Patient Command</h1><p>Every patient answers who, what, where, when and how. Detailed modules open only after the situation is clear.</p></div><nav><Link href="/referral-intake">New referral</Link><Link href="/input">Quick input</Link><Link href="/hospital-board">Hospital today</Link><Link href="/system-control">More tools</Link></nav></header>

    <section className="toolbar"><label>Operating date<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label><button onClick={() => setDate(localOperationalDate())}>Today</button><button onClick={() => void refresh()}>Refresh</button><strong aria-live="polite">{status}</strong></section>

    <section className="kpis"><article><b>{data.summary.activePatients}</b><small>active patients</small></article><article><b>{data.summary.scheduledPatients}</b><small>scheduled today</small></article><article className={data.summary.unscheduledPatients ? "amber" : "green"}><b>{data.summary.unscheduledPatients}</b><small>need a time/place</small></article><article className={critical.length + redConflicts ? "red" : "green"}><b>{critical.length + redConflicts}</b><small>critical now</small></article><article className={data.unlinkedTasks.length ? "amber" : "green"}><b>{data.unlinkedTasks.length}</b><small>legacy work unlinked</small></article></section>

    {data.unlinkedTasks.length ? <section className="integrity"><b>Legacy work is not live patient care.</b><span>{data.unlinkedTasks.length} item{data.unlinkedTasks.length === 1 ? "" : "s"} remain separate until a valid episode is linked.</span><button onClick={() => setView("legacy")}>Review</button></section> : null}

    <nav className="tabs"><button className={view === "patients" ? "active" : ""} onClick={() => setView("patients")}>Patients {patients.length}</button><button className={view === "attention" ? "active" : ""} onClick={() => setView("attention")}>My attention {mine.length}</button><button className={view === "legacy" ? "active" : ""} onClick={() => setView("legacy")}>Legacy {data.unlinkedTasks.length}</button></nav>

    {view === "patients" ? <section className="list"><div className="head"><div><span>WHO · WHAT · WHERE · WHEN · HOW</span><h2>Patient flow</h2></div><small>{patients.length} active</small></div>{patients.length ? patients.map(patient => {
      const nextBlock = patient.schedule[0];
      return <article className={`patient ${patient.attention.length ? "attention" : ""}`} key={patient.episodeRef}>
        <header><div><small>{patient.episodeRef}</small><h3>{patient.patientName}</h3><p>{label(patient.phase)} · {patient.urgency.toUpperCase()}</p></div><Link className="open" href={`/care?episode=${encodeURIComponent(patient.episodeRef)}`}>Open care brief →</Link></header>
        <section className="five"><div><dt>Who</dt><dd>{nextBlock?.leadStaffName || label(patient.ownerRole)}</dd></div><div><dt>What</dt><dd>{patient.nextAction}</dd></div><div><dt>Where</dt><dd>{patient.currentAreaName || patient.currentAreaRef || nextBlock?.areaName || "Not placed"}</dd></div><div><dt>When</dt><dd>{nextBlock ? `${clock(nextBlock.startsAt)}–${clock(nextBlock.endsAt)}` : "Not scheduled"}</dd></div><div><dt>How</dt><dd>{patient.attention.length ? `${patient.attention.length} control gap${patient.attention.length === 1 ? "" : "s"}` : "Recorded controls clear"}</dd></div></section>
        {patient.attention.length ? <div className="issues">{patient.attention.slice(0, 4).map(item => <span key={item}>{item}</span>)}</div> : null}
      </article>;
    }) : <article className="empty"><b>No canonical patients yet.</b><p>Create one synthetic referral, complete triage and accept it.</p><Link href="/referral-intake">Start synthetic referral</Link></article>}</section> : <section className="list"><div className="head"><div><span>{view === "legacy" ? "DATA QUALITY" : "OWNED ACTIONS"}</span><h2>{view === "legacy" ? "Unlinked legacy work" : "Do the next safe thing"}</h2></div><small>{visibleTasks.length}</small></div>{visibleTasks.length ? visibleTasks.map(item => <article className={`task ${tone(item.overdue ? "overdue" : item.urgency)}`} key={item.id}><div><header><b>{item.title}</b><span>{item.overdue ? "OVERDUE" : item.urgency.toUpperCase()}</span></header><p>{item.description || "No explanatory note"}</p><dl><div><dt>Who</dt><dd>{label(item.ownerRole)}</dd></div><div><dt>Where</dt><dd>{item.roomName || item.sectionName || "Not recorded"}</dd></div><div><dt>When</dt><dd>{time(item.dueAt)}</dd></div><div><dt>Patient</dt><dd>{item.patientName || "Not linked"}</dd></div></dl>{item.episodeRef ? <Link href={`/care?episode=${encodeURIComponent(item.episodeRef)}`}>Open care brief</Link> : <Link href="/referral-intake">Find or create episode</Link>}</div>{view !== "legacy" ? <aside>{item.status === "new" ? <button disabled={busy === item.id} onClick={() => void act(item, "start")}>Start</button> : null}{item.status === "in_progress" ? <button disabled={busy === item.id} onClick={() => void act(item, "complete")}>Complete</button> : null}{["new", "in_progress"].includes(item.status) ? <button disabled={busy === item.id} onClick={() => void act(item, "block")}>Block</button> : null}{item.status === "blocked" ? <button disabled={busy === item.id} onClick={() => void act(item, "return_to_queue")}>Return</button> : null}</aside> : null}</article>) : <article className="empty"><b>No work in this view.</b><p>Nothing currently requires action for the selected scope.</p></article>}</section>}
  </main>;
}

const css = `
.pc{min-height:100vh;background:#e9eef5;color:#0f172a;padding:8px;font-family:Inter,system-ui,sans-serif}.pc *{box-sizing:border-box}.loading{display:grid;place-items:center;background:#071019;color:white;font-weight:900}.hero{display:flex;justify-content:space-between;gap:16px;background:#071019;color:white;border-radius:18px;padding:18px}.hero span,.head span{color:#2dd4bf;font-size:11px;font-weight:950;letter-spacing:.13em}.hero h1{font-size:clamp(38px,7vw,70px);line-height:.92;margin:6px 0}.hero p{margin:0;color:#b6c2d1}.hero nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.hero a,.toolbar button,.integrity button,.tabs button,.task aside button{border:1px solid #334155;border-radius:999px;background:#0f172a;color:white;padding:10px 13px;text-decoration:none;font-weight:900}.toolbar{display:flex;gap:8px;align-items:end;flex-wrap:wrap;background:white;border:1px solid #cbd5e1;border-radius:13px;padding:9px;margin:9px 0}.toolbar label{display:grid;gap:3px;font-size:11px;font-weight:900;color:#475569}.toolbar input{min-height:43px;border:1px solid #94a3b8;border-radius:8px;padding:7px;font-size:16px}.toolbar strong{margin-left:auto;color:#475569}.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.kpis article,.patient,.task,.empty{background:white;border:1px solid #cbd5e1;border-radius:13px;padding:12px}.kpis article{border-top:5px solid #64748b}.kpis .red{border-top-color:#dc2626}.kpis .amber{border-top-color:#f59e0b}.kpis .green{border-top-color:#16a34a}.kpis b{display:block;font-size:28px}.kpis small{color:#64748b}.integrity{display:flex;gap:8px;align-items:center;background:#fffbeb;border:1px solid #f59e0b;border-radius:12px;padding:10px;margin-top:8px}.integrity span{flex:1;color:#92400e}.tabs{display:flex;gap:7px;overflow:auto;padding:10px 0}.tabs button{background:white;color:#0f172a;border-color:#cbd5e1;white-space:nowrap}.tabs .active{background:#0f172a;color:white}.list{display:grid;gap:9px}.head{display:flex;justify-content:space-between;align-items:end}.head h2{font-size:34px;margin:4px 0}.head small{font-weight:900;color:#64748b}.patient.attention,.task.red{border-left:7px solid #dc2626}.task.amber{border-left:7px solid #f59e0b}.patient>header,.task header{display:flex;justify-content:space-between;gap:8px}.patient h3{font-size:27px;margin:3px 0}.patient p,.task p{margin:0;color:#475569}.open{align-self:start;border-radius:999px;background:#0f172a;color:white;padding:10px 12px;text-decoration:none;font-weight:900}.five,.task dl{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-top:10px}.five div,.task dl div{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px}.five dt,.task dt{font-size:10px;font-weight:950;color:#64748b;text-transform:uppercase}.five dd,.task dd{margin:4px 0 0;font-weight:850;overflow-wrap:anywhere}.issues{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.issues span{background:#fff1f2;border:1px solid #fecaca;border-radius:999px;padding:6px 9px}.task{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px}.task header span{font-size:10px;font-weight:950}.task a,.empty a{color:#1d4ed8;font-weight:900}.task aside{display:flex;flex-direction:column;gap:6px;justify-content:center}@media(max-width:900px){.hero{display:grid}.kpis{grid-template-columns:repeat(2,1fr)}.five{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.pc{padding:5px}.hero nav a{flex:1;text-align:center}.toolbar strong{width:100%}.integrity{display:grid}.patient>header{display:grid}.five,.task dl{grid-template-columns:1fr 1fr}.task{grid-template-columns:1fr}.task aside{display:grid;grid-template-columns:repeat(2,1fr)}}
`;
