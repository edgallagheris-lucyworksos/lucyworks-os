"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { getOperationalContext } from "@/lib/operational-context";

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
  const [{ siteName }] = useState(() => getOperationalContext());
  const [episodeRef, setEpisodeRef] = useState(params.get("episode") || "");
  const [data, setData] = useState<Brief | null>(null);
  const [status, setStatus] = useState("Select a patient episode");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (value = episodeRef) => {
    const ref = value.trim();
    if (!ref) return;
    setBusy(true);
    setStatus("Loading patient summary");
    try {
      const result = await apiGet<Brief>(`/api/v16/care-brief/${encodeURIComponent(ref)}`);
      setData(result);
      setEpisodeRef(result.episodeRef);
      setStatus(`Updated ${new Date(result.generatedAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`);
    } catch (error) {
      setData(null);
      setStatus(error instanceof Error ? error.message : "Patient summary unavailable");
    } finally {
      setBusy(false);
    }
  }, [episodeRef]);

  useEffect(() => {
    const initial = params.get("episode");
    if (initial) void load(initial);
  }, [load, params]);

  return <main className="care-summary">
    <style>{css}</style>
    <header className="care-head">
      <div className="care-identity"><Link href="/hospital-board" className="care-mark">LW</Link><div><h1>Care brief</h1><span>{siteName}</span></div></div>
      <nav><Link href="/workspace">Patients</Link><Link href="/hospital-board">Hospital</Link><Link href="/referral-intake">New referral</Link></nav>
    </header>

    <section className="care-finder">
      <label>Episode<input value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} placeholder="Episode reference" /></label>
      <button disabled={busy || !episodeRef.trim()} onClick={() => void load()}>{busy ? "Loading…" : "Open"}</button>
      <strong aria-live="polite">{status}</strong>
    </section>

    {!data ? <section className="care-empty"><strong>No patient selected</strong><span>Open a patient from the workspace or enter an episode reference above.</span><Link href="/workspace">Patient workspace</Link></section> : <>
      <section className={`care-patient ${data.recordedControlsReady ? "clear" : "attention"}`}>
        <div><span>{label(data.serviceLine)} · {label(data.phase)}</span><h2>{data.patientName}</h2><small>{data.urgency.toUpperCase()}</small></div>
        <div><strong>{data.recordedControlsReady ? "Controls clear" : "Attention required"}</strong><span>{data.recordedControlsReady ? "Recorded requirements support the next step." : `${data.how.attention.length + data.how.gateGaps.length} recorded issue${data.how.attention.length + data.how.gateGaps.length === 1 ? "" : "s"} to resolve.`}</span></div>
      </section>

      <section className="care-five">
        <article><span>Lead</span><strong>{data.who.leadName || label(data.who.accountableRole)}</strong><small>{data.who.leadName ? label(data.who.leadRole) : "Accountable role"}</small></article>
        <article><span>Next action</span><strong>{data.what.nextAction}</strong><small>{data.what.currentOrNextProcedure || label(data.what.currentPhase)}</small></article>
        <article><span>Location</span><strong>{data.where.areaName || "Not placed"}</strong><small>{data.where.areaName ? "Current clinical area" : "Location required"}</small></article>
        <article><span>Timing</span><strong>{data.when.startsAt ? when(data.when.startsAt) : "Not scheduled"}</strong><small>{data.when.nextDeadline ? `Next: ${data.when.nextDeadline.title}` : data.when.endsAt ? `Until ${when(data.when.endsAt)}` : "No deadline recorded"}</small></article>
        <article className={data.how.criticalTaskCount || data.how.openConflictCount ? "attention" : "clear"}><span>Controls</span><strong>{data.how.criticalTaskCount + data.how.openConflictCount}</strong><small>critical tasks / conflicts</small></article>
      </section>

      <section className="care-actions"><Link className="primary" href={data.links.episodeCommand}>Episode control</Link><Link href={data.links.patientRecord}>Patient record</Link><Link href={data.links.clinicalExecution}>Clinical work</Link><Link href={data.links.hospitalBoard}>Hospital board</Link></section>

      <div className="care-columns">
        <section className="care-panel"><header><div><span>Safety</span><h2>Attention & blockers</h2></div><small>{data.how.attention.length}</small></header><div className="care-panel-body">{data.how.attention.length ? data.how.attention.map(item => <div className="care-issue" key={item}>{item}</div>) : <div className="care-clear">No red, overdue or unresolved recorded-control gaps.</div>}</div></section>
        <section className="care-panel"><header><div><span>Work</span><h2>Open actions</h2></div><small>{data.tasks.length}</small></header><div className="care-panel-body">{data.tasks.length ? data.tasks.map(task => <article className={`care-task ${tone(task.overdue ? "overdue" : task.urgency)}`} key={task.id}><header><strong>{task.title}</strong><span>{task.overdue ? "Overdue" : label(task.urgency)}</span></header><p>{task.description || "No additional note"}</p><small>{label(task.ownerRole)} · {task.area || "No area"} · {when(task.dueAt)}</small></article>) : <div className="care-clear">No open actions linked to this episode.</div>}</div></section>
      </div>

      <section className="care-panel"><header><div><span>Plan</span><h2>Recorded schedule</h2></div><small>{data.schedule.length}</small></header><div className="care-schedule">{data.schedule.length ? data.schedule.map(block => <article className={tone(block.riskLevel)} key={block.blockRef}><time>{when(block.startsAt)}</time><strong>{block.procedureName}</strong><span>{block.areaName}</span><small>{block.leadStaffName || "Lead not assigned"} · {label(block.status)}</small></article>) : <div className="care-clear">No scheduled work recorded.</div>}</div></section>
    </>}
  </main>;
}

const css = `
.care-summary{display:grid;gap:10px;min-height:100vh;background:#eef2f7;color:#172033;padding:12px 18px 28px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.care-summary *{box-sizing:border-box}.care-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 12px;background:#fff;border:1px solid #d9e1e9;border-radius:11px}.care-identity{display:flex;align-items:center;gap:10px}.care-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(145deg,#163a57,#102a42);color:#fff;text-decoration:none;font-size:11px;font-weight:900}.care-identity h1{margin:0;color:#142b40;font-size:17px}.care-identity span{display:block;margin-top:2px;color:#6f7e91;font-size:9px}.care-head nav{display:flex;gap:5px}.care-head nav a{padding:7px 9px;border-radius:7px;color:#294761;text-decoration:none;font-size:10px;font-weight:800}.care-finder{display:grid;grid-template-columns:minmax(220px,340px) auto 1fr;gap:7px;align-items:end;padding:9px 10px;background:#fff;border:1px solid #d9e1e9;border-radius:9px}.care-finder label{display:grid;gap:3px;color:#6b7a8d;font-size:9px;font-weight:800;text-transform:uppercase}.care-finder input{height:38px;border:1px solid #c2ccd7;border-radius:7px;padding:0 9px;color:#172033;font-size:12px}.care-finder button{height:38px;border:0;border-radius:7px;background:#173f5f;color:#fff;padding:0 12px;font-size:10px;font-weight:800}.care-finder strong{justify-self:end;align-self:center;color:#7a8796;font-size:9px}.care-empty{display:grid;justify-items:start;gap:5px;padding:22px;background:#fff;border:1px solid #d9e1e9;border-radius:10px;color:#6a798b}.care-empty strong{color:#243a4e;font-size:14px}.care-empty span{font-size:10px}.care-empty a{margin-top:4px;padding:7px 9px;border-radius:7px;background:#edf3f7;color:#294b65;text-decoration:none;font-size:9px;font-weight:800}.care-patient{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:13px 14px;background:#fff;border:1px solid #d9e1e9;border-left:4px solid #2d8061;border-radius:10px}.care-patient.attention{border-left-color:#c27a16}.care-patient>div:first-child span{color:#6c7a8c;font-size:8px;font-weight:800;text-transform:uppercase}.care-patient h2{margin:2px 0;color:#152f45;font-size:25px;letter-spacing:-.025em}.care-patient small{color:#6e7d8f;font-size:9px;font-weight:800}.care-patient>div:last-child{display:grid;gap:2px;text-align:right}.care-patient>div:last-child strong{font-size:11px;color:#294c40}.care-patient.attention>div:last-child strong{color:#8a5812}.care-patient>div:last-child span{color:#788596;font-size:9px}.care-five{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.care-five article{display:grid;align-content:start;gap:4px;min-height:92px;padding:10px 11px;background:#fff;border:1px solid #d9e1e9;border-top:3px solid #52738d;border-radius:9px}.care-five article.clear{border-top-color:#2d8061}.care-five article.attention{border-top-color:#c27a16}.care-five span{color:#738194;font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.06em}.care-five strong{color:#1e374c;font-size:12px;line-height:1.25}.care-five small{color:#7a8796;font-size:9px;line-height:1.35}.care-actions{display:flex;gap:6px;flex-wrap:wrap}.care-actions a{padding:7px 9px;border:1px solid #cbd5df;border-radius:7px;background:#fff;color:#294b65;text-decoration:none;font-size:9px;font-weight:800}.care-actions a.primary{border-color:#173f5f;background:#173f5f;color:#fff}.care-columns{display:grid;grid-template-columns:1fr 1fr;gap:10px}.care-panel{background:#fff;border:1px solid #d9e1e9;border-radius:10px;overflow:hidden}.care-panel>header{display:flex;justify-content:space-between;align-items:end;gap:8px;padding:10px 11px;border-bottom:1px solid #e8edf2;background:#f8fafc}.care-panel>header span{display:block;color:#718095;font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.08em}.care-panel>header h2{margin:2px 0 0;color:#1b3247;font-size:15px}.care-panel>header small{color:#7a8796;font-size:9px}.care-panel-body{display:grid;gap:6px;padding:8px}.care-issue{padding:8px 9px;border-left:3px solid #b9403a;border-radius:6px;background:#fff7f6;color:#823a35;font-size:9px;font-weight:700}.care-clear{padding:10px;border-radius:7px;background:#f1faf6;color:#387259;font-size:9px}.care-task{display:grid;gap:4px;padding:8px 9px;border:1px solid #e1e7ed;border-left:3px solid #2d8061;border-radius:7px}.care-task.red{border-left-color:#b9403a}.care-task.amber{border-left-color:#c27a16}.care-task>header{display:flex;justify-content:space-between;gap:8px}.care-task strong{font-size:10px}.care-task header span{color:#758296;font-size:8px;font-weight:800}.care-task p{margin:0;color:#607083;font-size:9px}.care-task small{color:#84909e;font-size:8px}.care-schedule{display:flex;gap:7px;overflow:auto;padding:8px}.care-schedule article{display:grid;gap:3px;min-width:210px;padding:9px 10px;border:1px solid #dfe6ec;border-left:3px solid #2d8061;border-radius:7px}.care-schedule article.red{border-left-color:#b9403a}.care-schedule article.amber{border-left-color:#c27a16}.care-schedule time{color:#315d7d;font-size:9px;font-weight:850}.care-schedule strong{font-size:11px}.care-schedule span,.care-schedule small{color:#718095;font-size:8px}
@media(max-width:980px){.care-five{grid-template-columns:repeat(3,1fr)}.care-columns{grid-template-columns:1fr}}
@media(max-width:620px){.care-summary{padding:8px}.care-head nav a:not(:first-child){display:none}.care-finder{grid-template-columns:1fr auto}.care-finder strong{grid-column:1/-1;justify-self:start}.care-patient{display:grid}.care-patient>div:last-child{text-align:left}.care-five{grid-template-columns:1fr 1fr}.care-actions a{flex:1;text-align:center}}
`;
