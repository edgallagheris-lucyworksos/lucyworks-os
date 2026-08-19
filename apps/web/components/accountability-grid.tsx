"use client";

import { useMemo, useState } from "react";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import { ScheduleWarningsPanel } from "@/components/schedule-warnings-panel";
import type { OperationalActionType, OperationalTarget } from "@/lib/operational-actions";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";
import { useDayControlStore } from "@/lib/day-control-store";

function toTarget(block: ScheduledWorkBlock): OperationalTarget {
  return { id: block.id, label: `${block.time} / ${block.subject || block.what}`, type: "scheduled_work_block", lane: block.lane, source: "accountability-grid", ownerRole: block.assignedRole || block.who, blocker: block.blocker, nextAction: block.next, route: block.route };
}

function medStock(block: ScheduledWorkBlock) {
  const text = `${block.what} ${block.how} ${block.lane}`.toLowerCase();
  if (text.includes("theatre") || text.includes("surgery")) return "anaesthesia / pain plan / theatre stock";
  if (text.includes("mri") || text.includes("ct") || text.includes("imaging")) return "sedation / contrast / monitoring stock";
  if (text.includes("discharge")) return "discharge meds / label / owner instructions";
  if (text.includes("ward") || text.includes("recovery")) return "inpatient meds / fluids / observations";
  return "none logged";
}

export function AccountabilityGrid() {
  const { blocks, pressure, blocked, applyAction, resetBlocks } = useDayControlStore();
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const rows = useMemo(() => [...blocks].sort((a, b) => a.time.localeCompare(b.time) || (a.subject || a.what).localeCompare(b.subject || b.what)), [blocks]);

  function onActionComplete(target: OperationalTarget, action: OperationalActionType) {
    applyAction(String(target.id), action);
  }

  return <main className="ag"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Hospital accountability grid</h1><p>One operating table. Time is the spine. Each row shows case, place, work, owner, support, resource, medication/stock workstream, blocker and next action.</p></div><aside><b>{pressure.length}</b><small>pressure</small><button onClick={resetBlocks}>Reset</button></aside></header><section className="summary"><div><b>Now</b><small>{pressure[0]?.what || "No active pressure"}</small></div><div><b>Blocked</b><small>{blocked.length} blocked rows</small></div><div><b>Rows</b><small>{rows.length} live blocks</small></div></section><ScheduleWarningsPanel /><section className="tableWrap"><table><thead><tr><th>Time</th><th>Case</th><th>Location</th><th>Work</th><th>Accountable</th><th>Support</th><th>Resource</th><th>Meds / stock</th><th>Blocker</th><th>Next</th><th>Status</th></tr></thead><tbody>{rows.map((block) => <tr key={block.id} onClick={() => setSelected(toTarget(block))}><td className="time">{block.time}</td><td><b>{block.subject || block.what}</b><small>{block.episodeRef || block.generatedFrom || block.id}</small></td><td>{block.where}</td><td><b>{block.what}</b><small>{block.how}</small></td><td><b>{block.assignedStaffName || block.assignedRole || block.who}</b><small>{block.assignedRole || block.who}</small></td><td>{block.assignedStaffName ? block.who : "not assigned"}</td><td>{block.resourceName || block.where}</td><td>{medStock(block)}</td><td className={block.blocker !== "none" ? "bad" : "ok"}>{block.blocker}</td><td>{block.next}</td><td><span className={`status ${block.status}`}>{block.status}</span></td></tr>)}</tbody></table></section><section className="rule"><b>Rule:</b> one row per time/case/work item. No separate MRI/ward/theatre truth tables. Department pages are filtered views only.</section><QueueDetailDrawer target={selected} onClose={() => setSelected(null)} onActionComplete={onActionComplete} /></main>;
}

const css = `.ag{min-height:100vh;background:#020617;color:#e5e7eb;padding:12px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:16px;background:#06101f;border:1px solid #26364f;border-radius:18px;padding:14px}header span{text-transform:uppercase;letter-spacing:.16em;color:#67e8f9;font-size:11px;font-weight:900}h1{font-size:clamp(32px,5vw,64px);line-height:.92;margin:6px 0}p,small{color:#9fb0c6}aside{display:grid;gap:6px;place-items:center;min-width:120px;border:1px solid #334155;background:#0f172a;border-radius:16px;padding:10px}aside b{font-size:38px}button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:999px;padding:7px 10px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.summary div,.rule{border:1px solid #26364f;background:#07111f;border-radius:14px;padding:10px}.summary b,.summary small{display:block}.tableWrap{max-height:76vh;overflow:auto;border:1px solid #26364f;border-radius:16px;background:#07111f}table{border-collapse:separate;border-spacing:0;min-width:1680px;width:100%;font-size:12px}th,td{border-right:1px solid #26364f;border-bottom:1px solid #26364f;padding:8px;vertical-align:top}th{position:sticky;top:0;z-index:2;background:#111827;text-transform:uppercase;letter-spacing:.08em;color:#bae6fd;font-size:11px;text-align:left}td{background:#07111f}tr:hover td{background:#10223c;cursor:pointer}.time{position:sticky;left:0;z-index:1;background:#0f172a!important;color:#bae6fd;font-weight:900;white-space:nowrap}td b{display:block;color:#f8fafc}td small{display:block;font-size:10px}.bad{color:#fecaca}.ok{color:#bbf7d0}.status{display:inline-block;border:1px solid #334155;border-radius:999px;padding:3px 8px;text-transform:uppercase;font-weight:900}.red{border-color:#ef4444;color:#fecaca}.amber{border-color:#f59e0b;color:#fde68a}.green{border-color:#22c55e;color:#bbf7d0}.blue{border-color:#38bdf8;color:#bae6fd}.rule{margin-top:10px}@media(max-width:1100px){.summary{grid-template-columns:1fr}header{flex-direction:column}}`;
