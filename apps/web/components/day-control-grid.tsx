"use client";

import { useState } from "react";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import type { OperationalTarget } from "@/lib/operational-actions";
import { blocksFor, dayControlLanes, dayControlTimes, pressureBlocks, type ScheduledWorkBlock } from "@/lib/day-control-work";

function statusClass(status: ScheduledWorkBlock["status"]) {
  return `block ${status}`;
}

function toTarget(block: ScheduledWorkBlock): OperationalTarget {
  return {
    id: block.id,
    label: `${block.time} / ${block.what}`,
    type: "scheduled_work_block",
    lane: block.lane,
    source: "day-control-grid",
    ownerRole: block.who,
    blocker: block.blocker,
    nextAction: block.next,
    route: block.route,
  };
}

export function DayControlGrid() {
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const pressure = pressureBlocks();

  return <div className="dcg"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Day control grid</h1><p>Time slots are the base. Each cell shows who, what, where, when, how, blocker and next action.</p></div><aside><b>{pressure.length}</b><small>pressure rows</small></aside></header><section className="rules"><div><b>One place</b><small>The whole day is visible in a single grid.</small></div><div><b>Every cell has meaning</b><small>Who / what / where / how / blocker / next.</small></div><div><b>Click, do not hunt</b><small>Click any block to route, assign, hold, review or complete.</small></div></section><section className="grid"><div className="top-left">Time</div>{dayControlLanes.map((lane) => <div className="lane-head" key={lane.key}><b>{lane.label}</b><small>{lane.purpose}</small></div>)}{dayControlTimes.map((time) => <div className="row" key={time}><div className="time">{time}</div>{dayControlLanes.map((lane) => { const blocks = blocksFor(time, lane.key); return <div className="cell" key={`${time}-${lane.key}`}>{blocks.length ? blocks.map((block) => <button key={block.id} type="button" className={statusClass(block.status)} onClick={() => setSelected(toTarget(block))}><b>{block.what}</b><span>{block.who}</span><small>{block.where}</small><small>{block.how}</small><em>{block.blocker} → {block.next}</em></button>) : <span className="empty">—</span>}</div>; })}</div> )}</section><section className="bottom"><b>Presentation rule:</b> this grid is the base layer. Department pages, staff views and client-contact work must be filtered versions of these blocks, not separate invented pages.</section><QueueDetailDrawer target={selected} onClose={() => setSelected(null)} /></div>;
}

const css = `.dcg{min-height:100vh;background:#020617;color:#e5e7eb;padding:14px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:16px;background:#06101f;border:1px solid #26364f;border-radius:22px;padding:18px}header span{text-transform:uppercase;letter-spacing:.16em;color:#67e8f9;font-size:12px;font-weight:900}h1{font-size:clamp(42px,7vw,88px);line-height:.86;margin:8px 0}p,small{color:#9fb0c6}header aside{display:grid;place-items:center;min-width:140px;border:1px solid #334155;background:#0f172a;border-radius:18px;padding:14px}header aside b{font-size:44px}.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0}.rules div,.bottom{border:1px solid #26364f;background:#07111f;border-radius:16px;padding:12px}.rules b,.rules small{display:block}.grid{min-width:1480px;border:1px solid #26364f;border-radius:18px;overflow:hidden}.top-left,.lane-head,.time,.cell{border-right:1px solid #26364f;border-bottom:1px solid #26364f;background:#07111f}.top-left,.lane-head{min-height:72px;padding:10px;background:#111827}.grid{display:grid;grid-template-columns:80px repeat(9,minmax(150px,1fr))}.row{display:contents}.time{padding:10px;font-weight:900;color:#bae6fd;background:#0f172a}.cell{min-height:104px;padding:7px;display:grid;gap:6px;align-content:start}.empty{color:#475569}.block{display:grid;gap:3px;width:100%;border:1px solid #334155;background:#0b1220;color:#e5e7eb;border-radius:12px;padding:8px;text-align:left}.block:hover{outline:2px solid #67e8f9}.block span{font-size:12px;color:#cbd5e1}.block em{font-style:normal;color:#f8fafc;font-size:12px}.red{border-left:5px solid #ef4444}.amber{border-left:5px solid #f59e0b}.green{border-left:5px solid #22c55e}.blue{border-left:5px solid #38bdf8}.bottom{margin-top:12px}@media(max-width:1100px){.rules{grid-template-columns:1fr}header{flex-direction:column}.grid{min-width:1400px}}`;
