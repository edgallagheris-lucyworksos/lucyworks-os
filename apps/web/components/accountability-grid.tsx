"use client";

import { useMemo, useState } from "react";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import { ScheduleWarningsPanel } from "@/components/schedule-warnings-panel";
import type { OperationalActionType, OperationalTarget } from "@/lib/operational-actions";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";
import { useDayControlStore } from "@/lib/day-control-store";

const departmentFilters = [
  { key: "all", label: "Whole hospital" },
  { key: "theatre", label: "Theatres" },
  { key: "imaging", label: "Imaging" },
  { key: "care", label: "Wards / ICU" },
  { key: "front", label: "Front door" },
  { key: "blocked", label: "Blocked" },
] as const;

type FilterKey = typeof departmentFilters[number]["key"];

function toTarget(block: ScheduledWorkBlock): OperationalTarget {
  return { id: block.id, label: `${block.time} / ${block.subject || block.what}`, type: "scheduled_work_block", lane: block.lane, source: "accountability-grid", ownerRole: block.assignedRole || block.who, blocker: block.blocker, nextAction: block.next, route: block.route };
}

function department(block: ScheduledWorkBlock) {
  const text = `${block.lane} ${block.where} ${block.resourceName || ""} ${block.what}`.toLowerCase();
  if (text.includes("theatre") || text.includes("procedure")) return "theatre";
  if (block.lane === "imaging" || /mri|ct|x-ray|ultrasound|lab/.test(text)) return "imaging";
  if (block.lane === "care" || /ward|icu|recovery/.test(text)) return "care";
  if (["arrival", "reception", "consult", "insurance", "intake"].includes(block.lane)) return "front";
  return "other";
}

function matches(block: ScheduledWorkBlock, filter: FilterKey, query: string) {
  if (filter === "blocked" && block.blocker === "none") return false;
  if (filter !== "all" && filter !== "blocked" && department(block) !== filter) return false;
  if (!query) return true;
  return `${block.subject} ${block.what} ${block.where} ${block.who} ${block.blocker} ${block.next}`.toLowerCase().includes(query.toLowerCase());
}

function theatreName(block: ScheduledWorkBlock) {
  const value = block.resourceName || block.where;
  return /theatre\s*\d/i.test(value) ? value : "Theatre 1";
}

export function AccountabilityGrid() {
  const { blocks, pressure, blocked, applyAction, resetBlocks } = useDayControlStore();
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [query, setQuery] = useState("");
  const rows = useMemo(() => [...blocks]
    .filter((block) => matches(block, filter, query))
    .sort((a, b) => a.time.localeCompare(b.time) || (a.subject || a.what).localeCompare(b.subject || b.what)), [blocks, filter, query]);

  const activePatients = new Set(blocks.map((block) => block.subject).filter(Boolean)).size;
  const unowned = blocks.filter((block) => !block.assignedStaffName && !block.assignedRole && !block.who).length;
  const diagnostics = blocks.filter((block) => department(block) === "imaging");
  const theatres = ["Theatre 1", "Theatre 2", "Theatre 3", "Theatre 4"].map((name) => {
    const work = blocks.filter((block) => department(block) === "theatre" && theatreName(block) === name);
    return { name, work, blocked: work.filter((block) => block.blocker !== "none").length };
  });

  function onActionComplete(target: OperationalTarget, action: OperationalActionType) {
    applyAction(String(target.id), action);
  }

  return <main className="command">
    <style>{css}</style>
    <section className="commandStrip" aria-label="Hospital operating status">
      <div><span>On site</span><b>{activePatients}</b><small>active patients</small></div>
      <div className={blocked.length ? "risk" : ""}><span>Blocked</span><b>{blocked.length}</b><small>needs intervention</small></div>
      <div className={pressure.length ? "warn" : ""}><span>Pressure</span><b>{pressure.length}</b><small>red / amber work</small></div>
      <div><span>Unowned</span><b>{unowned}</b><small>work without owner</small></div>
      <div><span>Diagnostics</span><b>{diagnostics.length}</b><small>scheduled blocks</small></div>
    </section>

    <section className="controls">
      <div className="filters" role="group" aria-label="Department filter">
        {departmentFilters.map((item) => <button key={item.key} className={filter === item.key ? "active" : ""} onClick={() => setFilter(item.key)}>{item.label}</button>)}
      </div>
      <label><span className="srOnly">Search hospital work</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search patient, owner, room or blocker" /></label>
      <button className="reset" onClick={resetBlocks}>Reset local changes</button>
    </section>

    <ScheduleWarningsPanel />

    <section className="operations">
      <div className="patientBoard">
        <header><div><h2>Live patient flow</h2><p>{rows.length} work blocks shown · select a row to act without leaving the board</p></div><strong>{filter === "all" ? "Whole hospital" : departmentFilters.find((item) => item.key === filter)?.label}</strong></header>
        <div className="tableWrap">
          <table>
            <thead><tr><th>Time</th><th>Patient / episode</th><th>Stage & location</th><th>Accountable owner</th><th>Blocker / next action</th><th>State</th></tr></thead>
            <tbody>{rows.map((block) => <tr key={block.id} onClick={() => setSelected(toTarget(block))} data-status={block.status}>
              <td className="time">{block.time}</td>
              <td><b>{block.subject || "Hospital work"}</b><small>{block.episodeRef || block.id}</small></td>
              <td><b>{block.what}</b><small>{block.where} · {block.durationMinutes || 15} min</small></td>
              <td><b>{block.assignedStaffName || block.assignedRole || block.who || "Unowned"}</b><small>{block.how}</small></td>
              <td className={block.blocker !== "none" ? "blocked" : ""}><b>{block.blocker === "none" ? block.next : block.blocker}</b><small>{block.blocker === "none" ? "ready to progress" : `Next: ${block.next}`}</small></td>
              <td><span className={`state ${block.status}`}>{block.status}</span></td>
            </tr>)}</tbody>
          </table>
        </div>
      </div>

      <aside className="resourceRail">
        <section><header><h2>Theatre control</h2><span>4 rooms</span></header>{theatres.map((theatre) => <button key={theatre.name} onClick={() => { setFilter("theatre"); setQuery(theatre.name); }}>
          <span><b>{theatre.name}</b><small>{theatre.work[0]?.what || "Available / unallocated"}</small></span>
          <em className={theatre.blocked ? "bad" : ""}>{theatre.blocked ? `${theatre.blocked} blocked` : `${theatre.work.length} blocks`}</em>
        </button>)}</section>
        <section><header><h2>Diagnostics</h2><span>live queues</span></header>
          {["MRI", "CT", "X-ray", "Laboratory"].map((name) => {
            const count = diagnostics.filter((block) => `${block.what} ${block.where}`.toLowerCase().includes(name.toLowerCase())).length;
            return <button key={name} onClick={() => { setFilter("imaging"); setQuery(name); }}><span><b>{name}</b><small>{count ? "scheduled work" : "No queued work"}</small></span><em>{count}</em></button>;
          })}
        </section>
      </aside>
    </section>

    <section className="safetyRule"><b>Single-source rule:</b> theatre, imaging, wards and workforce are filtered views of these same scheduled work blocks. Actions update the selected block and its audit trail.</section>
    <QueueDetailDrawer target={selected} onClose={() => setSelected(null)} onActionComplete={onActionComplete} />
  </main>;
}

const css = `
.command{display:grid;gap:10px;padding:12px 18px 28px;background:#eef2f7;color:#172033;min-height:calc(100vh - 64px)}
.commandStrip{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:7px}
.commandStrip>div{display:grid;grid-template-columns:1fr auto;align-items:end;gap:2px 8px;padding:9px 11px;background:#fff;border:1px solid #d8e0e8;border-radius:9px}
.commandStrip span{color:#66778a;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em}.commandStrip b{grid-row:1/3;grid-column:2;font-size:25px;color:#15344e}.commandStrip small{font-size:10px;color:#788798}.commandStrip .risk{border-left:4px solid #c23b3b}.commandStrip .warn{border-left:4px solid #d68a16}
.controls{display:grid;grid-template-columns:1fr minmax(240px,380px) auto;gap:8px;align-items:center;background:#fff;border:1px solid #d8e0e8;border-radius:9px;padding:7px}.filters{display:flex;gap:4px;overflow-x:auto}.controls button{min-height:32px;padding:6px 9px;border:1px solid #d5dee7;border-radius:6px;background:#f7f9fb;color:#45596d;font-size:11px;font-weight:750;white-space:nowrap}.controls button.active{background:#173f5f;color:#fff;border-color:#173f5f}.controls input{min-height:34px;padding:7px 9px;border:1px solid #cad5df;border-radius:6px;background:#fff;color:#172033;font-size:12px}.srOnly{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.operations{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:10px;align-items:start}.patientBoard,.resourceRail section{background:#fff;border:1px solid #d8e0e8;border-radius:10px;overflow:hidden}.patientBoard>header,.resourceRail header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 12px;border-bottom:1px solid #e1e7ed}.patientBoard h2,.resourceRail h2{margin:0;font-size:14px;color:#17344e}.patientBoard p{margin:2px 0 0;color:#718092;font-size:10px}.patientBoard header strong,.resourceRail header span{color:#657588;font-size:10px}.tableWrap{max-height:68vh;overflow:auto}table{width:100%;border-collapse:separate;border-spacing:0;font-size:11px}th{position:sticky;top:0;z-index:2;text-align:left;padding:7px 8px;background:#edf2f6;color:#617286;border-bottom:1px solid #d8e0e8;font-size:9px;text-transform:uppercase;letter-spacing:.04em}td{padding:7px 8px;border-bottom:1px solid #e7ebef;vertical-align:top;background:#fff}tr:hover td{background:#f3f7fa;cursor:pointer}tr[data-status=red] td:first-child{border-left:4px solid #c83c3c}tr[data-status=amber] td:first-child{border-left:4px solid #d58a18}td b{display:block;color:#20364a;font-size:11px}td small{display:block;margin-top:2px;color:#758497;font-size:9px}.time{font-weight:850;color:#244c69;white-space:nowrap}.blocked b{color:#a53030}.state{display:inline-block;padding:3px 6px;border-radius:999px;font-size:8px;font-weight:900;text-transform:uppercase}.state.red{background:#f9dddd;color:#9d2525}.state.amber{background:#fff0cf;color:#8a5900}.state.green{background:#dcf3e5;color:#17653a}.state.blue{background:#dcecf8;color:#245b82}
.resourceRail{display:grid;gap:10px}.resourceRail section>button{width:100%;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 10px;border:0;border-bottom:1px solid #e7ebef;background:#fff;color:#20364a;text-align:left}.resourceRail section>button:hover{background:#f3f7fa}.resourceRail button span{display:grid;gap:2px}.resourceRail button b{font-size:11px}.resourceRail button small{font-size:9px;color:#768596}.resourceRail em{font-size:9px;font-style:normal;color:#52687c}.resourceRail em.bad{color:#a53030;font-weight:800}.safetyRule{padding:9px 11px;border:1px solid #cdd8e2;border-radius:8px;background:#f8fafc;color:#657588;font-size:10px}
@media(max-width:1050px){.commandStrip{grid-template-columns:repeat(3,1fr)}.operations{grid-template-columns:1fr}.resourceRail{grid-template-columns:1fr 1fr}.controls{grid-template-columns:1fr}.controls .reset{justify-self:start}}
@media(max-width:650px){.command{padding:8px}.commandStrip{grid-template-columns:1fr 1fr}.commandStrip>div:last-child{display:none}.resourceRail{grid-template-columns:1fr}.tableWrap{max-height:none}table{min-width:760px}.patientBoard>header{align-items:flex-start}.controls label{order:-1}}
`;
