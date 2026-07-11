"use client";

import { useMemo, useState } from "react";
import { GovernanceGatesPanel } from "@/components/governance-gates-panel";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import { QuickAssignmentStrip } from "@/components/quick-assignment-strip";
import { ReferralPathwayGenerator } from "@/components/referral-pathway-generator";
import { ScheduleWarningsPanel } from "@/components/schedule-warnings-panel";
import { pharmacyLabels, procedureForWork, protectedTimeLabel } from "@/lib/clinical-catalogue";
import { dayControlTimes, type ScheduledWorkBlock } from "@/lib/day-control-work";
import { useDayControlStore } from "@/lib/day-control-store";
import type { OperationalActionType, OperationalTarget } from "@/lib/operational-actions";

const columns = [
  { key: "clinician", label: "Vet / clinician", words: ["vet", "clinician", "surgeon", "consult", "theatre"] },
  { key: "imaging", label: "Imaging", words: ["imaging", "mri", "ct", "scan", "radiography", "ultrasound"] },
  { key: "anaesthesia", label: "Anaesthesia", words: ["anaes", "anaesthesia", "anesthesia", "induction", "sedation"] },
  { key: "nurse", label: "Nurse", words: ["nurse", "nursing", "ward", "recovery", "triage"] },
  { key: "pca", label: "PCA / support", words: ["pca", "support", "kennel", "clean"] },
  { key: "admin", label: "Reception / admin", words: ["admin", "reception", "insurance", "consent", "estimate", "owner", "client"] },
  { key: "pharmacy", label: "Pharmacy / stock", words: ["pharmacy", "meds", "medication", "stock", "contrast", "drug"] },
  { key: "coordinator", label: "Coordinator", words: ["coordinator", "flow", "ops", "handover", "blocker"] },
] as const;

type ColumnKey = (typeof columns)[number]["key"];
type LocationViewKey = "mri" | "theatre" | "ward";
type ViewKey = "all" | "blocked" | ColumnKey | LocationViewKey;
type BoardMode = "role" | "person";
type DisplayColumn = { key: string; label: string; roleKey?: ColumnKey; kind: "role" | "person" | "unassigned" };

const views: { key: ViewKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "blocked", label: "Blocked" },
  { key: "clinician", label: "Vets" },
  { key: "imaging", label: "Imaging" },
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

function safe(value: string | number | null | undefined) {
  return String(value || "").trim();
}

function roleText(block: ScheduledWorkBlock) {
  return `${safe(block.assignedRole)} ${safe(block.who)}`.toLowerCase();
}

function fullText(block: ScheduledWorkBlock) {
  return `${roleText(block)} ${safe(block.what)} ${safe(block.how)} ${safe(block.where)} ${safe(block.lane)} ${safe(block.next)}`.toLowerCase();
}

function findColumnByText(value: string) {
  return columns.find((column) => column.words.some((word) => value.includes(word)))?.key;
}

function roleColumn(key: ColumnKey) {
  return columns.find((column) => column.key === key) || columns[columns.length - 1];
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
  const next = safe(block.next).toLowerCase();
  if (next.includes("mri")) return "-> MRI";
  if (next.includes("ct")) return "-> CT";
  if (next.includes("theatre")) return "-> theatre";
  if (next.includes("ward")) return "-> ward";
  if (next.includes("owner") || next.includes("client")) return "-> client";
  return safe(block.next) || "NO NEXT ACTION";
}

function procedure(block: ScheduledWorkBlock) {
  return procedureForWork(`${block.what} ${block.how} ${block.where} ${block.next}`, block.lane);
}

function hasPharmacyDependency(block: ScheduledWorkBlock) {
  return Boolean(procedure(block)?.pharmacyRefs.length);
}

function clinicalLine(block: ScheduledWorkBlock) {
  const item = procedure(block);
  if (!item) return "procedure: not templated";
  return protectedTimeLabel(item);
}

function pharmacyLine(block: ScheduledWorkBlock) {
  const item = procedure(block);
  if (!item || item.pharmacyRefs.length === 0) return "pharmacy: none";
  return `pharmacy: ${pharmacyLabels(item.pharmacyRefs).join(" / ")}`;
}

function roleViewColumns(view: ViewKey): DisplayColumn[] {
  if (view === "all" || view === "blocked" || view === "mri" || view === "theatre" || view === "ward") return columns.map((column) => ({ key: column.key, label: column.label, roleKey: column.key, kind: "role" }));
  return columns.filter((column) => column.key === view).map((column) => ({ key: column.key, label: column.label, roleKey: column.key, kind: "role" }));
}

function personColumnKey(block: ScheduledWorkBlock) {
  const named = safe(block.assignedStaffName);
  if (named) return `person:${safe(block.assignedStaffId) || named.toLowerCase()}`;
  const role = columnKey(block);
  return `unassigned:${role}`;
}

function personColumnLabel(block: ScheduledWorkBlock) {
  const named = safe(block.assignedStaffName);
  if (named) return named;
  return `Unassigned ${roleColumn(columnKey(block)).label}`;
}

function personViewColumns(blocks: ScheduledWorkBlock[]): DisplayColumn[] {
  const map = new Map<string, DisplayColumn>();
  for (const block of blocks) {
    const key = personColumnKey(block);
    if (!map.has(key)) map.set(key, { key, label: personColumnLabel(block), roleKey: columnKey(block), kind: key.startsWith("person:") ? "person" : "unassigned" });
  }
  return Array.from(map.values()).sort((a, b) => Number(a.kind !== "person") - Number(b.kind !== "person") || a.label.localeCompare(b.label));
}

function blockVisible(block: ScheduledWorkBlock, view: ViewKey) {
  const text = fullText(block);
  const blocker = safe(block.blocker) || "none";
  if (view === "all") return true;
  if (view === "blocked") return blocker.toLowerCase() !== "none" || !hasOwner(block) || !hasLocation(block) || !hasNext(block);
  if (view === "mri") return text.includes("mri");
  if (view === "theatre") return text.includes("theatre") || text.includes("surgery") || text.includes("surgical");
  if (view === "ward") return text.includes("ward") || text.includes("recovery") || text.includes("kennel");
  if (view === "pharmacy") return columnKey(block) === "pharmacy" || hasPharmacyDependency(block);
  return columnKey(block) === view;
}

function cellBlocks(blocks: ScheduledWorkBlock[], time: string, column: DisplayColumn, view: ViewKey, mode: BoardMode) {
  if (mode === "person") return blocks.filter((block) => block.time === time && personColumnKey(block) === column.key);
  if (view === "pharmacy" && column.roleKey === "pharmacy") return blocks.filter((block) => block.time === time && (columnKey(block) === "pharmacy" || hasPharmacyDependency(block)));
  return blocks.filter((block) => block.time === time && columnKey(block) === column.roleKey);
}

export function StaffLocationGrid() {
  const { blocks, pressure, blocked, addBlocks, assignBlock, clearAssignment, applyAction, resetBlocks, syncStatus } = useDayControlStore();
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const [view, setView] = useState<ViewKey>("all");
  const [mode, setMode] = useState<BoardMode>("person");
  const filteredBlocks = useMemo(() => blocks.filter((block) => blockVisible(block, view)), [blocks, view]);
  const visibleColumns = useMemo(() => mode === "person" ? personViewColumns(filteredBlocks) : roleViewColumns(view), [filteredBlocks, mode, view]);
  const timesWithWork = dayControlTimes.filter((time) => filteredBlocks.some((block) => block.time === time));
  const visibleTimes = timesWithWork.length ? timesWithWork : dayControlTimes;
  const integrityWarnings = blocks.filter((block) => !hasOwner(block) || !hasLocation(block) || !hasNext(block)).length;
  const namedPeople = blocks.filter((block) => safe(block.assignedStaffName)).length;

  function onActionComplete(item: OperationalTarget, action: OperationalActionType) {
    applyAction(String(item.id), action);
  }

  function workCard(block: ScheduledWorkBlock) {
    const blocker = safe(block.blocker) || "none";
    return <div key={block.id} className="workcard"><button type="button" className={`work ${block.status}${integrityClass(block)}`} onClick={() => setSelected(target(block))}><b>{block.subject || block.what}</b><span>{block.what}</span><small>{owner(block) || "NO OWNER"} - {block.where || "NO LOCATION"}</small><small className="clinical">{clinicalLine(block)}</small><small className="clinical">{pharmacyLine(block)}</small><em>{blocker.toLowerCase() !== "none" ? blocker : movement(block)}</em></button><QuickAssignmentStrip block={block} blocks={blocks} onAssign={assignBlock} onClear={clearAssignment} /></div>;
  }

  return <main className="slg"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Staff location grid</h1><p>Time down the side. People mode shows named staff columns first, then unassigned role columns. Role mode keeps the old operational group view.</p></div><aside><b>{blocked.length + integrityWarnings}</b><small>blocked / incomplete</small><button onClick={resetBlocks}>Reset</button></aside></header><ReferralPathwayGenerator onGenerate={addBlocks} syncStatus={syncStatus} /><section className="modebar"><button className={mode === "person" ? "active" : ""} onClick={() => setMode("person")}>People columns</button><button className={mode === "role" ? "active" : ""} onClick={() => setMode("role")}>Role columns</button><small>{namedPeople} named assignments - unassigned work stays visible</small></section><nav>{views.map((item) => <button key={item.key} className={view === item.key ? "active" : ""} onClick={() => setView(item.key)}>{item.label}</button>)}</nav><section className="summary"><div><b>Pressure</b><small>{pressure.length} rows</small></div><div><b>Visible</b><small>{filteredBlocks.length} tasks</small></div><div><b>Integrity</b><small>{integrityWarnings} missing owner/location/next</small></div></section><ScheduleWarningsPanel /><GovernanceGatesPanel /><section className="gridWrap"><section className="grid" style={{ gridTemplateColumns: `84px repeat(${Math.max(visibleColumns.length, 1)}, minmax(235px, 1fr))`, minWidth: `${84 + Math.max(visibleColumns.length, 1) * 235}px` }}><div className="corner">Time</div>{visibleColumns.length ? visibleColumns.map((column) => <div className={`head ${column.kind}`} key={column.key}>{column.label}</div>) : <div className="head">No visible work</div>}{visibleTimes.map((time) => <div className="row" key={time}><div className="time">{time}</div>{visibleColumns.length ? visibleColumns.map((column) => { const cell = cellBlocks(filteredBlocks, time, column, view, mode); return <div className="cell" key={`${time}-${column.key}`}>{cell.length ? cell.map(workCard) : <span className="empty">.</span>}</div>; }) : <div className="cell"><span className="empty">.</span></div>}</div>)}</section></section><section className="rule"><b>Rule:</b> person first. A named person column shows real capacity. Governance gates stop unsafe referral flow: consent, estimate, pharmacy, owner update and referring-vet report must be clear.</section><QueueDetailDrawer target={selected} onClose={() => setSelected(null)} onActionComplete={onActionComplete} /></main>;
}

const css = `.slg{min-height:100vh;background:#020617;color:#e5e7eb;padding:12px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:16px;background:#06101f;border:1px solid #26364f;border-radius:18px;padding:14px}header span{text-transform:uppercase;letter-spacing:.16em;color:#67e8f9;font-size:11px;font-weight:900}h1{font-size:clamp(34px,5vw,70px);line-height:.9;margin:6px 0}p,small{color:#9fb0c6}aside{display:grid;gap:6px;place-items:center;min-width:120px;border:1px solid #334155;background:#0f172a;border-radius:16px;padding:10px}aside b{font-size:38px}button{font:inherit}.modebar,nav{display:flex;gap:6px;overflow:auto;margin:10px 0;align-items:center}.modebar button,nav button,aside button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:999px;padding:7px 10px;white-space:nowrap}.modebar button.active,nav button.active{background:#0e7490;color:white;border-color:#67e8f9}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.summary div,.rule{border:1px solid #26364f;background:#07111f;border-radius:14px;padding:10px}.summary b,.summary small{display:block}.gridWrap{max-height:76vh;overflow:auto;border:1px solid #26364f;border-radius:16px}.grid{display:grid}.corner,.head,.time,.cell{border-right:1px solid #26364f;border-bottom:1px solid #26364f;background:#07111f}.corner,.head{position:sticky;top:0;z-index:4;min-height:48px;padding:10px;background:#111827;color:#bae6fd;font-weight:900;text-transform:uppercase;font-size:11px;letter-spacing:.08em}.head.person{color:#bbf7d0}.head.unassigned{color:#fecaca}.corner{left:0;z-index:5}.row{display:contents}.time{position:sticky;left:0;z-index:3;padding:8px;font-weight:900;color:#bae6fd;background:#0f172a}.cell{min-height:132px;padding:5px;display:grid;gap:7px;align-content:start}.empty{color:#334155}.workcard{display:grid;gap:4px}.work{display:grid;gap:2px;width:100%;border:1px solid #334155;background:#0b1220;color:#e5e7eb;border-radius:10px;padding:7px;text-align:left}.work:hover{outline:2px solid #67e8f9}.work b{font-size:12px}.work span{font-size:11px;color:#f8fafc}.work small{font-size:10px}.work .clinical{color:#a5f3fc}.work em{font-style:normal;font-size:10px;color:#cbd5e1}.qas{display:grid;grid-template-columns:1fr 1fr auto auto;gap:4px}.qas select,.qas button{min-width:0;border:1px solid #26364f;background:#020617;color:#dbeafe;border-radius:8px;padding:5px;font-size:10px}.qas button{background:#10223c}.qas button.warn{border-color:#f59e0b;color:#fde68a}.qas small{grid-column:1/-1;font-size:10px;line-height:1.2}.qasReason{color:#93c5fd}.qasWarn{color:#fbbf24}.red{border-left:5px solid #ef4444}.amber{border-left:5px solid #f59e0b}.green{border-left:5px solid #22c55e}.blue{border-left:5px solid #38bdf8}.integrity{box-shadow:inset 0 0 0 2px #ef4444}.rule{margin-top:10px}@media(max-width:1100px){.summary{grid-template-columns:1fr}header{flex-direction:column}.modebar{align-items:flex-start;flex-direction:column}.qas{grid-template-columns:1fr 1fr}}`;
