"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { getOperationalContext } from "@/lib/operational-context";

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

type Conflict = { severity: string; primaryBlockRef?: string; relatedRefs: string[]; explanation: string };
type Board = {
  generatedAt: string;
  operationalDate: string;
  blocks: Block[];
  episodes: Episode[];
  conflicts: Conflict[];
  summary: { blocks: number; episodes: number; redConflicts: number; amberConflicts: number; unassignedBlocks: number };
  liveWindow: { blocks: Block[] };
};

function clock(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["red", "emergency", "blocked", "critical"].includes(normal)) return "red";
  if (["amber", "planned", "pending", "warning"].includes(normal)) return "amber";
  return "green";
}

export function ResponsiveHospitalBoardV15() {
  const [{ premisesRef, siteName }] = useState(() => getOperationalContext());
  const [date, setDate] = useState(() => localOperationalDate());
  const [area, setArea] = useState("all");
  const [query, setQuery] = useState("");
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("Loading live hospital state");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${encodeURIComponent(premisesRef)}&operational_date=${date}`);
      setBoard(data);
      setError("");
      setStatus(`Updated ${new Date(data.generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Hospital board unavailable");
      setStatus("Unable to refresh");
    }
  }, [date, premisesRef]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const conflictMap = useMemo(() => {
    const rows = new Map<string, Conflict[]>();
    for (const conflict of board?.conflicts || []) {
      for (const ref of [conflict.primaryBlockRef, ...(conflict.relatedRefs || [])].filter(Boolean) as string[]) {
        rows.set(ref, [...(rows.get(ref) || []), conflict]);
      }
    }
    return rows;
  }, [board]);

  const filteredBlocks = useMemo(() => {
    if (!board) return [];
    const term = query.trim().toLowerCase();
    return board.blocks
      .filter(block => area === "all" || block.areaRef === area || block.areaName.toLowerCase().includes(area))
      .filter(block => !term || [block.patientName, block.procedureName, block.areaName, block.leadStaffName, block.episodeRef].some(value => value?.toLowerCase().includes(term)))
      .sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime());
  }, [area, board, query]);

  const scheduledRefs = useMemo(() => new Set(board?.blocks.map(block => block.episodeRef).filter(Boolean) as string[] || []), [board]);
  const unscheduled = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (board?.episodes || [])
      .filter(episode => !scheduledRefs.has(episode.episodeRef))
      .filter(episode => !term || [episode.patientName, episode.phase, episode.ownerRole, episode.episodeRef].some(value => value.toLowerCase().includes(term)));
  }, [board, query, scheduledRefs]);

  if (!board && !error) {
    return <section className="pro-board-state"><style>{css}</style><span className="pro-spinner" />Loading {siteName}</section>;
  }

  const attention = (board?.summary.redConflicts || 0) + (board?.summary.unassignedBlocks || 0);

  return (
    <section className="pro-board">
      <style>{css}</style>

      <div className="pro-board__toolbar">
        <div className="pro-board__search">
          <span aria-hidden="true">⌕</span>
          <input aria-label="Find patient or work" placeholder="Find patient, procedure, staff or episode" value={query} onChange={event => setQuery(event.target.value)} />
        </div>
        <label>Date<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label>
        <label>Area<select value={area} onChange={event => setArea(event.target.value)}><option value="all">All areas</option><option value="theatre">Theatres</option><option value="mri">MRI</option><option value="ct">CT</option><option value="x-ray">X-ray</option><option value="consult">Consults</option><option value="ward">Wards / ICU</option></select></label>
        <button type="button" className="pro-button" onClick={() => setDate(localOperationalDate())}>Today</button>
        <button type="button" className="pro-button" onClick={() => void refresh()}>Refresh</button>
      </div>

      <div className="pro-board__pulse" aria-live="polite">
        <div><span className={error ? "dot red" : "dot"} /><strong>{siteName}</strong><span>{error || status}</span></div>
        <div className={attention ? "attention" : "clear"}>{attention ? `${attention} needs attention` : "No critical operational exceptions"}</div>
      </div>

      <div className="pro-board__metrics">
        <article><span>Active patients</span><strong>{board?.summary.episodes ?? 0}</strong></article>
        <article><span>Scheduled work</span><strong>{board?.summary.blocks ?? 0}</strong></article>
        <article className={(board?.summary.redConflicts || 0) ? "critical" : "good"}><span>Critical conflicts</span><strong>{board?.summary.redConflicts ?? 0}</strong></article>
        <article className={(board?.summary.unassignedBlocks || 0) ? "warning" : "good"}><span>Without a lead</span><strong>{board?.summary.unassignedBlocks ?? 0}</strong></article>
      </div>

      {(board?.liveWindow.blocks.length || 0) > 0 && !query ? (
        <section className="pro-now">
          <header><div><span>Now & next</span><strong>Next 90 minutes</strong></div><small>{board?.liveWindow.blocks.length} scheduled</small></header>
          <div className="pro-now__rail">
            {board?.liveWindow.blocks.map(block => (
              <a href={`#${block.blockRef}`} key={block.blockRef}>
                <time>{clock(block.startsAt)}</time>
                <span><strong>{block.patientName || "Operational work"}</strong><small>{block.procedureName} · {block.areaName}</small></span>
              </a>
            ))}
          </div>
        </section>
      ) : null}

      <div className="pro-board__columns">
        <section className="pro-plan">
          <header><div><span>Operating plan</span><h2>Scheduled care</h2></div><small>{filteredBlocks.length} shown</small></header>
          <div className="pro-plan__head" aria-hidden="true"><span>Time</span><span>Patient / work</span><span>Location</span><span>Lead</span><span>Status</span><span /></div>
          {filteredBlocks.length ? filteredBlocks.map(block => {
            const issues = conflictMap.get(block.blockRef) || [];
            const risk = tone(issues.some(issue => issue.severity === "red") ? "red" : block.riskLevel);
            return (
              <article id={block.blockRef} className={`pro-row ${risk}`} key={block.blockRef}>
                <div className="pro-row__time"><strong>{clock(block.startsAt)}</strong><span>{clock(block.endsAt)}</span></div>
                <div className="pro-row__patient"><small>{block.procedureName}</small><strong>{block.patientName || "Operational work"}</strong>{issues.length ? <span>{issues[0].explanation}</span> : null}</div>
                <div className="pro-row__location"><strong>{block.areaName}</strong><span>{block.areaRef}</span></div>
                <div className="pro-row__lead"><strong>{block.leadStaffName || "Unassigned"}</strong></div>
                <div><span className={`pro-badge ${tone(block.status)}`}>{label(block.status)}</span></div>
                <div className="pro-row__action">{block.episodeRef ? <Link href={`/episode-command?episode=${encodeURIComponent(block.episodeRef)}`}>Open</Link> : <span>—</span>}</div>
              </article>
            );
          }) : <div className="pro-empty"><strong>No scheduled care matches this view.</strong><span>Change the filters or add a referral.</span></div>}
        </section>

        <aside className="pro-side">
          <section className="pro-side__panel">
            <header><div><span>Queue</span><h2>Waiting for a care block</h2></div><small>{unscheduled.length}</small></header>
            {unscheduled.length ? unscheduled.slice(0, 12).map(episode => (
              <article key={episode.episodeRef}>
                <div><strong>{episode.patientName}</strong><span>{label(episode.phase)} · {label(episode.ownerRole)}</span><small>{episode.nextAction || "Review next action"}</small></div>
                <Link href={`/episode-command?episode=${encodeURIComponent(episode.episodeRef)}`}>Open</Link>
              </article>
            )) : <div className="pro-side__clear">All active patients have planned care.</div>}
          </section>

          <section className="pro-side__panel compact">
            <header><div><span>Shortcuts</span><h2>Common actions</h2></div></header>
            <nav><Link href="/referral-intake">New referral</Link><Link href="/workspace">Patient workspace</Link><Link href="/system-control">System status</Link></nav>
          </section>
        </aside>
      </div>
    </section>
  );
}

const css = `
.pro-board{display:grid;gap:12px;padding:12px 18px 28px;color:#172033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.pro-board *{box-sizing:border-box}.pro-board-state{min-height:60vh;display:flex;align-items:center;justify-content:center;gap:10px;color:#5d6b7b;background:#eef2f7;font:700 13px Inter,system-ui,sans-serif}.pro-spinner{width:16px;height:16px;border:2px solid #cbd5e1;border-top-color:#284f6d;border-radius:999px;animation:prospin .8s linear infinite}@keyframes prospin{to{transform:rotate(360deg)}}
.pro-board__toolbar{display:grid;grid-template-columns:minmax(260px,1.5fr) 155px 170px auto auto;gap:8px;align-items:end}.pro-board__toolbar label{display:grid;gap:4px;color:#6a7889;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.pro-board__toolbar input,.pro-board__toolbar select{height:40px;min-height:40px;border:1px solid #c7d0db;border-radius:8px;background:#fff;color:#172033;padding:0 10px;font-size:13px}.pro-board__search{position:relative;align-self:end}.pro-board__search span{position:absolute;left:12px;top:9px;color:#748398;font-size:18px}.pro-board__search input{width:100%;padding-left:36px}.pro-button{height:40px;min-height:40px;border:1px solid #c7d0db;border-radius:8px;background:#fff;color:#29445c;padding:0 13px;font-size:12px;font-weight:800}.pro-button:hover{background:#f5f8fb}
.pro-board__pulse{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 11px;border:1px solid #dae2ea;border-radius:9px;background:#fff;color:#667487;font-size:11px}.pro-board__pulse>div:first-child{display:flex;align-items:center;gap:7px;min-width:0}.pro-board__pulse strong{color:#22384d}.pro-board__pulse .dot{width:7px;height:7px;border-radius:99px;background:#27855f;box-shadow:0 0 0 3px #dcefe7;flex:0 0 auto}.pro-board__pulse .dot.red{background:#bb3f39;box-shadow:0 0 0 3px #f7dfdd}.pro-board__pulse .attention{color:#9a5c0d;font-weight:800}.pro-board__pulse .clear{color:#2d7358;font-weight:800}
.pro-board__metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.pro-board__metrics article{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 12px;background:#fff;border:1px solid #d9e1e9;border-radius:10px;border-left:4px solid #52738d}.pro-board__metrics article.good{border-left-color:#2d8061}.pro-board__metrics article.warning{border-left-color:#c27a16}.pro-board__metrics article.critical{border-left-color:#b9403a}.pro-board__metrics span{color:#66768a;font-size:11px;font-weight:700}.pro-board__metrics strong{color:#17334d;font-size:22px;letter-spacing:-.03em}
.pro-now{background:#fff;border:1px solid #d9e1e9;border-radius:10px;overflow:hidden}.pro-now>header,.pro-plan>header,.pro-side__panel>header{display:flex;justify-content:space-between;align-items:end;gap:10px;padding:10px 12px;border-bottom:1px solid #e7ecf1}.pro-now header span,.pro-plan header span,.pro-side__panel header span{display:block;color:#6b7a8d;font-size:9px;font-weight:850;letter-spacing:.11em;text-transform:uppercase}.pro-now header strong{font-size:14px}.pro-now header small,.pro-plan header small,.pro-side__panel header small{color:#77859a;font-size:10px}.pro-now__rail{display:flex;gap:7px;overflow:auto;padding:8px}.pro-now__rail a{display:flex;gap:10px;min-width:230px;padding:9px 10px;border:1px solid #dfe6ed;border-radius:8px;color:#22394e;text-decoration:none}.pro-now__rail time{font-weight:850;color:#315d7d}.pro-now__rail a>span{display:grid}.pro-now__rail small{color:#718096;font-size:9px;margin-top:2px}
.pro-board__columns{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(280px,.62fr);gap:12px;align-items:start}.pro-plan,.pro-side__panel{background:#fff;border:1px solid #d9e1e9;border-radius:11px;overflow:hidden}.pro-plan h2,.pro-side__panel h2{margin:2px 0 0;color:#1a2e42;font-size:16px;letter-spacing:-.01em}.pro-plan__head,.pro-row{display:grid;grid-template-columns:72px minmax(240px,1.6fr) minmax(125px,.75fr) minmax(130px,.75fr) 90px 52px;gap:9px;align-items:center}.pro-plan__head{padding:7px 11px;background:#f7f9fb;border-bottom:1px solid #e6ebf0;color:#718096;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.pro-row{min-height:64px;padding:9px 11px;border-bottom:1px solid #edf0f3;border-left:4px solid #3e8569}.pro-row:last-child{border-bottom:0}.pro-row.red{border-left-color:#b9403a;background:#fffafa}.pro-row.amber{border-left-color:#c27a16}.pro-row__time{display:grid}.pro-row__time strong{font-size:14px}.pro-row__time span{color:#7a8798;font-size:9px}.pro-row__patient{display:grid;min-width:0}.pro-row__patient small{color:#6e7e91;font-size:9px}.pro-row__patient strong{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pro-row__patient>span{margin-top:2px;color:#a33f39;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pro-row__location,.pro-row__lead{display:grid;min-width:0}.pro-row__location strong,.pro-row__lead strong{font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pro-row__location span{color:#7d8998;font-size:8px}.pro-badge{display:inline-flex;border-radius:99px;padding:4px 7px;background:#e7f3ec;color:#2c684f;font-size:8px;font-weight:850;text-transform:uppercase}.pro-badge.amber{background:#fff2dc;color:#8e5a11}.pro-badge.red{background:#fbe7e5;color:#95342f}.pro-row__action{text-align:right}.pro-row__action a{display:inline-flex;padding:6px 8px;border-radius:7px;background:#edf3f7;color:#294b65;font-size:10px;font-weight:800;text-decoration:none}.pro-empty{display:grid;gap:3px;padding:22px;color:#64748b}.pro-empty strong{color:#2b4054}
.pro-side{display:grid;gap:12px}.pro-side__panel>article{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 11px;border-bottom:1px solid #edf0f3}.pro-side__panel>article:last-child{border-bottom:0}.pro-side__panel article>div{display:grid;min-width:0}.pro-side__panel article strong{font-size:12px}.pro-side__panel article span{color:#68788b;font-size:9px}.pro-side__panel article small{margin-top:3px;color:#8793a2;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pro-side__panel article a,.pro-side__panel nav a{padding:6px 8px;border-radius:7px;background:#edf3f7;color:#294b65;font-size:10px;font-weight:800;text-decoration:none;white-space:nowrap}.pro-side__clear{padding:14px;color:#357358;font-size:11px}.pro-side__panel.compact nav{display:grid;grid-template-columns:1fr;gap:6px;padding:9px}.pro-side__panel.compact nav a{background:#f6f8fa;border:1px solid #e1e7ed;padding:9px 10px}
@media(max-width:1100px){.pro-board__columns{grid-template-columns:1fr}.pro-side{grid-template-columns:1fr 1fr}.pro-board__toolbar{grid-template-columns:minmax(220px,1fr) 150px 160px auto auto}}
@media(max-width:760px){.pro-board{padding:8px}.pro-board__toolbar{grid-template-columns:1fr 1fr}.pro-board__search{grid-column:1/-1}.pro-board__toolbar .pro-button{width:100%}.pro-board__metrics{grid-template-columns:1fr 1fr}.pro-board__pulse{align-items:flex-start}.pro-board__pulse>div:first-child span:last-child{display:none}.pro-plan__head{display:none}.pro-row{grid-template-columns:56px minmax(0,1fr) auto;gap:7px}.pro-row__location,.pro-row__lead{grid-column:2}.pro-row>div:nth-child(5){grid-column:3;grid-row:1}.pro-row__action{grid-column:3;grid-row:2/4;align-self:center}.pro-side{grid-template-columns:1fr}.pro-now__rail a{min-width:205px}}
@media(max-width:480px){.pro-board__metrics article{display:grid;gap:2px}.pro-board__metrics strong{font-size:19px}.pro-row{grid-template-columns:50px minmax(0,1fr)}.pro-row>div:nth-child(5),.pro-row__action{grid-column:2}.pro-row__action{text-align:left}.pro-board__toolbar{grid-template-columns:1fr}.pro-board__search{grid-column:auto}.pro-board__pulse>div:last-child{display:none}}
`;
