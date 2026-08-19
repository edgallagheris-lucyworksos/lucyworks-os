"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";
import { useOperationalContext } from "@/lib/operational-context";

type Area = { areaRef: string; name: string; areaType: string; department: string; capacity: number; turnoverMinutes: number };
type Block = { blockRef: string; episodeRef?: string; patientName?: string; procedureName: string; areaRef: string; areaName: string; startsAt: string; endsAt: string; status: string; riskLevel: string; leadStaffName?: string; leadStaffRole?: string; blockers: unknown[] };
type Episode = { episodeRef: string; patientName: string; phase: string; urgency: string; ownerRole: string; currentAreaRef?: string; nextAction?: string; status?: string };
type Conflict = { conflictRef?: string; conflictType: string; severity: string; explanation: string; primaryBlockRef?: string };
type Board = {
  generatedAt: string;
  operationalDate: string;
  premises: { premisesRef: string; name: string };
  areas: Area[];
  blocks: Block[];
  episodes: Episode[];
  conflicts: Conflict[];
  summary: { redConflicts: number; amberConflicts: number; unassignedBlocks: number; blockedBlocks: number };
  liveWindow: { blocks: Block[] };
};

const DIAGNOSTIC_TYPES = new Set(["imaging", "mri", "ct", "xray", "ultrasound", "lab"]);
const CLOSED = new Set(["closed", "discharged", "cancelled"]);
const RISK_ORDER: Record<string, number> = { red: 0, amber: 1, green: 2 };

function time(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function isBlocked(block: Block) {
  return block.status.toLowerCase() === "blocked" || block.blockers.length > 0;
}

export function HospitalCommandOverview({ onOpenPatientFlow, onOpenResourceGrid }: { onOpenPatientFlow: () => void; onOpenResourceGrid: () => void }) {
  const { premisesRef, siteName } = useOperationalContext();
  const [board, setBoard] = useState<Board | null>(null);
  const [status, setStatus] = useState("Loading live hospital state");
  const operationalDate = localOperationalDate();

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<Board>(`/api/v11/master-board/day?premises_ref=${encodeURIComponent(premisesRef)}&operational_date=${operationalDate}`);
      setBoard(data);
      setStatus("Live");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Hospital state unavailable");
    }
  }, [operationalDate, premisesRef]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const activeEpisodes = useMemo(() => board?.episodes.filter((episode) => !CLOSED.has((episode.status || "").toLowerCase())) || [], [board]);
  const priorities = useMemo(() => [...(board?.blocks || [])]
    .filter((block) => block.riskLevel === "red" || block.riskLevel === "amber" || isBlocked(block))
    .sort((left, right) => (RISK_ORDER[left.riskLevel] ?? 9) - (RISK_ORDER[right.riskLevel] ?? 9) || left.startsAt.localeCompare(right.startsAt))
    .slice(0, 8), [board]);
  const theatres = useMemo(() => board?.areas.filter((area) => area.areaType === "theatre").sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })) || [], [board]);
  const diagnostics = useMemo(() => board?.areas.filter((area) => DIAGNOSTIC_TYPES.has(area.areaType)) || [], [board]);
  const flow = useMemo(() => {
    const grouped = new Map<string, number>();
    for (const episode of activeEpisodes) grouped.set(episode.phase || "unclassified", (grouped.get(episode.phase || "unclassified") || 0) + 1);
    return [...grouped.entries()].sort((a, b) => b[1] - a[1]).slice(0, 7);
  }, [activeEpisodes]);

  if (!board) return <section className="commandOverview loading"><style>{css}</style><b>{siteName}</b><span>{status}</span><button onClick={() => void refresh()}>Retry</button></section>;

  const blocksForArea = (areaRef: string) => board.blocks.filter((block) => block.areaRef === areaRef && !["cancelled", "completed"].includes(block.status.toLowerCase()));
  const configurationWarning = theatres.length !== 4 ? `Hospital configuration shows ${theatres.length} theatres; expected 4.` : null;

  return <main className="commandOverview">
    <style>{css}</style>
    <header className="overviewTitle">
      <div><span>Hospital command overview</span><h2>Today’s operating position</h2><p>{board.premises.name} · {board.operationalDate} · one authenticated master-board projection</p></div>
      <div className="overviewActions"><span className={status === "Live" ? "live" : "warning"}>{status}</span><button onClick={() => void refresh()}>Refresh</button><button className="primary" onClick={onOpenPatientFlow}>Open patient flow</button><button onClick={onOpenResourceGrid}>Resource grid</button></div>
    </header>

    {configurationWarning ? <section className="configurationWarning"><b>Configuration mismatch</b><span>{configurationWarning}</span></section> : null}

    <section className="position" aria-label="Current hospital position">
      <article><span>Patients on site</span><strong>{activeEpisodes.length}</strong><small>active episodes</small></article>
      <article className={board.summary.redConflicts ? "critical" : ""}><span>Red conflicts</span><strong>{board.summary.redConflicts}</strong><small>immediate intervention</small></article>
      <article className={board.summary.blockedBlocks ? "warning" : ""}><span>Blocked work</span><strong>{board.summary.blockedBlocks}</strong><small>cannot progress</small></article>
      <article className={board.summary.unassignedBlocks ? "warning" : ""}><span>Unassigned work</span><strong>{board.summary.unassignedBlocks}</strong><small>owner required</small></article>
      <article><span>Next 90 minutes</span><strong>{board.liveWindow.blocks.length}</strong><small>live scheduled blocks</small></article>
    </section>

    <section className="primaryGrid">
      <article className="panel priorities">
        <header><div><h3>Priority interventions</h3><p>Highest operational risk first</p></div><button onClick={onOpenPatientFlow}>View patients</button></header>
        <div className="priorityHead"><span>Time</span><span>Patient / work</span><span>Location</span><span>Owner</span></div>
        {priorities.length ? priorities.map((block) => <div className="priorityRow" data-risk={block.riskLevel} key={block.blockRef}>
          <time>{time(block.startsAt)}</time>
          <span><b>{block.patientName || "Operational work"}</b><small>{block.procedureName}</small></span>
          <span><b>{block.areaName}</b><small>{isBlocked(block) ? "Blocked" : block.status}</small></span>
          <span><b>{block.leadStaffName || block.leadStaffRole || "Unassigned"}</b><small>{block.riskLevel} priority</small></span>
        </div>) : <p className="clearState">No current red or amber operational interventions.</p>}
      </article>

      <article className="panel">
        <header><div><h3>Patient flow</h3><p>Active episodes by stage</p></div></header>
        <div className="flowRows">{flow.map(([phase, count]) => <div key={phase}><span>{phase.replaceAll("_", " ")}</span><strong>{count}</strong></div>)}</div>
      </article>
    </section>

    <section className="resourceGrid">
      <article className="panel">
        <header><div><h3>Theatre capacity</h3><p>Configured operating rooms</p></div></header>
        <div className="resourceRows">{theatres.map((area) => {
          const work = blocksForArea(area.areaRef);
          const next = [...work].sort((a, b) => a.startsAt.localeCompare(b.startsAt))[0];
          const blocked = work.filter(isBlocked).length;
          return <div key={area.areaRef} className={blocked ? "hasRisk" : ""}><span><b>{area.name}</b><small>{next ? `${time(next.startsAt)} · ${next.patientName || next.procedureName}` : "Available / unallocated"}</small></span><strong>{work.length}</strong><em>{blocked ? `${blocked} blocked` : "scheduled"}</em></div>;
        })}</div>
      </article>

      <article className="panel">
        <header><div><h3>Diagnostics</h3><p>Imaging and laboratory queues</p></div></header>
        <div className="resourceRows">{diagnostics.map((area) => {
          const work = blocksForArea(area.areaRef);
          const blocked = work.filter(isBlocked).length;
          return <div key={area.areaRef} className={blocked ? "hasRisk" : ""}><span><b>{area.name}</b><small>{area.department}</small></span><strong>{work.length}</strong><em>{blocked ? `${blocked} blocked` : "queued"}</em></div>;
        })}</div>
      </article>
    </section>

    <footer><span>Generated {new Date(board.generatedAt).toLocaleString()}</span><b>Source: authenticated v11 hospital master board</b></footer>
  </main>;
}

const css = `
.commandOverview{display:grid;gap:10px;padding:12px 18px 28px;background:#eef2f7;color:#182c3f}.commandOverview.loading{margin:12px 18px;padding:18px;background:#fff;border:1px solid #d8e0e8;border-radius:10px;grid-template-columns:1fr auto auto;align-items:center}.commandOverview button{min-height:32px;padding:6px 9px;border:1px solid #cad5df;border-radius:6px;background:#fff;color:#294a64;font-size:10px;font-weight:800}.commandOverview button.primary{background:#173f5f;border-color:#173f5f;color:#fff}.overviewTitle{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:13px 15px;background:#fff;border:1px solid #d8e0e8;border-radius:10px}.overviewTitle>div:first-child>span{color:#42657f;font-size:9px;font-weight:850;text-transform:uppercase;letter-spacing:.08em}.overviewTitle h2{margin:3px 0 0;font-size:21px;letter-spacing:-.025em;color:#17344e}.overviewTitle p{margin:4px 0 0;color:#718092;font-size:10px}.overviewActions{display:flex;align-items:center;gap:5px}.overviewActions>span{padding:5px 7px;border-radius:99px;font-size:8px;font-weight:850;text-transform:uppercase}.overviewActions .live{background:#e3f2ea;color:#28674d}.overviewActions .warning{background:#fff0da;color:#8c5a12}.configurationWarning{display:flex;gap:10px;padding:9px 11px;border:1px solid #e4bc75;border-left:4px solid #c77c14;border-radius:8px;background:#fff8eb;color:#704b18;font-size:10px}
.position{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.position article{display:grid;grid-template-columns:1fr auto;gap:2px 8px;padding:9px 11px;background:#fff;border:1px solid #d8e0e8;border-left:4px solid #64859d;border-radius:9px}.position article.warning{border-left-color:#c77c14}.position article.critical{border-left-color:#b63c38}.position span{font-size:8px;text-transform:uppercase;letter-spacing:.05em;color:#65778a;font-weight:800}.position strong{grid-row:1/3;grid-column:2;font-size:24px;color:#17344e}.position small{font-size:8px;color:#7b8998}
.primaryGrid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,.6fr);gap:10px}.resourceGrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.panel{background:#fff;border:1px solid #d8e0e8;border-radius:10px;overflow:hidden}.panel>header{display:flex;justify-content:space-between;align-items:center;padding:9px 11px;border-bottom:1px solid #e2e8ee}.panel h3{margin:0;font-size:13px;color:#17344e}.panel header p{margin:2px 0 0;font-size:8px;color:#748394}
.priorityHead,.priorityRow{display:grid;grid-template-columns:48px minmax(170px,1.3fr) minmax(120px,.8fr) minmax(120px,.8fr);gap:8px;align-items:center;padding:7px 9px}.priorityHead{background:#f1f5f8;color:#687a8c;font-size:8px;font-weight:850;text-transform:uppercase}.priorityRow{border-bottom:1px solid #e8edf1;font-size:10px}.priorityRow[data-risk=red]{border-left:4px solid #b73d39}.priorityRow[data-risk=amber]{border-left:4px solid #cc8319}.priorityRow time{font-weight:850;color:#294f6b}.priorityRow b{display:block}.priorityRow small{display:block;margin-top:2px;color:#788697;font-size:8px}.clearState{padding:14px;color:#547064;font-size:10px}
.flowRows>div{display:flex;justify-content:space-between;gap:10px;padding:9px 10px;border-bottom:1px solid #e8edf1}.flowRows span{font-size:10px;text-transform:capitalize}.flowRows strong{color:#17344e}
.resourceRows{display:grid;grid-template-columns:1fr 1fr}.resourceRows>div{display:grid;grid-template-columns:1fr auto;gap:2px 8px;padding:10px;border-right:1px solid #e8edf1;border-bottom:1px solid #e8edf1;border-left:3px solid #5d839d}.resourceRows>div.hasRisk{border-left-color:#b63c38}.resourceRows b{display:block;font-size:10px}.resourceRows small{display:block;margin-top:2px;color:#7a8897;font-size:8px}.resourceRows strong{font-size:17px}.resourceRows em{grid-column:2;font-size:8px;font-style:normal;color:#63788b}.commandOverview footer{display:flex;justify-content:space-between;padding:8px 10px;border:1px solid #d5dee6;border-radius:8px;background:#f8fafb;color:#69798a;font-size:8px}
@media(max-width:980px){.position{grid-template-columns:repeat(3,1fr)}.primaryGrid{grid-template-columns:1fr}.resourceGrid{grid-template-columns:1fr}.overviewTitle{align-items:flex-start}}
@media(max-width:600px){.commandOverview{padding:8px}.overviewTitle{display:grid}.position{grid-template-columns:1fr 1fr}.position article:last-child{display:none}.priorityHead{display:none}.priorityRow{grid-template-columns:42px 1fr}.priorityRow>span:nth-child(n+3){grid-column:2}.resourceRows{grid-template-columns:1fr}.overviewActions{overflow-x:auto}.commandOverview footer{display:grid;gap:3px}}
`;
