"use client";

import { useMemo } from "react";
import { useDayControlStore } from "@/lib/day-control-store";
import type { ScheduledWorkBlock } from "@/lib/day-control-work";

type OverviewProps = {
  onOpenPatientFlow: () => void;
  onOpenWorkforce: () => void;
};

const riskRank = { red: 0, amber: 1, blue: 2, green: 3 };

function area(block: ScheduledWorkBlock) {
  const text = `${block.lane} ${block.where} ${block.resourceName || ""} ${block.what}`.toLowerCase();
  if (/theatre|procedure|surgery/.test(text)) return "Theatres";
  if (block.lane === "imaging" || /mri|ct|x-ray|ultrasound|laboratory|lab/.test(text)) return "Diagnostics";
  if (block.lane === "care" || /ward|icu|recovery/.test(text)) return "Wards / ICU";
  if (["arrival", "reception", "consult", "insurance", "intake"].includes(block.lane)) return "Front door";
  if (block.lane === "client") return "Owner contact";
  return "Clinical support";
}

function theatreName(block: ScheduledWorkBlock) {
  const value = block.resourceName || block.where;
  return /theatre\s*\d/i.test(value) ? value : "Theatre 1";
}

export function HospitalCommandOverview({ onOpenPatientFlow, onOpenWorkforce }: OverviewProps) {
  const { blocks, pressure, blocked } = useDayControlStore();

  const patients = useMemo(() => new Set(blocks.map((block) => block.subject).filter(Boolean)).size, [blocks]);
  const urgent = useMemo(() => [...blocks]
    .filter((block) => block.status === "red" || block.status === "amber" || block.blocker !== "none")
    .sort((a, b) => riskRank[a.status] - riskRank[b.status] || a.time.localeCompare(b.time))
    .slice(0, 7), [blocks]);
  const unowned = blocks.filter((block) => !block.assignedStaffName && !block.assignedRole && !block.who).length;
  const areas = ["Front door", "Diagnostics", "Theatres", "Wards / ICU", "Owner contact"].map((name) => {
    const work = blocks.filter((block) => area(block) === name);
    return { name, work: work.length, blocked: work.filter((block) => block.blocker !== "none").length, patients: new Set(work.map((block) => block.subject).filter(Boolean)).size };
  });
  const theatres = ["Theatre 1", "Theatre 2", "Theatre 3", "Theatre 4"].map((name) => {
    const work = blocks.filter((block) => area(block) === "Theatres" && theatreName(block) === name);
    const next = [...work].sort((a, b) => a.time.localeCompare(b.time))[0];
    return { name, count: work.length, next, blocked: work.some((block) => block.blocker !== "none") };
  });
  const diagnosticNames = ["MRI", "CT", "X-ray", "Laboratory"];
  const diagnostics = diagnosticNames.map((name) => {
    const work = blocks.filter((block) => area(block) === "Diagnostics" && `${block.what} ${block.where}`.toLowerCase().includes(name.toLowerCase()));
    return { name, count: work.length, blocked: work.filter((block) => block.blocker !== "none").length };
  });

  return <main className="overview">
    <style>{css}</style>
    <header className="overviewHeader">
      <div><span>Hospital command overview</span><h2>Today’s operating position</h2><p>Exceptions, capacity and accountable next actions from the same live schedule used by every department.</p></div>
      <div className="headerActions"><button className="primary" onClick={onOpenPatientFlow}>Open patient flow</button><button onClick={onOpenWorkforce}>Open workforce</button></div>
    </header>

    <section className="position" aria-label="Current hospital position">
      <article><span>Patients on site</span><strong>{patients}</strong><small>active scheduled patients</small></article>
      <article className={blocked.length ? "critical" : ""}><span>Blocked work</span><strong>{blocked.length}</strong><small>requires intervention</small></article>
      <article className={pressure.length ? "warning" : ""}><span>Operational pressure</span><strong>{pressure.length}</strong><small>red or amber items</small></article>
      <article className={unowned ? "warning" : ""}><span>Unowned work</span><strong>{unowned}</strong><small>assignment required</small></article>
    </section>

    <section className="overviewGrid">
      <article className="panel priorities">
        <header><div><h3>Priority interventions</h3><p>Highest-risk work first</p></div><button onClick={onOpenPatientFlow}>View all</button></header>
        <div className="priorityHead"><span>Time</span><span>Patient / work</span><span>Owner</span><span>Required action</span></div>
        {urgent.length ? urgent.map((block) => <div className="priorityRow" key={block.id} data-risk={block.status}>
          <time>{block.time}</time>
          <span><b>{block.subject || block.what}</b><small>{block.what} · {block.where}</small></span>
          <span><b>{block.assignedStaffName || block.assignedRole || block.who || "Unowned"}</b><small>{area(block)}</small></span>
          <span><b>{block.blocker !== "none" ? block.blocker : block.next}</b><small>{block.blocker !== "none" ? `Next: ${block.next}` : "ready to progress"}</small></span>
        </div>) : <p className="clearState">No current red or amber operational exceptions.</p>}
      </article>

      <article className="panel flow">
        <header><div><h3>Flow by department</h3><p>Patients and blocked work</p></div></header>
        {areas.map((item) => <div className="flowRow" key={item.name}><span><b>{item.name}</b><small>{item.work} scheduled work items</small></span><strong>{item.patients}</strong><em className={item.blocked ? "bad" : ""}>{item.blocked ? `${item.blocked} blocked` : "clear"}</em></div>)}
      </article>
    </section>

    <section className="capacityGrid">
      <article className="panel capacity">
        <header><div><h3>Theatre capacity</h3><p>Four-room operating position</p></div><button onClick={onOpenPatientFlow}>Open theatre view</button></header>
        <div className="capacityRows">{theatres.map((theatre) => <div key={theatre.name} className={theatre.blocked ? "hasBlocker" : ""}><span><b>{theatre.name}</b><small>{theatre.next ? `${theatre.next.time} · ${theatre.next.subject || theatre.next.what}` : "Available / unallocated"}</small></span><strong>{theatre.count}</strong><em>{theatre.blocked ? "blocked" : theatre.count ? "scheduled" : "available"}</em></div>)}</div>
      </article>
      <article className="panel capacity">
        <header><div><h3>Diagnostics</h3><p>Queue and blocker position</p></div><button onClick={onOpenPatientFlow}>Open diagnostics</button></header>
        <div className="capacityRows">{diagnostics.map((item) => <div key={item.name} className={item.blocked ? "hasBlocker" : ""}><span><b>{item.name}</b><small>{item.blocked ? `${item.blocked} requiring intervention` : "No active blocker"}</small></span><strong>{item.count}</strong><em>{item.count ? "queued" : "available"}</em></div>)}</div>
      </article>
    </section>

    <footer><b>Operating rule:</b> this overview summarises live scheduled work. Patient flow, theatre, diagnostics and workforce must not maintain separate truth.</footer>
  </main>;
}

const css = `
.overview{display:grid;gap:10px;padding:12px 18px 28px;color:#182c3f;background:#eef2f7}.overviewHeader{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:14px 16px;background:#fff;border:1px solid #d8e0e8;border-radius:10px}.overviewHeader span{color:#42657f;font-size:9px;font-weight:850;text-transform:uppercase;letter-spacing:.08em}.overviewHeader h2{margin:3px 0 0;font-size:21px;letter-spacing:-.025em;color:#17344e}.overviewHeader p{margin:4px 0 0;color:#718092;font-size:11px}.headerActions{display:flex;gap:6px}.overview button{min-height:32px;padding:6px 9px;border:1px solid #cbd6df;border-radius:6px;background:#fff;color:#294a64;font-size:10px;font-weight:800}.overview button.primary{background:#173f5f;border-color:#173f5f;color:#fff}
.position{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.position article{display:grid;grid-template-columns:1fr auto;gap:2px 8px;padding:10px 12px;background:#fff;border:1px solid #d8e0e8;border-left:4px solid #64859d;border-radius:9px}.position article.warning{border-left-color:#c77c14}.position article.critical{border-left-color:#b63c38}.position span{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:#65778a;font-weight:800}.position strong{grid-row:1/3;grid-column:2;font-size:26px;color:#17344e}.position small{font-size:9px;color:#7b8998}
.overviewGrid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(300px,.65fr);gap:10px}.capacityGrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.panel{background:#fff;border:1px solid #d8e0e8;border-radius:10px;overflow:hidden}.panel>header{display:flex;justify-content:space-between;align-items:center;padding:9px 11px;border-bottom:1px solid #e2e8ee}.panel h3{margin:0;font-size:13px;color:#17344e}.panel header p{margin:2px 0 0;font-size:9px;color:#748394}
.priorityHead,.priorityRow{display:grid;grid-template-columns:48px minmax(160px,1.3fr) minmax(120px,.8fr) minmax(180px,1fr);gap:8px;align-items:center;padding:7px 9px}.priorityHead{background:#f1f5f8;color:#687a8c;font-size:8px;font-weight:850;text-transform:uppercase;letter-spacing:.04em}.priorityRow{border-bottom:1px solid #e8edf1;font-size:10px}.priorityRow[data-risk=red]{border-left:4px solid #b73d39}.priorityRow[data-risk=amber]{border-left:4px solid #cc8319}.priorityRow time{font-weight:850;color:#294f6b}.priorityRow b{display:block;color:#21384c}.priorityRow small{display:block;margin-top:2px;color:#788697;font-size:8px}.clearState{padding:14px;color:#547064;font-size:11px}
.flowRow{display:grid;grid-template-columns:1fr 32px 62px;align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid #e8edf1}.flowRow span b{display:block;font-size:10px}.flowRow span small{display:block;color:#7b8998;font-size:8px}.flowRow strong{text-align:right;color:#17344e}.flowRow em{text-align:right;font-size:8px;font-style:normal;color:#397359}.flowRow em.bad{color:#a4312e;font-weight:800}
.capacityRows{display:grid;grid-template-columns:1fr 1fr}.capacityRows>div{display:grid;grid-template-columns:1fr auto;gap:2px 8px;padding:10px;border-right:1px solid #e8edf1;border-bottom:1px solid #e8edf1;border-left:3px solid #5d839d}.capacityRows>div.hasBlocker{border-left-color:#b63c38}.capacityRows span b{display:block;font-size:10px}.capacityRows span small{display:block;margin-top:2px;color:#7a8897;font-size:8px}.capacityRows strong{font-size:17px;color:#17344e}.capacityRows em{grid-column:2;font-size:8px;font-style:normal;color:#63788b}.overview footer{padding:8px 10px;border:1px solid #d5dee6;border-radius:8px;background:#f8fafb;color:#69798a;font-size:9px}
@media(max-width:980px){.overviewGrid{grid-template-columns:1fr}.position{grid-template-columns:1fr 1fr}.capacityGrid{grid-template-columns:1fr}.overviewHeader{align-items:flex-start}}
@media(max-width:600px){.overview{padding:8px}.overviewHeader{display:grid}.position{grid-template-columns:1fr 1fr}.priorityHead{display:none}.priorityRow{grid-template-columns:42px 1fr}.priorityRow>span:nth-child(n+3){grid-column:2}.capacityRows{grid-template-columns:1fr}.headerActions{overflow-x:auto}}
`;
