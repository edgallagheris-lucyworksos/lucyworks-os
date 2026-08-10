"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { HospitalMasterBoardV11 } from "@/components/hospital-master-board-v11";
import { AutomationBoardDockV23 } from "@/components/automation-board-dock-v23";

type Block = {
  blockRef: string;
  episodeRef?: string;
  patientName?: string;
  procedureName: string;
  areaRef: string;
  areaName: string;
  startsAt: string;
  endsAt: string;
  status: string;
  riskLevel: string;
  leadStaffName?: string;
};

type Episode = {
  episodeRef: string;
  patientName: string;
  phase: string;
  urgency: string;
  ownerRole: string;
  nextAction?: string;
};

type Board = {
  generatedAt: string;
  operationalDate: string;
  blocks: Block[];
  episodes: Episode[];
  conflicts: Array<{ severity: string; primaryBlockRef?: string; relatedRefs: string[]; explanation: string }>;
  summary: { blocks: number; episodes: number; redConflicts: number; amberConflicts: number; unassignedBlocks: number };
  liveWindow: { blocks: Block[] };
};

const PREMISES = "default-premises";

function clock(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "emergency", "blocked"].includes(normal)) return "red";
  if (["amber", "planned", "pending"].includes(normal)) return "amber";
  return "green";
}

function MobileHospitalBoard() {
  const [date, setDate] = useState(() => localOperationalDate());
  const [area, setArea] = useState("all");
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("Loading operational state");

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${PREMISES}&operational_date=${date}`);
      setBoard(data);
      setStatus(`Updated ${new Date(data.generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Hospital board unavailable");
    }
  }, [date]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const conflicts = useMemo(() => {
    const rows = new Map<string, string[]>();
    for (const conflict of board?.conflicts || []) {
      for (const ref of [conflict.primaryBlockRef, ...(conflict.relatedRefs || [])].filter(Boolean) as string[]) {
        rows.set(ref, [...(rows.get(ref) || []), conflict.explanation]);
      }
    }
    return rows;
  }, [board]);

  const blocks = useMemo(() => {
    if (!board) return [];
    return board.blocks
      .filter(block => area === "all" || block.areaRef === area || block.areaName.toLowerCase().includes(area))
      .sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime());
  }, [area, board]);

  if (!board) return <main className="hb-loading"><style>{css}</style><span className="spinner" />{status}</main>;

  const scheduledRefs = new Set(board.blocks.map(block => block.episodeRef).filter(Boolean));
  const unscheduled = board.episodes.filter(episode => !scheduledRefs.has(episode.episodeRef));
  const attention = board.summary.redConflicts + board.summary.unassignedBlocks;

  return (
    <main className="hb-mobile">
      <style>{css}</style>

      <section className="hb-summary">
        <div className="hb-summary-copy">
          <span>Live hospital</span>
          <h2>Today&apos;s operating plan</h2>
          <p>Current patients, clinical areas, accountable staff and constraints.</p>
        </div>
        <div className={`hb-health ${attention ? "attention" : "clear"}`}>
          <b>{attention}</b>
          <small>{attention === 1 ? "item needs attention" : "items need attention"}</small>
        </div>
      </section>

      <section className="hb-toolbar">
        <label>Date<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label>
        <label>Area<select value={area} onChange={event => setArea(event.target.value)}><option value="all">All clinical areas</option><option value="theatre">Theatres</option><option value="mri">MRI</option><option value="ct">CT</option><option value="x-ray">X-ray</option><option value="consult">Consults</option><option value="ward">Wards / ICU</option></select></label>
        <button type="button" onClick={() => setDate(localOperationalDate())}>Today</button>
        <button type="button" onClick={() => void refresh()}>Refresh</button>
        <span>{status}</span>
      </section>

      <section className="hb-kpis">
        <article><b>{board.summary.episodes}</b><small>active patients</small></article>
        <article><b>{board.summary.blocks}</b><small>care blocks</small></article>
        <article className={board.summary.redConflicts ? "red" : "clear"}><b>{board.summary.redConflicts}</b><small>critical conflicts</small></article>
        <article className={board.summary.unassignedBlocks ? "amber" : "clear"}><b>{board.summary.unassignedBlocks}</b><small>without a lead</small></article>
      </section>

      {board.liveWindow.blocks.length ? (
        <section className="hb-now">
          <header><span>Next 90 minutes</span><strong>{board.liveWindow.blocks.length} scheduled</strong></header>
          <div>
            {board.liveWindow.blocks.map(block => (
              <a href={`#${block.blockRef}`} key={block.blockRef}>
                <time>{clock(block.startsAt)}</time>
                <span><b>{block.patientName || "Operational work"}</b><small>{block.procedureName} · {block.areaName}</small></span>
              </a>
            ))}
          </div>
        </section>
      ) : null}

      <section className="hb-list">
        <header><div><span>Operating plan</span><h2>Scheduled care</h2></div><small>{blocks.length} shown</small></header>
        {blocks.length ? blocks.map(block => {
          const issues = conflicts.get(block.blockRef) || [];
          const risk = tone(issues.length ? "red" : block.riskLevel);
          return (
            <article id={block.blockRef} className={risk} key={block.blockRef}>
              <div className="hb-time"><b>{clock(block.startsAt)}</b><span>{clock(block.endsAt)}</span></div>
              <div className="hb-card">
                <div className="hb-card-head"><div><small>{block.areaName}</small><h3>{block.patientName || "Operational work"}</h3></div><span className={`hb-pill ${tone(block.status)}`}>{label(block.status)}</span></div>
                <strong className="hb-procedure">{block.procedureName}</strong>
                <div className="hb-meta"><span><small>Lead</small><b>{block.leadStaffName || "Not assigned"}</b></span><span><small>Episode</small><b>{block.episodeRef || "Not linked"}</b></span></div>
                {issues.length ? <div className="hb-issues"><strong>Resolve before proceeding</strong>{issues.slice(0, 4).map(issue => <span key={issue}>{issue}</span>)}</div> : null}
                <footer>{block.episodeRef ? <Link href={`/episode-command?episode=${block.episodeRef}`}>Open episode</Link> : null}<Link href="/workspace">Patient workspace</Link></footer>
              </div>
            </article>
          );
        }) : <div className="hb-empty"><strong>No scheduled care for this view.</strong><span>Change the area or date, or add a referral from the intake workspace.</span><Link href="/referral-intake">Referral intake</Link></div>}
      </section>

      <section className="hb-unscheduled">
        <header><div><span>Capacity</span><h2>Patients without a care block</h2></div><small>{unscheduled.length}</small></header>
        {unscheduled.length ? unscheduled.map(episode => (
          <article key={episode.episodeRef}>
            <div><b>{episode.patientName}</b><span>{label(episode.phase)} · {label(episode.ownerRole)}</span><small>{episode.nextAction || "Review the next safe action"}</small></div>
            <Link href={`/episode-command?episode=${episode.episodeRef}`}>Open</Link>
          </article>
        )) : <div className="hb-clear"><strong>Every active patient has scheduled care.</strong></div>}
      </section>

      <details className="hb-automation">
        <summary>Automation controls</summary>
        <AutomationBoardDockV23 operationalDate={date} />
      </details>
    </main>
  );
}

export function ResponsiveHospitalBoardV15() {
  const [mobile, setMobile] = useState<boolean | null>(null);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 760px)");
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  if (mobile === null) return <main className="hb-loading"><style>{css}</style><span className="spinner" />Loading hospital board</main>;
  return mobile ? <MobileHospitalBoard /> : <HospitalMasterBoardV11 />;
}

const css = `
.hb-mobile{min-height:100vh;background:#eef2f6;color:#182233;padding:8px;font-family:Inter,system-ui,sans-serif}.hb-mobile *{box-sizing:border-box}.hb-loading{min-height:60vh;display:flex;align-items:center;justify-content:center;gap:10px;background:#eef2f6;color:#526174;font:700 13px Inter,system-ui,sans-serif}.spinner{width:16px;height:16px;border:2px solid #cbd5e1;border-top-color:#315d7d;border-radius:999px;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.hb-summary{display:flex;justify-content:space-between;align-items:center;gap:12px;background:#fff;border:1px solid #d9e1ea;border-radius:13px;padding:13px 14px}.hb-summary-copy>span,.hb-list>header span,.hb-unscheduled>header span{color:#66778b;font-size:9px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.hb-summary h2{margin:3px 0 2px;font-size:22px;letter-spacing:-.025em}.hb-summary p{margin:0;color:#65758a;font-size:12px}.hb-health{display:grid;min-width:86px;text-align:right}.hb-health b{font-size:24px}.hb-health small{font-size:9px;color:#65758a}.hb-health.attention b{color:#b45309}.hb-health.clear b{color:#26785a}
.hb-toolbar{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:7px 0;background:#fff;border:1px solid #d9e1ea;border-radius:11px;padding:8px}.hb-toolbar label{display:grid;gap:3px;color:#66778b;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.hb-toolbar input,.hb-toolbar select{width:100%;min-height:40px;border:1px solid #b9c5d2;border-radius:7px;background:#fff;color:#172033;padding:6px 8px;font-size:14px}.hb-toolbar button{border:1px solid #c5d0dc;border-radius:7px;background:#f8fafc;color:#29465f;min-height:38px;font-weight:750}.hb-toolbar>span{grid-column:1/-1;color:#718096;font-size:10px}
.hb-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.hb-kpis article{background:#fff;border:1px solid #d9e1ea;border-radius:9px;padding:8px}.hb-kpis b{display:block;color:#17334d;font-size:20px}.hb-kpis small{display:block;color:#6c7b8d;font-size:9px}.hb-kpis article.red{border-top:3px solid #b9403a}.hb-kpis article.amber{border-top:3px solid #c47a16}.hb-kpis article.clear{border-top:3px solid #3d8469}
.hb-now{margin-top:7px;background:#fff;border:1px solid #d9e1ea;border-radius:10px;overflow:hidden}.hb-now>header{display:flex;justify-content:space-between;padding:8px 10px;border-bottom:1px solid #e8edf2;color:#596a7d;font-size:10px}.hb-now>div{display:flex;gap:6px;overflow:auto;padding:7px}.hb-now a{display:flex;gap:8px;min-width:205px;padding:8px 9px;border:1px solid #dbe3eb;border-radius:8px;color:#20364a;text-decoration:none}.hb-now time{font-weight:850;color:#315d7d}.hb-now a>span{display:grid}.hb-now small{color:#718096;font-size:9px;margin-top:2px}
.hb-list,.hb-unscheduled{display:grid;gap:7px;margin-top:10px}.hb-list>header,.hb-unscheduled>header{display:flex;justify-content:space-between;align-items:end;padding:0 2px}.hb-list h2,.hb-unscheduled h2{margin:2px 0 0;font-size:18px}.hb-list>header>small,.hb-unscheduled>header>small{color:#738196;font-size:10px}.hb-list>article{display:grid;grid-template-columns:57px minmax(0,1fr);background:#fff;border:1px solid #d8e0e9;border-left:4px solid #3d8469;border-radius:10px;overflow:hidden}.hb-list>article.red{border-left-color:#b9403a}.hb-list>article.amber{border-left-color:#c47a16}.hb-time{display:grid;align-content:start;gap:1px;padding:10px 7px;background:#f8fafc;border-right:1px solid #e4e9ef}.hb-time b{font-size:15px}.hb-time span{color:#78869a;font-size:9px}.hb-card{padding:9px}.hb-card-head{display:flex;justify-content:space-between;gap:8px}.hb-card-head small{color:#718096;font-size:9px}.hb-card h3{margin:2px 0;font-size:18px}.hb-pill{align-self:start;border-radius:999px;padding:4px 6px;background:#e7f5ed;color:#256148;font-size:8px;font-weight:850;text-transform:uppercase}.hb-pill.amber{background:#fff4df;color:#8c570d}.hb-pill.red{background:#ffebe9;color:#962f2a}.hb-procedure{display:block;margin-top:3px;font-size:12px}.hb-meta{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:7px}.hb-meta>span{display:grid;padding:6px;background:#f7f9fb;border-radius:6px;min-width:0}.hb-meta small{color:#78869a;font-size:8px;text-transform:uppercase}.hb-meta b{font-size:10px;overflow-wrap:anywhere}.hb-issues{display:grid;gap:3px;margin-top:7px;border-left:3px solid #b9403a;background:#fff5f4;border-radius:6px;padding:7px}.hb-issues strong{font-size:10px}.hb-issues span{color:#6f4a48;font-size:10px}.hb-card footer{display:flex;gap:12px;margin-top:8px}.hb-card footer a,.hb-empty a,.hb-unscheduled a{color:#285c82;font-size:10px;font-weight:800;text-decoration:none}
.hb-empty{display:grid;gap:5px;background:#fff;border:1px dashed #bdc9d5;border-radius:10px;padding:13px;color:#5f6e80}.hb-empty strong{color:#27394c}.hb-empty span{font-size:11px}.hb-unscheduled>article{display:flex;justify-content:space-between;align-items:center;gap:8px;background:#fff;border:1px solid #e0c48f;border-radius:9px;padding:9px}.hb-unscheduled>article div{display:grid;gap:2px}.hb-unscheduled span,.hb-unscheduled small{color:#718096;font-size:10px}.hb-clear{border:1px solid #b9dfcc;background:#f3fbf7;color:#2d674f;border-radius:9px;padding:9px;font-size:11px}.hb-automation{margin-top:12px;border:1px solid #d9e1ea;border-radius:10px;background:#fff}.hb-automation>summary{padding:10px 12px;color:#506175;font-size:11px;font-weight:800;cursor:pointer}
@media(max-width:480px){.hb-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.hb-summary p{display:none}.hb-health{min-width:70px}.hb-card h3{font-size:16px}}
`;
