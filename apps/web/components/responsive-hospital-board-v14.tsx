"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { HospitalMasterBoardV11 } from "@/components/hospital-master-board-v11";

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
  blockers: unknown[];
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

function today() {
  return new Date().toISOString().slice(0, 10);
}

function clock(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "emergency", "blocked"].includes(normal)) return "red";
  if (["amber", "planned", "pending"].includes(normal)) return "amber";
  return "green";
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function MobileHospitalAgenda() {
  const [date, setDate] = useState(today());
  const [area, setArea] = useState("all");
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("Loading hospital agenda");

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${PREMISES}&operational_date=${date}`);
      setBoard(data);
      setStatus(`Live · ${new Date(data.generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Board unavailable");
    }
  }, [date]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const conflicts = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const conflict of board?.conflicts || []) {
      for (const ref of [conflict.primaryBlockRef, ...(conflict.relatedRefs || [])].filter(Boolean) as string[]) {
        map.set(ref, [...(map.get(ref) || []), conflict.explanation]);
      }
    }
    return map;
  }, [board]);

  const blocks = useMemo(() => {
    if (!board) return [];
    return board.blocks
      .filter(block => area === "all" || block.areaRef === area || block.areaName.toLowerCase().includes(area))
      .sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime());
  }, [board, area]);

  const scheduledRefs = new Set((board?.blocks || []).map(block => block.episodeRef).filter(Boolean));
  const unscheduled = (board?.episodes || []).filter(episode => !scheduledRefs.has(episode.episodeRef));

  if (!board) return <main className="ma loading"><style>{css}</style>{status}</main>;

  return <main className="ma">
    <style>{css}</style>
    <header className="hero">
      <span>LucyWorks OS · mobile hospital agenda</span>
      <h1>Today</h1>
      <p>Patients, places, times, staff and blockers — designed for a phone rather than a desktop grid.</p>
      <nav><Link href="/workspace">Patient command</Link><Link href="/referral-intake">New referral</Link><Link href="/input">Quick input</Link></nav>
    </header>

    <section className="toolbar">
      <label>Date<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label>
      <label>Area<select value={area} onChange={event => setArea(event.target.value)}><option value="all">All areas</option><option value="theatre">Theatres</option><option value="mri">MRI</option><option value="ct">CT</option><option value="x-ray">X-ray</option><option value="consult">Consults</option><option value="ward">Wards / ICU</option></select></label>
      <button onClick={() => void refresh()}>Refresh</button>
      <strong>{status}</strong>
    </section>

    <section className="kpis">
      <article><b>{board.summary.blocks}</b><small>care blocks</small></article>
      <article><b>{board.summary.episodes}</b><small>active patients</small></article>
      <article className={board.summary.redConflicts ? "red" : "green"}><b>{board.summary.redConflicts}</b><small>red conflicts</small></article>
      <article className={board.summary.unassignedBlocks ? "amber" : "green"}><b>{board.summary.unassignedBlocks}</b><small>no lead assigned</small></article>
    </section>

    {board.liveWindow.blocks.length ? <section className="live"><b>Next 90 minutes</b>{board.liveWindow.blocks.map(block => <a href={`#${block.blockRef}`} key={block.blockRef}><time>{clock(block.startsAt)}</time><span>{block.patientName || "Operational work"}</span><small>{block.procedureName} · {block.areaName}</small></a>)}</section> : null}

    <section className="agenda">
      <div className="head"><div><span>OPERATING PLAN</span><h2>{blocks.length ? "Scheduled care" : "No care blocks scheduled"}</h2></div><small>{blocks.length} shown</small></div>
      {blocks.length ? blocks.map(block => {
        const issues = conflicts.get(block.blockRef) || [];
        return <article id={block.blockRef} className={tone(issues.length ? "red" : block.riskLevel)} key={block.blockRef}>
          <div className="time"><b>{clock(block.startsAt)}</b><span>{clock(block.endsAt)}</span></div>
          <div className="body"><header><div><small>{block.areaName}</small><h3>{block.patientName || "Operational work"}</h3></div><span className={`pill ${tone(block.status)}`}>{label(block.status)}</span></header><p>{block.procedureName}</p><dl><div><dt>Lead</dt><dd>{block.leadStaffName || "Not assigned"}</dd></div><div><dt>Episode</dt><dd>{block.episodeRef || "Not linked"}</dd></div></dl>{issues.length ? <div className="issues"><b>Cannot proceed cleanly</b>{issues.slice(0, 4).map(issue => <span key={issue}>{issue}</span>)}</div> : null}<footer>{block.episodeRef ? <Link href={`/episode-command?episode=${block.episodeRef}`}>Episode command</Link> : null}<Link href="/workspace">Patient command</Link></footer></div>
        </article>;
      }) : <article className="empty"><b>The board is empty for this date.</b><p>This does not mean the hospital has no work. Check unscheduled patients below and link operational tasks to their canonical episodes.</p><Link href="/workspace">Open patient command</Link></article>}
    </section>

    <section className="unscheduled">
      <div className="head"><div><span>CAPACITY RISK</span><h2>Active patients without a block</h2></div><small>{unscheduled.length}</small></div>
      {unscheduled.length ? unscheduled.map(episode => <article key={episode.episodeRef}><div><b>{episode.patientName}</b><span>{label(episode.phase)} · {label(episode.ownerRole)}</span><small>{episode.nextAction || "Review and schedule the next safe step"}</small></div><Link href={`/episode-command?episode=${episode.episodeRef}`}>Open</Link></article>) : <div className="clear"><b>Every active patient has at least one care block today.</b></div>}
    </section>
  </main>;
}

export function ResponsiveHospitalBoardV14() {
  const [mobile, setMobile] = useState<boolean | null>(null);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 760px)");
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  if (mobile === null) return <main className="ma loading"><style>{css}</style>Loading hospital board</main>;
  return mobile ? <MobileHospitalAgenda /> : <HospitalMasterBoardV11 />;
}

const css = `
.ma{min-height:100vh;background:#e9eef5;color:#0f172a;padding:7px;font-family:Inter,system-ui,sans-serif}.ma *{box-sizing:border-box}.ma.loading{display:grid;place-items:center;background:#071019;color:white;font-weight:900}.hero{background:#071019;color:white;border-radius:17px;padding:17px}.hero>span,.head>div>span{color:#2dd4bf;font-size:10px;font-weight:950;letter-spacing:.13em}.hero h1{font-size:55px;line-height:.9;margin:7px 0}.hero p{color:#b6c2d1;margin:0}.hero nav{display:flex;gap:7px;margin-top:14px;overflow:auto}.hero a,.toolbar button{flex:0 0 auto;border:1px solid #334155;border-radius:999px;background:#0f172a;color:white;padding:10px 12px;text-decoration:none;font-weight:900}.toolbar{display:grid;grid-template-columns:1fr 1fr;gap:8px;background:white;border:1px solid #cbd5e1;border-radius:13px;padding:9px;margin:8px 0}.toolbar label{display:grid;gap:3px;font-size:11px;font-weight:900;color:#475569}.toolbar input,.toolbar select{min-height:44px;border:1px solid #94a3b8;border-radius:8px;padding:7px;font-size:16px;background:white}.toolbar button{border-color:#0f172a}.toolbar strong{grid-column:1/-1;color:#475569;font-size:12px}.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kpis article{background:white;border:1px solid #cbd5e1;border-top:5px solid #64748b;border-radius:11px;padding:9px}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{display:block;font-size:27px}.kpis small{color:#64748b}.live{display:flex;gap:7px;overflow:auto;padding:8px 0}.live>b{display:grid;place-items:center;min-width:86px;background:#0f172a;color:white;border-radius:9px;padding:8px}.live a{display:grid;gap:2px;min-width:170px;border:1px solid #cbd5e1;border-radius:9px;background:white;padding:8px;color:#0f172a;text-decoration:none}.live time{font-weight:950}.live small{color:#64748b}.agenda,.unscheduled{display:grid;gap:8px;margin-top:9px}.head{display:flex;justify-content:space-between;align-items:end;gap:8px}.head h2{font-size:28px;line-height:1;margin:4px 0}.head>small{font-weight:900;color:#64748b}.agenda>article{display:grid;grid-template-columns:62px minmax(0,1fr);background:white;border:1px solid #cbd5e1;border-left:7px solid #16a34a;border-radius:13px;overflow:hidden}.agenda>article.red{border-left-color:#dc2626}.agenda>article.amber{border-left-color:#f59e0b}.time{display:grid;align-content:start;gap:2px;background:#f8fafc;padding:10px 7px;border-right:1px solid #e2e8f0}.time b{font-size:18px}.time span{font-size:11px;color:#64748b}.body{padding:10px}.body header{display:flex;justify-content:space-between;gap:8px}.body header small{color:#64748b;font-weight:850}.body h3{font-size:22px;margin:2px 0}.body>p{margin:5px 0;font-weight:800}.pill{height:max-content;border-radius:999px;padding:5px 7px;background:#dcfce7;color:#166534;font-size:10px;font-weight:950}.pill.amber{background:#fef3c7;color:#92400e}.pill.red{background:#fee2e2;color:#991b1b}.body dl{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0}.body dl div{background:#f8fafc;border-radius:7px;padding:7px}.body dt{font-size:9px;font-weight:900;color:#64748b;text-transform:uppercase}.body dd{margin:2px 0 0;font-weight:800;overflow-wrap:anywhere}.issues{display:grid;gap:4px;border:1px solid #fecaca;background:#fff1f2;border-radius:8px;padding:8px}.issues span:before{content:"• ";font-weight:900}.body footer{display:flex;gap:12px;margin-top:9px}.body footer a,.empty a,.unscheduled a{color:#1d4ed8;font-weight:900}.empty{display:block!important;padding:15px!important}.empty b{font-size:20px}.empty p{color:#475569}.unscheduled>article{display:flex;justify-content:space-between;gap:9px;align-items:center;background:white;border:1px solid #f59e0b;border-radius:10px;padding:10px}.unscheduled>article div{display:grid;gap:2px}.unscheduled span,.unscheduled small{color:#64748b}.clear{border:1px solid #bbf7d0;background:#f0fdf4;color:#166534;border-radius:10px;padding:11px}
`;
