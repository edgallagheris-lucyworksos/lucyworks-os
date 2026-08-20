"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { getSession } from "@/lib/session";

type Task = { id: number; title: string; description: string; urgency: string; status: string; ownerRole: string; patientName?: string | null; episodeRef?: string | null; sectionName?: string | null; roomName?: string | null; dueAt?: string | null; overdue: boolean };
type Block = { blockRef: string; procedureName: string; areaName: string; startsAt: string; endsAt: string; riskLevel: string; leadStaffName?: string | null; conflictCount: number };
type Patient = { episodeRef: string; patientName: string; urgency: string; phase: string; ownerRole: string; currentAreaRef?: string | null; currentAreaName?: string | null; nextAction: string; scheduled: boolean; attention: string[]; taskCount: number; redTaskCount: number; overdueTaskCount: number; schedule: Block[] };
type Workspace = { generatedAt: string; summary: { activePatients: number; scheduledPatients: number; unscheduledPatients: number; unlinkedTasks: number }; patientFlow: Patient[]; tasks: Task[]; unlinkedTasks: Task[]; conflicts: Array<{ severity: string }> };
type View = "patients" | "attention" | "data_quality";
type Action = "start" | "complete" | "block" | "return_to_queue";

function label(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()); }
function time(value?: string | null) { return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "Not recorded"; }
function clock(value: string) { return new Date(value).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }); }
function tone(value: string) { const v = value.toLowerCase(); return ["red", "blocked", "overdue", "emergency", "failed"].includes(v) ? "red" : ["amber", "urgent", "in_progress", "pending", "queued"].includes(v) ? "amber" : "green"; }

export function OperationalWorkspaceV16() {
  const [data, setData] = useState<Workspace | null>(null);
  const [date, setDate] = useState(() => localOperationalDate());
  const [view, setView] = useState<View>("patients");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Loading patient workspace");
  const [busy, setBusy] = useState<number | null>(null);
  const role = getSession()?.user.role || "unknown";

  const refresh = useCallback(async () => {
    try {
      const result = await apiGet<Workspace>(`/api/v14/operational-workspace?operational_date=${date}`);
      setData(result);
      setStatus(`Updated ${new Date(result.generatedAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Patient workspace unavailable");
    }
  }, [date]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function act(item: Task, action: Action) {
    setBusy(item.id);
    try {
      await apiPost(`/api/v14/operational-workspace/work-items/${item.id}/action`, { action, expectedStatus: item.status, note: `${label(action)} from patient workspace` });
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  const critical = useMemo(() => (data?.tasks || []).filter(item => item.urgency === "red" || item.overdue || item.status === "blocked"), [data]);
  const mine = useMemo(() => (data?.tasks || []).filter(item => critical.includes(item) || item.ownerRole === role).sort((a, b) => Number(b.overdue) - Number(a.overdue)), [critical, data, role]);
  const patients = useMemo(() => {
    const term = query.trim().toLowerCase();
    return [...(data?.patientFlow || [])]
      .filter(patient => !term || [patient.patientName, patient.episodeRef, patient.phase, patient.ownerRole, patient.nextAction].some(value => value?.toLowerCase().includes(term)))
      .sort((a, b) => b.attention.length - a.attention.length || a.patientName.localeCompare(b.patientName));
  }, [data, query]);
  const redConflicts = (data?.conflicts || []).filter(item => item.severity === "red").length;
  const visibleTasks = view === "data_quality" ? data?.unlinkedTasks || [] : mine;

  if (!data) return <main className="pw loading"><style>{css}</style>{status}</main>;

  return <main className="pw"><style>{css}</style>
    <section className="pw-toolbar">
      <div className="pw-search"><span aria-hidden="true">⌕</span><input aria-label="Find patient" placeholder="Find patient, episode or next action" value={query} onChange={event => setQuery(event.target.value)} /></div>
      <label>Date<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label>
      <button onClick={() => setDate(localOperationalDate())}>Today</button>
      <button onClick={() => void refresh()}>Refresh</button>
      <strong aria-live="polite">{status}</strong>
    </section>

    <section className="pw-kpis">
      <article><span>Active patients</span><strong>{data.summary.activePatients}</strong></article>
      <article><span>Scheduled today</span><strong>{data.summary.scheduledPatients}</strong></article>
      <article className={data.summary.unscheduledPatients ? "amber" : "green"}><span>Need time / place</span><strong>{data.summary.unscheduledPatients}</strong></article>
      <article className={critical.length + redConflicts ? "red" : "green"}><span>Critical attention</span><strong>{critical.length + redConflicts}</strong></article>
    </section>

    {data.unlinkedTasks.length ? <section className="pw-integrity"><div><strong>Unlinked work needs review</strong><span>{data.unlinkedTasks.length} item{data.unlinkedTasks.length === 1 ? "" : "s"} cannot be treated as live patient care until linked to an episode.</span></div><button onClick={() => setView("data_quality")}>Review</button></section> : null}

    <nav className="pw-tabs" aria-label="Patient workspace views">
      <button className={view === "patients" ? "active" : ""} onClick={() => setView("patients")}>Patients <span>{patients.length}</span></button>
      <button className={view === "attention" ? "active" : ""} onClick={() => setView("attention")}>My attention <span>{mine.length}</span></button>
      <button className={view === "data_quality" ? "active" : ""} onClick={() => setView("data_quality")}>Data quality <span>{data.unlinkedTasks.length}</span></button>
    </nav>

    {view === "patients" ? <section className="pw-list">
      <header><div><span>Patient flow</span><h2>Active patients</h2></div><small>{patients.length} shown</small></header>
      {patients.length ? patients.map(patient => {
        const nextBlock = patient.schedule[0];
        return <article className={`pw-patient ${patient.attention.length ? "attention" : ""}`} key={patient.episodeRef}>
          <header><div><h3>{patient.patientName}</h3><span>{label(patient.phase)} · {patient.urgency.toUpperCase()}</span></div><Link href={`/episode-command?episode=${encodeURIComponent(patient.episodeRef)}`}>Open episode</Link></header>
          <div className="pw-five"><div><span>Who</span><strong>{nextBlock?.leadStaffName || label(patient.ownerRole)}</strong></div><div><span>What</span><strong>{patient.nextAction}</strong></div><div><span>Where</span><strong>{patient.currentAreaName || patient.currentAreaRef || nextBlock?.areaName || "Not placed"}</strong></div><div><span>When</span><strong>{nextBlock ? `${clock(nextBlock.startsAt)}–${clock(nextBlock.endsAt)}` : "Not scheduled"}</strong></div><div><span>Controls</span><strong>{patient.attention.length ? `${patient.attention.length} to resolve` : "Clear"}</strong></div></div>
          {patient.attention.length ? <div className="pw-issues">{patient.attention.slice(0, 4).map(item => <span key={item}>{item}</span>)}</div> : null}
        </article>;
      }) : <div className="pw-empty">No active patients match this view.</div>}
    </section> : <section className="pw-list">
      <header><div><span>{view === "data_quality" ? "Data quality" : "Owned actions"}</span><h2>{view === "data_quality" ? "Unlinked work" : "Next safe actions"}</h2></div><small>{visibleTasks.length}</small></header>
      {visibleTasks.length ? visibleTasks.map(item => <article className={`pw-task ${tone(item.overdue ? "overdue" : item.urgency)}`} key={item.id}>
        <div><header><strong>{item.title}</strong><span>{item.overdue ? "Overdue" : label(item.urgency)}</span></header><p>{item.description || "No additional note"}</p><dl><div><dt>Owner</dt><dd>{label(item.ownerRole)}</dd></div><div><dt>Location</dt><dd>{item.roomName || item.sectionName || "Not recorded"}</dd></div><div><dt>Due</dt><dd>{time(item.dueAt)}</dd></div><div><dt>Patient</dt><dd>{item.patientName || "Not linked"}</dd></div></dl>{item.episodeRef ? <Link href={`/episode-command?episode=${encodeURIComponent(item.episodeRef)}`}>Open episode</Link> : <Link href="/referral-intake">Find or create patient</Link>}</div>
        {view !== "data_quality" ? <aside>{item.status === "new" ? <button disabled={busy === item.id} onClick={() => void act(item, "start")}>Start</button> : null}{item.status === "in_progress" ? <button disabled={busy === item.id} onClick={() => void act(item, "complete")}>Complete</button> : null}{["new", "in_progress"].includes(item.status) ? <button className="warn" disabled={busy === item.id} onClick={() => void act(item, "block")}>Block</button> : null}{item.status === "blocked" ? <button disabled={busy === item.id} onClick={() => void act(item, "return_to_queue")}>Return</button> : null}</aside> : null}
      </article>) : <div className="pw-empty">No work currently requires action in this view.</div>}
    </section>}
  </main>;
}

const css = `
.pw{display:grid;gap:10px;min-height:100vh;background:#eef2f7;color:#172033;padding:12px 18px 28px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.pw *{box-sizing:border-box}.pw.loading{place-items:center;min-height:60vh;color:#64748b;font-size:12px;font-weight:800}.pw-toolbar{display:grid;grid-template-columns:minmax(250px,1fr) 150px auto auto minmax(130px,auto);gap:8px;align-items:end;padding:9px 10px;background:#fff;border:1px solid #d9e1e9;border-radius:10px}.pw-toolbar label{display:grid;gap:3px;color:#69798c;font-size:9px;font-weight:800;text-transform:uppercase}.pw-toolbar input{min-height:38px;height:38px;border:1px solid #c4cfda;border-radius:7px;background:#fff;color:#172033;padding:0 9px;font-size:12px}.pw-search{position:relative}.pw-search span{position:absolute;left:10px;top:6px;color:#77869a;font-size:18px}.pw-search input{width:100%;padding-left:34px}.pw-toolbar button,.pw-integrity button,.pw-tabs button,.pw-task aside button{min-height:38px;border:1px solid #c8d2dc;border-radius:7px;background:#fff;color:#294761;padding:0 11px;font-size:10px;font-weight:800}.pw-toolbar strong{align-self:center;color:#7a8798;font-size:9px;font-weight:700;text-align:right}.pw-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.pw-kpis article{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 12px;background:#fff;border:1px solid #d9e1e9;border-left:4px solid #52738d;border-radius:9px}.pw-kpis article.green{border-left-color:#2d8061}.pw-kpis article.amber{border-left-color:#c27a16}.pw-kpis article.red{border-left-color:#b9403a}.pw-kpis span{color:#68788b;font-size:10px;font-weight:700}.pw-kpis strong{color:#17334d;font-size:20px}.pw-integrity{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 11px;background:#fff9ef;border:1px solid #ebc88d;border-radius:9px}.pw-integrity>div{display:grid;gap:2px}.pw-integrity strong{font-size:11px;color:#744b12}.pw-integrity span{font-size:9px;color:#8b6734}.pw-tabs{display:flex;gap:6px;overflow:auto}.pw-tabs button{display:flex;align-items:center;gap:6px;white-space:nowrap}.pw-tabs button span{display:grid;place-items:center;min-width:18px;height:18px;padding:0 4px;border-radius:99px;background:#edf2f6;color:#50657a;font-size:8px}.pw-tabs button.active{border-color:#173f5f;background:#173f5f;color:#fff}.pw-tabs button.active span{background:rgba(255,255,255,.16);color:#fff}.pw-list{display:grid;gap:8px}.pw-list>header{display:flex;justify-content:space-between;align-items:end;padding:2px}.pw-list>header span{color:#6c7b8e;font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.1em}.pw-list>header h2{margin:2px 0 0;color:#1a3146;font-size:18px}.pw-list>header small{color:#7b8898;font-size:9px}.pw-patient,.pw-task{background:#fff;border:1px solid #d9e1e9;border-radius:10px;overflow:hidden}.pw-patient.attention{border-left:4px solid #b9403a}.pw-patient>header{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid #edf0f3}.pw-patient>header>div{display:grid;gap:2px}.pw-patient h3{margin:0;color:#1b3247;font-size:16px}.pw-patient>header span{color:#6b7b8d;font-size:9px}.pw-patient>header a,.pw-task a{padding:6px 8px;border-radius:7px;background:#edf3f7;color:#294b65;text-decoration:none;font-size:9px;font-weight:800;white-space:nowrap}.pw-five{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:#edf0f3}.pw-five>div{display:grid;gap:3px;padding:9px 10px;background:#fff}.pw-five span{color:#788596;font-size:8px;font-weight:800;text-transform:uppercase}.pw-five strong{font-size:10px;overflow-wrap:anywhere}.pw-issues{display:flex;gap:5px;flex-wrap:wrap;padding:8px 10px;border-top:1px solid #f1d6d3;background:#fff9f8}.pw-issues span{padding:4px 6px;border-radius:99px;background:#fbe8e6;color:#8f3832;font-size:8px;font-weight:750}.pw-task{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:11px 12px;border-left:4px solid #2d8061}.pw-task.red{border-left-color:#b9403a}.pw-task.amber{border-left-color:#c27a16}.pw-task>div>header{display:flex;justify-content:space-between;gap:8px}.pw-task>div>header strong{font-size:12px}.pw-task>div>header span{font-size:8px;font-weight:850;text-transform:uppercase;color:#6e7d8f}.pw-task p{margin:5px 0;color:#637387;font-size:10px}.pw-task dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:8px 0}.pw-task dl>div{display:grid;gap:2px;padding:6px 7px;background:#f7f9fb;border-radius:6px}.pw-task dt{color:#7c8999;font-size:7px;font-weight:800;text-transform:uppercase}.pw-task dd{margin:0;font-size:9px;font-weight:700}.pw-task aside{display:flex;flex-direction:column;justify-content:center;gap:5px}.pw-task aside button.warn{color:#89530e;background:#fff8ec;border-color:#e8c18a}.pw-empty{padding:22px;background:#fff;border:1px solid #d9e1e9;border-radius:10px;color:#6d7c8e;text-align:center;font-size:10px}
@media(max-width:900px){.pw-toolbar{grid-template-columns:1fr 145px auto auto}.pw-toolbar strong{grid-column:1/-1;text-align:left}.pw-five{grid-template-columns:repeat(3,1fr)}.pw-task dl{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.pw{padding:8px}.pw-toolbar{grid-template-columns:1fr 1fr}.pw-search{grid-column:1/-1}.pw-toolbar strong{grid-column:1/-1}.pw-kpis{grid-template-columns:1fr 1fr}.pw-kpis article{display:grid;gap:2px}.pw-five{grid-template-columns:1fr 1fr}.pw-patient>header{align-items:flex-start}.pw-task{grid-template-columns:1fr}.pw-task aside{flex-direction:row;justify-content:flex-start;flex-wrap:wrap}.pw-integrity{align-items:flex-start}}
`;
