"use client";

import { useMemo, useState } from "react";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import { ScheduleWarningsPanel } from "@/components/schedule-warnings-panel";
import { pharmacyLabels, procedureForWork } from "@/lib/clinical-catalogue";
import { dayControlTimes, type ScheduledWorkBlock } from "@/lib/day-control-work";
import { useDayControlStore } from "@/lib/day-control-store";
import type { OperationalActionType, OperationalTarget } from "@/lib/operational-actions";

const columns = [
  { key: "clinician", label: "Vet / clinician", words: ["vet", "clinician", "surgeon", "consult", "theatre"] },
  { key: "anaesthesia", label: "Anaesthesia", words: ["anaes", "anaesthesia", "anesthesia", "induction", "sedation", "mri", "ct"] },
  { key: "nurse", label: "Nurse", words: ["nurse", "nursing", "ward", "recovery", "triage"] },
  { key: "pca", label: "PCA / support", words: ["pca", "support", "kennel", "clean"] },
  { key: "admin", label: "Reception / admin", words: ["admin", "reception", "insurance", "consent", "estimate", "owner", "client"] },
  { key: "pharmacy", label: "Pharmacy / stock", words: ["pharmacy", "meds", "medication", "stock", "contrast", "drug"] },
  { key: "coordinator", label: "Coordinator", words: ["coordinator", "flow", "ops", "handover", "blocker"] },
] as const;

type ColumnKey = (typeof columns)[number]["key"];
type LocationViewKey = "mri" | "theatre" | "ward";
type ViewKey = "all" | "blocked" | ColumnKey | LocationViewKey;

const views: { key: ViewKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "blocked", label: "Blocked" },
  { key: "clinician", label: "Vets" },
  { key: "anaesthesia", label: "Anaesthesia" },
  { key: "nurse", label: "Nurses" },
  { key: "pca", label: "PCA" },
  { key: "admin", label: "Admin" },
  { key: "pharmacy", label: "Pharmacy" },
  { key: "coordinator", label: "Coordinator" },
  { key: "mri", label: "MRI" },
  { key: "theatre", label: "Theatre" },
  { key: "ward", label: "Ward" },
];

function roleText(block: ScheduledWorkBlock) {
  return `${block.assignedRole || ""} ${block.who || ""}`.toLowerCase();
}

function fullText(block: ScheduledWorkBlock) {
  return `${roleText(block)} ${block.what} ${block.how} ${block.where} ${block.lane} ${block.next}`.toLowerCase();
}

function findColumnByText(value: string) {
  return columns.find((column) => column.words.some((word) => value.includes(word)))?.key;
}

function columnKey(block: ScheduledWorkBlock): ColumnKey {
  const roleMatch = findColumnByText(roleText(block));
  if (roleMatch) return roleMatch;
  return findColumnByText(fullText(block)) || "coordinator";
}

function target(block: ScheduledWorkBlock): OperationalTarget {
  return { id: block.id, label: `${block.time} / ${block.subject || block.what}`, type: "scheduled_work_block", lane: block.lane, source: "staff-location-grid", ownerRole: block.assignedRole || block.who, blocker: block.blocker, nextAction: block.next, route: block.route };
}

function owner(block: ScheduledWorkBlock) {
  return block.assignedStaffName || block.assignedRole || block.who;
}

function hasOwner(block: ScheduledWorkBlock) {
  return Boolean(owner(block)?.trim());
}

function hasLocation(block: ScheduledWorkBlock) {
  return Boolean(block.where?.trim());
}

function hasNext(block: ScheduledWorkBlock) {
  return Boolean(block.next?.trim());
}

function integrityClass(block: ScheduledWorkBlock) {
  if (!hasOwner(block) || !hasLocation(block) || !hasNext(block)) return " integrity";
  return "";
}

function movement(block: ScheduledWorkBlock) {
  const next = block.next.toLowerCase();
  if (next.includes("mri")) return "→ MRI";
  if (next.includes("ct")) return "→ CT";
  if (next.includes("theatre")) return "→ theatre";
  if (next.includes("ward")) return "→ ward";
  if (next.includes("owner") || next.includes("client")) return "→ client";
  return block.next;
}

function clinicalLine(block: ScheduledWorkBlock) {
  const procedure = procedureForWork(block.what, block.lane);
  if (!procedure) return "procedure: not templated";
  return `${procedure.label} · ${procedure.defaultMinutes}m · ${procedure.resourceType}`;
}

function pharmacyLine(block: ScheduledWorkBlock) {
  const procedure = procedureForWork(block.what, block.lane);
  if (!procedure || procedure.pharmacyRefs.length === 0) return "pharmacy: none";
  return `pharmacy: ${pharmacyLabels(procedure.pharmacyRefs).join(" / ")}`;
}

function viewColumns(view: ViewKey) {
  if (view === "all" || view === "blocked" || view === "mri" || view === "theatre" || view === "ward") return columns;
  return columns.filter((column) => column.key === view);
}

function blockVisible(block: ScheduledWorkBlock, view: ViewKey) {
  const text = fullText(block);
  if (view === "all") return true;
  if (view === "blocked") return block.blocker !== "none" || !hasOwner(block) || !hasLocation(block) || !hasNext(block);
  if (view === "mri") return text.includes("mri");
  if (view === "theatre") return text.includes("theatre") || text.includes("surgery") || text.includes("surgical");
  if (view === "ward") return text.includes("ward") || text.includes("recovery") || text.includes("kennel");
  return columnKey(block) === view;
}

export function StaffLocationGrid() {
  const { blocks, pressure, blocked, applyAction, resetBlocks } = useDayControlStore();
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const [view, setView] = useState<ViewKey>("all");
  const filteredBlocks = useMemo(() => blocks.filter((block) => blockVisible(block, view)), [blocks, view]);
  const visibleColumns = viewColumns(view);
  const timesWithWork = dayControlTimes.filter((time) => filteredBlocks.some((block) => block.time === time));
  const visibleTimes = timesWithWork.length ? timesWithWork : dayControlTimes;
  const integrityWarnings = blocks.filter((block) => !hasOwner(block) || !hasLocation(block) || !hasNext(block)).length;

  function onActionComplete(item: OperationalTarget, action: OperationalActionType) {
    applyAction(String(item.id), action);
  }

  return <main className="slg"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Staff location grid</h1><p>Time down the side. People and working groups across the top. Cells show patient, task, owner, location, procedure, pharmacy, blocker and next physical move.</p></div><aside><b>{blocked.length + integrityWarnings}</b><small>blocked / incomplete</small><button onClick={resetBlocks}>Reset</button></aside></header><nav>{views.map((item) => <button key={item.key} className={view === item.key ? "active" : ""} onClick={() => setView(item.key)}>{item.label}</button>)}</nav><section className="summary"><div><b>Pressure</b><small>{pressure.length} rows</small></div><div><b>Visible</b><small>{filteredBlocks.length} tasks</small></div><div><b>Integrity</b><small>{integrityWarnings} missing owner/location/next</small></div></section><ScheduleWarningsPanel /><section className="gridWrap"><section className="grid" style={{ gridTemplateColumns: `84px repeat(${visibleColumns.length}, minmax(235px, 1fr))`, minWidth: `${84 + visibleColumns.length * 235}px` }}><div className="corner">Time</div>{visibleColumns.map((column) => <div className="head" key={column.key}>{column.label}</div>)}{visibleTimes.map((time) => <div className="row" key={time}><div className="time">{time}</div>{visibleColumns.map((column) => { const cell = filteredBlocks.filter((block) => block.time === time && columnKey(block) === column.key); return <div className="cell" key={`${time}-${column.key}`}>{cell.length ? cell.map((block) => <button key={block.id} className={`work ${block.status}${integrityClass(block)}`} onClick={() => setSelected(target(block))}><b>{block.subject || block.what}</b><span>{block.what}</span><small>{owner(block) || "NO OWNER"} · {block.where || "NO LOCATION"}</small><small className="clinical">{clinicalLine(block)}</small><small className="clinical">{pharmacyLine(block)}</small><em>{block.blocker !== "none" ? block.blocker : movement(block)}</em></button>) : <span className="empty">·</span>}</div>; })}</div>)}</section></section><section className="rule"><b>Rule:</b> staff, time and location first. MRI/theatre/ward buttons are filters of the same work items, not duplicate boards. Missing owner, location or next action is unsafe.</section><QueueDetailDrawer target={selected} onClose={() => setSelected(null)} onActionComplete={onActionComplete} /></main>;
}

const css = `.slg{min-height:100vh;background:#020617;color:#e5e7eb;padding:12px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:16px;background:#06101f;border:1px solid #26364f;border-radius:18px;padding:14px}header span{text-transform:uppercase;letter-spacing:.16em;color:#67e8f9;font-size:11px;font-weight:900}h1{font-size:clamp(34px,5vw,70px);line-height:.9;margin:6px 0}p,small{color:#9fb0c6}aside{display:grid;gap:6px;place-items:center;min-width:120px;border:1px solid #334155;background:#0f172a;border-radius:16px;padding:10px}aside b{font-size:38px}button{font:inherit}nav{display:flex;gap:6px;overflow:auto;margin:10px 0}nav button,aside button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:999px;padding:7px 10px;white-space:nowrap}nav button.active{background:#0e7490;color:white;border-color:#67e8f9}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.summary div,.rule{border:1px solid #26364f;background:#07111f;border-radius:14px;padding:10px}.summary b,.summary small{display:block}.gridWrap{max-height:76vh;overflow:auto;border:1px solid #26364f;border-radius:16px}.grid{display:grid}.corner,.head,.time,.cell{border-right:1px solid #26364f;border-bottom:1px solid #26364f;background:#07111f}.corner,.head{position:sticky;top:0;z-index:4;min-height:48px;padding:10px;background:#111827;color:#bae6fd;font-weight:900;text-transform:uppercase;font-size:11px;letter-spacing:.08em}.corner{left:0;z-index:5}.row{display:contents}.time{position:sticky;left:0;z-index:3;padding:8px;font-weight:900;color:#bae6fd;background:#0f172a}.cell{min-height:92px;padding:5px;display:grid;gap:5px;align-content:start}.empty{color:#334155}.work{display:grid;gap:2px;width:100%;border:1px solid #334155;background:#0b1220;color:#e5e7eb;border-radius:10px;padding:7px;text-align:left}.work:hover{outline:2px solid #67e8f9}.work b{font-size:12px}.work span{font-size:11px;color:#f8fafc}.work small{font-size:10px}.work .clinical{color:#a5f3fc}.work em{font-style:normal;font-size:10px;color:#cbd5e1}.red{border-left:5px solid #ef4444}.amber{border-left:5px solid #f59e0b}.green{border-left:5px solid #22c55e}.blue{border-left:5px solid #38bdf8}.integrity{box-shadow:inset 0 0 0 2px #ef4444}.rule{margin-top:10px}@media(max-width:1100px){.summary{grid-template-columns:1fr}header{flex-direction:column}}`;
