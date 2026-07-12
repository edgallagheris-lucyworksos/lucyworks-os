"use client";

import { useMemo, useState } from "react";
import { GovernanceGatesPanel } from "@/components/governance-gates-panel";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import { QuickAssignmentStrip } from "@/components/quick-assignment-strip";
import { ReferralPathwayGenerator } from "@/components/referral-pathway-generator";
import { ScheduleWarningsPanel } from "@/components/schedule-warnings-panel";
import { pharmacyLabels, procedureForWork, protectedTimeLabel } from "@/lib/clinical-catalogue";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";
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
  if (next.includes("mri")) return "to MRI";
  if (next.includes("ct")) return "to CT";
  if (next.includes("theatre")) return "to theatre";
  if (next.includes("ward")) return "to ward";
  if (next.includes("owner") || next.includes("client")) return "owner/client contact";
  return safe(block.next) || "NO NEXT ACTION";
}

function procedure(block: ScheduledWorkBlock) {
  return procedureForWork(`${safe(block.what)} ${safe(block.how)} ${safe(block.where)} ${safe(block.next)}`, block.lane);
}

function hasPharmacyDependency(block: ScheduledWorkBlock) {
  return Boolean(procedure(block)?.pharmacyRefs.length);
}

function clinicalLine(block: ScheduledWorkBlock) {
  const item = procedure(block);
  if (!item) return "general work";
  return protectedTimeLabel(item);
}

function pharmacyLine(block: ScheduledWorkBlock) {
  const item = procedure(block);
  if (!item || item.pharmacyRefs.length === 0) return "pharmacy clear";
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

function blockSort(left: ScheduledWorkBlock, right: ScheduledWorkBlock) {
  return safe(left.time).localeCompare(safe(right.time)) || safe(left.subject || left.what).localeCompare(safe(right.subject || right.what));
}

function columnBlocks(blocks: ScheduledWorkBlock[], column: DisplayColumn, mode: BoardMode) {
  if (mode === "person") return blocks.filter((block) => personColumnKey(block) === column.key).sort(blockSort);
  return blocks.filter((block) => columnKey(block) === column.roleKey).sort(blockSort);
}

function groupedByTime(blocks: ScheduledWorkBlock[]) {
  const map = new Map<string, ScheduledWorkBlock[]>();
  for (const block of [...blocks].sort(blockSort)) {
    const time = safe(block.time) || "time unset";
    map.set(time, [...(map.get(time) || []), block]);
  }
  return Array.from(map.entries());
}

export function StaffLocationGrid() {
  const { blocks, pressure, blocked, addBlocks, assignBlock, clearAssignment, applyAction, resetBlocks, syncStatus } = useDayControlStore();
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const [view, setView] = useState<ViewKey>("all");
  const [mode, setMode] = useState<BoardMode>("person");
  const filteredBlocks = useMemo(() => blocks.filter((block) => blockVisible(block, view)), [blocks, view]);
  const visibleColumns = useMemo(() => mode === "person" ? personViewColumns(filteredBlocks) : roleViewColumns(view), [filteredBlocks, mode, view]);
  const visibleGroups = useMemo(() => groupedByTime(filteredBlocks), [filteredBlocks]);
  const integrityWarnings = blocks.filter((block) => !hasOwner(block) || !hasLocation(block) || !hasNext(block)).length;
  const namedPeople = blocks.filter((block) => safe(block.assignedStaffName)).length;
  const blockedCount = blocked.length + integrityWarnings;

  function onActionComplete(item: OperationalTarget, action: OperationalActionType) {
    applyAction(String(item.id), action);
  }

  function workCard(block: ScheduledWorkBlock) {
    const blocker = safe(block.blocker) || "none";
    const isBlocked = blocker.toLowerCase() !== "none";
    return <article key={block.id} className={`workcard ${block.status}${integrityClass(block)}`}>
      <button type="button" className="work" onClick={() => setSelected(target(block))}>
        <span className="eyebrow">{block.time} · {roleColumn(columnKey(block)).label}</span>
        <b>{block.subject || block.what}</b>
        <strong>{block.what}</strong>
        <small>{owner(block) || "NO OWNER"} · {block.where || "NO LOCATION"}</small>
        <small>{clinicalLine(block)}</small>
        <small>{pharmacyLine(block)}</small>
        <em>{isBlocked ? `Blocked: ${blocker}` : movement(block)}</em>
      </button>
      <details className="assignment">
        <summary>Assign staff / resource</summary>
        <QuickAssignmentStrip block={block} blocks={blocks} onAssign={assignBlock} onClear={clearAssignment} />
      </details>
    </article>;
  }

  return <main className="slg"><style>{css}</style>
    <section className="topbar">
      <div>
        <span>LucyWorks OS</span>
        <h1>Hospital command board</h1>
        <p>Person / role / location / time. Mobile-first case flow with the master board still underneath.</p>
      </div>
      <div className="topActions">
        <a href="/hospital-board">Board</a>
        <a href="/system-control">System</a>
        <a href="/workspace">Workspace</a>
        <button type="button" onClick={resetBlocks}>Reset</button>
      </div>
    </section>

    <section className="commandStrip">
      <div><b>{blockedCount}</b><small>blocked / incomplete</small></div>
      <div><b>{pressure.length}</b><small>pressure rows</small></div>
      <div><b>{filteredBlocks.length}</b><small>visible tasks</small></div>
      <div><b>{namedPeople}</b><small>named assignments</small></div>
    </section>

    <ReferralPathwayGenerator onGenerate={addBlocks} syncStatus={syncStatus} />

    <section className="modebar">
      <button className={mode === "person" ? "active" : ""} onClick={() => setMode("person")}>People columns</button>
      <button className={mode === "role" ? "active" : ""} onClick={() => setMode("role")}>Role columns</button>
      <small>{namedPeople} named assignments · Unassigned work stays visible</small>
    </section>

    <nav className="filters" aria-label="Board filters">{views.map((item) => <button key={item.key} className={view === item.key ? "active" : ""} onClick={() => setView(item.key)}>{item.label}</button>)}</nav>

    <details className="diagnostics">
      <summary>Warnings and governance</summary>
      <ScheduleWarningsPanel />
      <GovernanceGatesPanel />
    </details>

    <section className="mobileTimeline" aria-label="Mobile hospital timeline">
      {visibleGroups.map(([time, rows]) => <section className="timeGroup" key={time}>
        <h2>{time}</h2>
        <div>{rows.map(workCard)}</div>
      </section>)}
    </section>

    <section className="desktopBoard" aria-label="Grouped master board">
      {visibleColumns.length ? visibleColumns.map((column) => {
        const rows = columnBlocks(filteredBlocks, column, mode);
        return <section className={`column ${column.kind}`} key={column.key}>
          <h2>{column.label}</h2>
          {rows.length ? rows.map(workCard) : <p className="empty">No visible work.</p>}
        </section>;
      }) : <section className="column"><h2>No visible work</h2></section>}
    </section>

    <section className="rule"><b>Rule:</b> person first. A named person column shows real capacity. Governance gates stop unsafe referral flow: consent, estimate, pharmacy, owner update and referring-vet report must be clear.</section>
    <QueueDetailDrawer target={selected} onClose={() => setSelected(null)} onActionComplete={onActionComplete} />
  </main>;
}

const css = `.slg{min-height:100vh;background:#f5f7fb;color:#111827;padding:12px;font-family:Inter,system-ui,sans-serif;overflow:auto}.slg *{box-sizing:border-box}.slg .topbar{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;background:white;border:1px solid #d8e0ec;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.06)}.slg .topbar span{display:block;text-transform:uppercase;letter-spacing:.14em;color:#2563eb;font-size:11px;font-weight:900}.slg .topbar h1{font-size:clamp(30px,7vw,58px);line-height:.95;margin:6px 0;color:#111827}.slg .topbar p{max-width:760px;color:#475569;margin:0;font-size:15px}.slg .topActions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.slg a,.slg button{font:inherit}.slg .topActions a,.slg .topActions button,.slg .modebar button,.slg .filters button,.slg .assignment summary{border:1px solid #cbd5e1;background:white;color:#0f172a;border-radius:999px;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.slg .topActions button{background:#0f172a;color:white}.slg .commandStrip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}.slg .commandStrip div{background:white;border:1px solid #d8e0ec;border-radius:16px;padding:14px}.slg .commandStrip b{display:block;font-size:32px;line-height:1;color:#0f172a}.slg .commandStrip small{display:block;margin-top:4px;color:#64748b}.slg .modebar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0}.slg .modebar .active,.slg .filters .active{background:#0f172a;color:white;border-color:#0f172a}.slg .modebar small{color:#64748b}.slg .filters{display:flex;gap:8px;overflow-x:auto;padding-bottom:8px;margin-bottom:8px}.slg .filters button{white-space:nowrap}.slg .diagnostics{background:white;border:1px solid #d8e0ec;border-radius:16px;padding:10px;margin:10px 0}.slg .diagnostics>summary{cursor:pointer;font-weight:900;color:#0f172a}.slg .mobileTimeline{display:none}.slg .desktopBoard{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.slg .column{background:white;border:1px solid #d8e0ec;border-radius:18px;padding:12px;min-height:140px}.slg .column h2,.slg .timeGroup h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#475569;margin:0 0 10px}.slg .workcard{border:1px solid #cbd5e1;border-left:5px solid #f59e0b;border-radius:14px;margin-bottom:10px;background:#fff;overflow:hidden}.slg .workcard.red{border-left-color:#dc2626}.slg .workcard.green{border-left-color:#16a34a}.slg .workcard.blue{border-left-color:#2563eb}.slg .workcard.integrity{outline:2px solid #fb923c}.slg .work{display:grid;text-align:left;width:100%;gap:3px;border:0;background:white;color:#111827;padding:12px;cursor:pointer;-webkit-user-select:none;user-select:none}.slg .work .eyebrow{font-size:11px;color:#2563eb;text-transform:uppercase;letter-spacing:.08em;font-weight:900}.slg .work b{font-size:20px}.slg .work strong{font-size:14px;font-weight:700;color:#334155}.slg .work small{color:#475569;font-size:13px}.slg .work em{font-style:normal;color:#92400e;background:#fffbeb;border-radius:8px;padding:5px 7px;font-size:12px;margin-top:4px}.slg .assignment{border-top:1px solid #e2e8f0;background:#f8fafc}.slg .assignment summary{display:inline-block;margin:8px 10px;border-radius:10px}.slg .qas{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:0 10px 10px}.slg .qas select,.slg .qas button{min-height:42px;border-radius:10px;border:1px solid #cbd5e1;background:white;color:#0f172a;padding:8px}.slg .qas small{grid-column:1/-1;color:#2563eb;font-size:11px}.slg .qas .warn{border-color:#d97706;color:#92400e}.slg .empty{color:#94a3b8}.slg .rule{margin-top:12px;background:#e0f2fe;border:1px solid #bae6fd;color:#0f172a;border-radius:16px;padding:12px}@media(max-width:760px){.slg{padding:10px}.slg .topbar{display:grid}.slg .topActions{justify-content:stretch}.slg .topActions a,.slg .topActions button{flex:1;text-align:center}.slg .commandStrip{grid-template-columns:repeat(2,minmax(0,1fr))}.slg .commandStrip div{padding:10px}.slg .commandStrip b{font-size:25px}.slg .desktopBoard{display:none}.slg .mobileTimeline{display:grid;gap:10px}.slg .timeGroup{display:grid;grid-template-columns:64px 1fr;gap:8px;align-items:start}.slg .timeGroup h2{position:sticky;top:8px;margin:0;background:#e0f2fe;color:#075985;border-radius:12px;text-align:center;padding:8px 4px;font-size:16px;letter-spacing:0}.slg .work b{font-size:18px}.slg .qas{grid-template-columns:1fr}.slg .diagnostics{padding:8px}}`;