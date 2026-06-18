"use client";

import { useEffect, useMemo, useState } from "react";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import type { OperationalActionType, OperationalTarget } from "@/lib/operational-actions";
import { dayControlLanes, dayControlTimes, scheduledWorkBlocks, type DayControlLane, type ScheduledWorkBlock } from "@/lib/day-control-work";

const STORAGE_KEY = "lucyworks.day-control.blocks.v1";

function statusClass(status: ScheduledWorkBlock["status"]) {
  return `block ${status}`;
}

function toTarget(block: ScheduledWorkBlock): OperationalTarget {
  return { id: block.id, label: `${block.time} / ${block.what}`, type: "scheduled_work_block", lane: block.lane, source: "day-control-grid", ownerRole: block.who, blocker: block.blocker, nextAction: block.next, route: block.route };
}

function blocksForSource(blocks: ScheduledWorkBlock[], time: string, lane: DayControlLane) {
  return blocks.filter((block) => block.time === time && block.lane === lane);
}

function applyAction(block: ScheduledWorkBlock, action: OperationalActionType): ScheduledWorkBlock {
  if (action === "resolve") return { ...block, status: "green", blocker: "none", next: "complete or continue planned flow" };
  if (action === "hold") return { ...block, status: "blue", blocker: "on hold", next: "review hold reason" };
  if (action === "escalate") return { ...block, status: "red", blocker: block.blocker === "none" ? "escalated" : block.blocker, next: "senior review required" };
  if (action === "request_review") return { ...block, status: "amber", next: "review requested" };
  if (action === "assign") return { ...block, status: block.status === "red" ? "red" : "amber", next: "owner assigned" };
  if (action === "handover") return { ...block, status: "green", blocker: "none", next: "handover complete" };
  if (action === "owner_update") return { ...block, status: "green", blocker: "none", next: "update recorded" };
  return { ...block, status: "amber", next: `${action.replaceAll("_", " ")} requested` };
}

export function DayControlGrid() {
  const [blocks, setBlocks] = useState<ScheduledWorkBlock[]>(scheduledWorkBlocks);
  const [selected, setSelected] = useState<OperationalTarget | null>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) setBlocks(JSON.parse(saved));
    } catch {}
  }, []);

  useEffect(() => {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(blocks)); } catch {}
  }, [blocks]);

  const pressure = useMemo(() => blocks.filter((block) => block.status === "red" || block.status === "amber" || block.blocker !== "none"), [blocks]);
  const blocked = useMemo(() => blocks.filter((block) => block.blocker !== "none"), [blocks]);
  const nextThree = pressure.slice(0, 3);
  const gridColumns = `76px repeat(${dayControlLanes.length}, minmax(150px, 1fr))`;
  const gridMinWidth = `${76 + dayControlLanes.length * 150}px`;

  function onActionComplete(target: OperationalTarget, action: OperationalActionType) {
    setBlocks((current) => current.map((block) => block.id === target.id ? applyAction(block, action) : block));
  }

  function resetLocalState() {
    setBlocks(scheduledWorkBlocks);
    try { window.localStorage.removeItem(STORAGE_KEY); } catch {}
  }

  return <div className="dcg"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Day control grid</h1><p>15-minute slots are the base. Arrivals, reception, consults, insurance/admin, procedure flow and staff pressure sit in one operating board.</p></div><aside><b>{pressure.length}</b><small>pressure rows</small><button type="button" onClick={resetLocalState}>Reset local board</button></aside></header><section className="rules"><div><b>Now</b><small>{pressure[0]?.what || "No active pressure"}</small></div><div><b>Next</b><small>{nextThree.map((block) => `${block.time} ${block.what}`).join(" / ")}</small></div><div><b>Blocked</b><small>{blocked.length} rows have blockers</small></div></section><section className="grid-wrap"><section className="grid" style={{ gridTemplateColumns: gridColumns, minWidth: gridMinWidth }}><div className="top-left">Time</div>{dayControlLanes.map((lane) => <div className="lane-head" key={lane.key}><b>{lane.label}</b><small>{lane.purpose}</small></div>)}{dayControlTimes.map((time) => <div className="row" key={time}><div className="time">{time}</div>{dayControlLanes.map((lane) => { const laneBlocks = blocksForSource(blocks, time, lane.key); return <div className="cell" key={`${time}-${lane.key}`}>{laneBlocks.length ? laneBlocks.map((block) => <button key={block.id} type="button" className={statusClass(block.status)} onClick={() => setSelected(toTarget(block))}><b>{block.what}</b><span>{block.who}</span><small>{block.where} / {block.how}</small><em>{block.blocker} → {block.next}</em></button>) : <span className="empty">·</span>}</div>; })}</div>)}</section></section><section className="bottom"><b>System rule:</b> time-grid first. Every page must be a filtered view of the generated schedule, not a separate invented board. Drawer actions update and locally persist the selected block.</section><QueueDetailDrawer target={selected} onClose={() => setSelected(null)} onActionComplete={onActionComplete} /></div>;
}

const css = `.dcg{min-height:100vh;background:#020617;color:#e5e7eb;padding:12px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:16px;background:#06101f;border:1px solid #26364f;border-radius:18px;padding:14px}header span{text-transform:uppercase;letter-spacing:.16em;color:#67e8f9;font-size:11px;font-weight:900}h1{font-size:clamp(34px,5vw,72px);line-height:.9;margin:6px 0}p,small{color:#9fb0c6}header aside{display:grid;gap:6px;place-items:center;min-width:120px;border:1px solid #334155;background:#0f172a;border-radius:16px;padding:10px}header aside b{font-size:38px}header aside button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:999px;padding:7px 10px;font-size:12px}.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.rules div,.bottom{border:1px solid #26364f;background:#07111f;border-radius:14px;padding:10px}.rules b,.rules small{display:block}.grid-wrap{max-height:72vh;overflow:auto;border:1px solid #26364f;border-radius:16px}.grid{display:grid}.top-left,.lane-head,.time,.cell{border-right:1px solid #26364f;border-bottom:1px solid #26364f;background:#07111f}.top-left,.lane-head{position:sticky;top:0;z-index:4;min-height:58px;padding:8px;background:#111827}.top-left{left:0;z-index:5}.lane-head b{display:block}.lane-head small{display:block;font-size:11px;line-height:1.15}.row{display:contents}.time{position:sticky;left:0;z-index:3;padding:8px;font-weight:900;color:#bae6fd;background:#0f172a}.cell{min-height:54px;padding:4px;display:grid;gap:4px;align-content:start}.empty{color:#334155}.block{display:grid;gap:1px;width:100%;border:1px solid #334155;background:#0b1220;color:#e5e7eb;border-radius:9px;padding:6px;text-align:left}.block:hover{outline:2px solid #67e8f9}.block b{font-size:12px}.block span{font-size:11px;color:#cbd5e1}.block small{font-size:10px}.block em{font-style:normal;color:#f8fafc;font-size:10px}.red{border-left:5px solid #ef4444}.amber{border-left:5px solid #f59e0b}.green{border-left:5px solid #22c55e}.blue{border-left:5px solid #38bdf8}.bottom{margin-top:10px}@media(max-width:1100px){.rules{grid-template-columns:1fr}header{flex-direction:column}}`;
