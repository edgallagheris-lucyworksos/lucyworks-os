"use client";

import { useState } from "react";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import { ScheduleWarningsPanel } from "@/components/schedule-warnings-panel";
import { dayControlTimes, type ScheduledWorkBlock } from "@/lib/day-control-work";
import { useDayControlStore } from "@/lib/day-control-store";
import type { OperationalActionType, OperationalTarget } from "@/lib/operational-actions";

const columns = [
  { key: "clinician", label: "Vet / clinician", words: ["vet", "clinician", "surgeon", "consult", "theatre"] },
  { key: "anaesthesia", label: "Anaesthesia", words: ["anaes", "induction", "sedation", "mri", "ct"] },
  { key: "nurse", label: "Nurse", words: ["nurse", "nursing", "ward", "recovery", "triage"] },
  { key: "pca", label: "PCA / support", words: ["pca", "support", "kennel", "clean"] },
  { key: "admin", label: "Reception / admin", words: ["admin", "reception", "insurance", "consent", "estimate", "owner", "client"] },
  { key: "pharmacy", label: "Pharmacy / stock", words: ["pharmacy", "meds", "stock", "contrast"] },
  { key: "coordinator", label: "Coordinator", words: ["coordinator", "flow", "ops", "handover", "blocker"] },
];

function text(block: ScheduledWorkBlock) {
  return `${block.who} ${block.assignedRole || ""} ${block.what} ${block.how} ${block.where} ${block.lane} ${block.next}`.toLowerCase();
}

function columnKey(block: ScheduledWorkBlock) {
  const value = text(block);
  const found = columns.find((column) => column.words.some((word) => value.includes(word)));
  return found?.key || "coordinator";
}

function target(block: ScheduledWorkBlock): OperationalTarget {
  return { id: block.id, label: `${block.time} / ${block.subject || block.what}`, type: "scheduled_work_block", lane: block.lane, source: "staff-location-grid", ownerRole: block.assignedRole || block.who, blocker: block.blocker, nextAction: block.next, route: block.route };
}

function owner(block: ScheduledWorkBlock) {
  return block.assignedStaffName || block.assignedRole || block.who;
}

export function StaffLocationGrid() {
  const { blocks, pressure, blocked, applyAction, resetBlocks } = useDayControlStore();
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const times = dayControlTimes.filter((time) => blocks.some((block) => block.time === time));
  const visibleTimes = times.length ? times : dayControlTimes;

  function onActionComplete(item: OperationalTarget, action: OperationalActionType) {
    applyAction(String(item.id), action);
  }

  return <main className="slg"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Staff location grid</h1><p>Time down the side. People and working groups across the top. Each cell shows patient, task, location, owner, blocker and next move.</p></div><aside><b>{blocked.length}</b><small>blocked</small><button onClick={resetBlocks}>Reset</button></aside></header><section className="summary"><div><b>Pressure</b><small>{pressure.length} rows</small></div><div><b>Live blocks</b><small>{blocks.length} tasks</small></div><div><b>Truth</b><small>one work item, many filtered views</small></div></section><ScheduleWarningsPanel /><section className="gridWrap"><section className="grid" style={{ gridTemplateColumns: `84px repeat(${columns.length}, minmax(210px, 1fr))`, minWidth: `${84 + columns.length * 210}px` }}><div className="corner">Time</div>{columns.map((column) => <div className="head" key={column.key}>{column.label}</div>)}{visibleTimes.map((time) => <div className="row" key={time}><div className="time">{time}</div>{columns.map((column) => { const cell = blocks.filter((block) => block.time === time && columnKey(block) === column.key); return <div className="cell" key={`${time}-${column.key}`}>{cell.length ? cell.map((block) => <button key={block.id} className={`work ${block.status}`} onClick={() => setSelected(target(block))}><b>{block.subject || block.what}</b><span>{block.what}</span><small>{owner(block)} · {block.where}</small><em>{block.blocker !== "none" ? block.blocker : block.next}</em></button>) : <span className="empty">·</span>}</div>; })}</div>)}</section></section><section className="rule"><b>Rule:</b> staff, time and location first. Department pages are filtered views only.</section><QueueDetailDrawer target={selected} onClose={() => setSelected(null)} onActionComplete={onActionComplete} /></main>;
}

const css = `.slg{min-height:100vh;background:#020617;color:#e5e7eb;padding:12px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:16px;background:#06101f;border:1px solid #26364f;border-radius:18px;padding:14px}header span{text-transform:uppercase;letter-spacing:.16em;color:#67e8f9;font-size:11px;font-weight:900}h1{font-size:clamp(34px,5vw,70px);line-height:.9;margin:6px 0}p,small{color:#9fb0c6}aside{display:grid;gap:6px;place-items:center;min-width:120px;border:1px solid #334155;background:#0f172a;border-radius:16px;padding:10px}aside b{font-size:38px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.summary div,.rule{border:1px solid #26364f;background:#07111f;border-radius:14px;padding:10px}.summary b,.summary small{display:block}.gridWrap{max-height:76vh;overflow:auto;border:1px solid #26364f;border-radius:16px}.grid{display:grid}.corner,.head,.time,.cell{border-right:1px solid #26364f;border-bottom:1px solid #26364f;background:#07111f}.corner,.head{position:sticky;top:0;z-index:4;min-height:48px;padding:10px;background:#111827;color:#bae6fd;font-weight:900;text-transform:uppercase;font-size:11px;letter-spacing:.08em}.corner{left:0;z-index:5}.row{display:contents}.time{position:sticky;left:0;z-index:3;padding:8px;font-weight:900;color:#bae6fd;background:#0f172a}.cell{min-height:72px;padding:5px;display:grid;gap:5px;align-content:start}.empty{color:#334155}.work{display:grid;gap:2px;width:100%;border:1px solid #334155;background:#0b1220;color:#e5e7eb;border-radius:10px;padding:7px;text-align:left}.work:hover{outline:2px solid #67e8f9}.work b{font-size:12px}.work span{font-size:11px;color:#f8fafc}.work small{font-size:10px}.work em{font-style:normal;font-size:10px;color:#cbd5e1}.red{border-left:5px solid #ef4444}.amber{border-left:5px solid #f59e0b}.green{border-left:5px solid #22c55e}.blue{border-left:5px solid #38bdf8}.rule{margin-top:10px}`;
