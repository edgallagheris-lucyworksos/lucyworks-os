"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type Brief = {
  generatedAt: string;
  episodeRef: string;
  patientName: string;
  patientRef?: string | null;
  status: string;
  urgency: string;
  phase: string;
  serviceLine: string;
  recordedControlsReady: boolean;
  who: { accountableRole: string; accountableSubject?: string | null; leadName?: string | null; leadRole?: string | null };
  what: { currentPhase: string; currentOrNextProcedure?: string | null; nextAction: string };
  where: { areaRef?: string | null; areaName?: string | null };
  when: { startsAt?: string | null; endsAt?: string | null; nextDeadline?: { title: string; dueAt?: string | null; ownerRole: string; overdue: boolean } | null };
  how: { gateGaps: string[]; blockers: string[]; openTaskCount: number; criticalTaskCount: number; openConflictCount: number; attention: string[] };
  why: { urgency: string; flags: string[]; conflicts: Array<{ severity: string; explanation: string }> };
  schedule: Array<{ blockRef: string; procedureName: string; areaName: string; startsAt: string; endsAt: string; status: string; riskLevel: string; leadStaffName?: string | null }>;
  tasks: Array<{ id: number; title: string; description: string; urgency: string; status: string; ownerRole: string; area?: string | null; dueAt?: string | null; overdue: boolean }>;
  links: { patientCommand: string; hospitalBoard: string; episodeCommand: string; patientRecord: string; clinicalExecution: string };
  clinicalBoundary: string;
};

function label(value?: string | null) {
  if (!value) return "Not recorded";
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function when(value?: string | null) {
  return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "Not scheduled";
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "blocked", "overdue", "emergency"].includes(normal)) return "red";
  if (["amber", "urgent", "pending", "in_progress"].includes(normal)) return "amber";
  return "green";
}

export function CareBriefV16() {
  const params = useSearchParams();
  const [episodeRef, setEpisodeRef] = useState(params.get("episode") || "");
  const [data, setData] = useState<Brief | null>(null);
  const [status, setStatus] = useState("Enter or open an episode");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (value = episodeRef) => {
    const ref = value.trim();
    if (!ref) return;
    setBusy(true);
    setStatus("Loading care brief");
    try {
      const result = await apiGet<Brief>(`/api/v16/care-brief/${encodeURIComponent(ref)}`);
      setData(result);
      setEpisodeRef(result.episodeRef);
      setStatus(`Live · updated ${new Date(result.generatedAt).toLocaleTimeString("en-GB")}`);
    } catch (error) {
      setData(null);
      setStatus(error instanceof Error ? error.message : "Care brief unavailable");
    } finally {
      setBusy(false);
    }
  }, [episodeRef]);

  useEffect(() => {
    const initial = params.get("episode");
    if (initial) void load(initial);
  }, [load, params]);

  return <main className="cb">
    <style>{css}</style>
    <header className="hero">
      <div><span>LUCYWORKS OS · CARE BRIEF V16</span><h1>Care brief</h1><p>One screen answers who, what, where, when and how before staff open detailed controls.</p></div>
      <nav><Link href="/workspace">Patients</Link><Link href="/hospital-board">Hospital today</Link><Link href="/referral-intake">New referral</Link><Link href="/input">Quick input</Link></nav>
    </header>

    <section className="finder"><label>Episode reference<input value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} placeholder="EP-..." /></label><button disabled={busy || !episodeRef.trim()} onClick={() => void load()}>{busy ? "Loading…" : "Open care brief"}</button><strong aria-live="polite">{status}</strong></section>

    {!data ? <section className="empty"><b>No patient selected.</b><p>Open a patient from Patient Command or enter the episode reference above.</p><Link href="/workspace">Open Patient Command</Link></section> : <>
      <section className={`identity ${data.recordedControlsReady ? "green" : "amber"}`}>
        <div><small>{data.episodeRef}</small><h2>{data.patientName}</h2><p>{label(data.serviceLine)} · {label(data.phase)} · {data.urgency.toUpperCase()}</p></div>
        <div><b>{data.recordedControlsReady ? "Recorded controls clear" : "Recorded controls need attention"}</b><small>{data.clinicalBoundary}</small></div>
      </section>

      <section className="five">
        <article><span>WHO</span><h3>{data.who.leadName || label(data.who.accountableRole)}</h3><p>{data.who.leadName ? `${label(data.who.leadRole)} · accountable ${label(data.who.accountableRole)}` : `Accountable role: ${label(data.who.accountableRole)}`}</p></article>
        <article><span>WHAT</span><h3>{data.what.nextAction}</h3><p>{data.what.currentOrNextProcedure || label(data.what.currentPhase)}</p></article>
        <article><span>WHERE</span><h3>{data.where.areaName || label(data.where.areaRef)}</h3><p>{data.where.areaRef ? `Area reference ${data.where.areaRef}` : "No governed location recorded"}</p></article>
        <article><span>WHEN</span><h3>{when(data.when.startsAt)}</h3><p>{data.when.endsAt ? `Expected until ${when(data.when.endsAt)}` : data.when.nextDeadline ? `Next deadline: ${data.when.nextDeadline.title} · ${when(data.when.nextDeadline.dueAt)}` : "No time or deadline recorded"}</p></article>
        <article><span>HOW</span><h3>{data.recordedControlsReady ? "Proceed through the recorded next step" : "Resolve the listed control gaps first"}</h3><p>{data.how.openTaskCount} open tasks · {data.how.openConflictCount} conflicts · {data.how.gateGaps.length} evidence gates</p></article>
      </section>

      <section className="actions"><Link href={data.links.episodeCommand}>Episode decisions</Link><Link href={data.links.patientRecord}>Patient record</Link><Link href={data.links.clinicalExecution}>Patient work</Link><Link href={data.links.hospitalBoard}>Hospital board</Link></section>

      <section className="columns">
        <div><div className="head"><h2>Attention and blockers</h2><small>{data.how.attention.length}</small></div>{data.how.attention.length ? data.how.attention.map(item => <div className="issue" key={item}>{item}</div>) : <div className="clear">No red, overdue or unresolved recorded-control gaps.</div>}</div>
        <div><div className="head"><h2>Open work</h2><small>{data.tasks.length}</small></div>{data.tasks.length ? data.tasks.map(task => <article className={`task ${tone(task.overdue ? "overdue" : task.urgency)}`} key={task.id}><header><b>{task.title}</b><span>{task.overdue ? "OVERDUE" : task.urgency.toUpperCase()}</span></header><p>{task.description || "No explanatory note recorded"}</p><small>{label(task.ownerRole)} · {task.area || "No area"} · {when(task.dueAt)}</small></article>) : <div className="clear">No open work linked to this episode.</div>}</div>
      </section>

      <section><div className="head"><h2>Recorded schedule</h2><small>{data.schedule.length}</small></div><div className="schedule">{data.schedule.length ? data.schedule.map(block => <article className={tone(block.riskLevel)} key={block.blockRef}><time>{when(block.startsAt)}–{new Date(block.endsAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</time><b>{block.procedureName}</b><span>{block.areaName}</span><small>{block.leadStaffName || "Lead not assigned"} · {label(block.status)}</small></article>) : <div className="clear">No operational block recorded.</div>}</div></section>
    </>}
  </main>;
}

const css = `
.cb{min-height:100vh;background:#e9eef5;color:#0f172a;padding:9px;font-family:Inter,system-ui,sans-serif}.cb *{box-sizing:border-box}.hero{display:flex;justify-content:space-between;gap:16px;background:#071019;color:white;border-radius:18px;padding:18px}.hero>div{max-width:800px}.hero span,.five span{color:#2dd4bf;font-size:11px;font-weight:950;letter-spacing:.13em}.hero h1{font-size:clamp(40px,8vw,72px);line-height:.92;margin:6px 0}.hero p{margin:0;color:#b6c2d1}.hero nav,.actions{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.hero a,.actions a,.finder button{border:1px solid #334155;border-radius:999px;background:#0f172a;color:white;padding:10px 13px;text-decoration:none;font-weight:900}.finder{display:flex;gap:8px;align-items:end;flex-wrap:wrap;background:white;border:1px solid #cbd5e1;border-radius:13px;padding:10px;margin:9px 0}.finder label{display:grid;gap:3px;font-size:11px;font-weight:900;color:#475569}.finder input{min-height:44px;border:1px solid #94a3b8;border-radius:8px;padding:8px;font-size:16px}.finder strong{margin-left:auto;color:#475569}.empty,.identity,.five article,.task,.columns>div,.schedule article,.clear{background:white;border:1px solid #cbd5e1;border-radius:14px;padding:13px}.empty a{color:#1d4ed8;font-weight:900}.identity{display:flex;justify-content:space-between;gap:12px;align-items:center;border-left:7px solid #f59e0b}.identity.green{border-left-color:#16a34a}.identity h2{font-size:32px;margin:3px 0}.identity p,.identity small{color:#64748b}.identity>div:last-child{display:grid;gap:4px;max-width:480px}.five{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:9px 0}.five h3{font-size:19px;margin:7px 0 4px}.five p{margin:0;color:#475569}.actions{margin:9px 0}.columns{display:grid;grid-template-columns:1fr 1fr;gap:9px}.columns>div{display:grid;gap:7px}.head{display:flex;justify-content:space-between;align-items:end;gap:8px}.head h2{margin:7px 0;font-size:26px}.head small{font-weight:900;color:#64748b}.issue{border-left:6px solid #dc2626;background:#fff1f2;border-radius:8px;padding:9px}.clear{background:#f0fdf4;border-color:#bbf7d0;color:#166534}.task{border-left:6px solid #16a34a}.task.red{border-left-color:#dc2626}.task.amber{border-left-color:#f59e0b}.task header{display:flex;justify-content:space-between;gap:8px}.task header span{font-size:10px;font-weight:950}.task p{margin:5px 0;color:#475569}.task small{color:#64748b}.schedule{display:flex;gap:8px;overflow:auto}.schedule article{display:grid;gap:3px;min-width:220px;border-left:6px solid #16a34a}.schedule article.red{border-left-color:#dc2626}.schedule article.amber{border-left-color:#f59e0b}.schedule time{font-weight:950}.schedule span,.schedule small{color:#64748b}@media(max-width:1000px){.five{grid-template-columns:repeat(2,1fr)}.columns{grid-template-columns:1fr}}@media(max-width:620px){.cb{padding:5px}.hero{display:grid}.hero nav a{flex:1;text-align:center}.finder strong{width:100%}.identity{display:grid}.five{grid-template-columns:1fr}.actions a{flex:1;text-align:center}}
`;
