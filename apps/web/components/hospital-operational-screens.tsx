"use client";

import Link from "next/link";

type User = { role?: string; name?: string; email?: string };
type State = "red" | "amber" | "green" | "blue";
type Row = { title: string; meta: string; detail: string; state: State };

const actionRows: Row[] = [
  { title: "Resolve cover clash", meta: "Now · Clinical Director", detail: "Imaging and Theatre 1 need the same senior cover. Pick the safe sequence.", state: "red" },
  { title: "Confirm recovery space", meta: "+15 · ICU / recovery", detail: "The next procedure cannot move until recovery capacity is confirmed.", state: "red" },
  { title: "Complete discharge signoff", meta: "+30 · clinician", detail: "A ward bed stays blocked until final instructions are signed.", state: "amber" },
  { title: "Owner update on delay", meta: "+30 · admin", detail: "Communication is overdue and needs a named owner.", state: "amber" },
];

const flowRows: Row[] = [
  { title: "Triage to diagnostics", meta: "Case A · owner needed", detail: "Waiting for a named clinical owner before moving.", state: "red" },
  { title: "Diagnostics to service", meta: "Case B · cover check", detail: "Slot is available but the receiving service is not ready.", state: "amber" },
  { title: "Theatre to recovery", meta: "Case C · capacity", detail: "Theatre timing depends on recovery acceptance.", state: "red" },
  { title: "Ward to discharge", meta: "Case D · signoff", detail: "Discharge work is blocking bed release.", state: "amber" },
];

const interruptRows: Row[] = [
  { title: "Urgent callback", meta: "09:05 · admin", detail: "Owner waiting for delay explanation.", state: "amber" },
  { title: "Recovery capacity shock", meta: "09:08 · ICU", detail: "The planned theatre order is now at risk.", state: "red" },
  { title: "Result escalation", meta: "09:12 · clinical", detail: "A clinical owner must act before the case can move.", state: "red" },
  { title: "Walk-in pressure", meta: "09:18 · front desk", detail: "New triage load displaces planned work.", state: "amber" },
];

const shiftRows: Row[] = [
  { title: "Prep checks", meta: "Now · theatre", detail: "Checklist, receiver, consent visibility and handoff status.", state: "red" },
  { title: "ICU observations", meta: "+15 · ICU", detail: "Observation cycle due before movement decision.", state: "amber" },
  { title: "Discharge pack", meta: "+30 · ward", detail: "Prepare instructions and flag clinician signoff.", state: "amber" },
  { title: "Patient movement", meta: "+45 · PCA", detail: "Move only when the receiving team confirms handoff.", state: "amber" },
];

const staffRows = [
  ["Clinical Director", "Command", "6", "92%", "none", "red"],
  ["Duty Clinician", "Triage/ECC", "5", "84%", "+90", "red"],
  ["Senior cover", "Imaging + Theatre", "4", "96%", "overlap", "red"],
  ["Imaging Nurse", "Imaging", "4", "82%", "+60", "amber"],
  ["Theatre Nurse", "Theatre", "3", "73%", "+45", "amber"],
  ["ICU Nurse", "ICU", "5", "90%", "none", "red"],
  ["Ward Nurse", "Ward", "7", "88%", "+75", "red"],
  ["PCA", "Movement", "8", "76%", "+30", "amber"],
  ["Reception/Admin", "Owner comms", "9", "81%", "+45", "amber"],
];

const resourceRows = [
  ["Theatre 1", "Blocked", "turnover + recovery", "red"],
  ["Theatre 2", "Busy", "kit confirmation", "amber"],
  ["Imaging", "Held", "senior signoff", "amber"],
  ["CT", "Running", "result ownership", "red"],
  ["ICU", "7/8", "high pressure", "red"],
  ["Ward", "14/18", "discharge blockers", "amber"],
  ["Pharmacy", "Queue", "clinical signoff", "amber"],
  ["PCA movement", "Loaded", "three moves due", "amber"],
];

const lanes = ["Triage", "Imaging", "CT", "Theatre 1", "Theatre 2", "Recovery", "ICU", "Ward", "Discharge"];
const slots = ["Now", "+15", "+30", "+45", "+60", "+90", "+120"];

function cx(state: string) { return state === "red" ? "red" : state === "amber" ? "amber" : state === "green" ? "green" : "blue"; }

function Screen({ title, subtitle, focus, children }: { title: string; subtitle: string; focus: string; children: any }) {
  return <div className="ops"><style>{css}</style><header className="hero"><div><span>LucyWorks OS · {focus}</span><h1>{title}</h1><p>{subtitle}</p></div><nav><Link href="/hospital-board">NOW</Link><Link href="/flow">Flow</Link><Link href="/resources">Ops</Link><Link href="/my-shift">Shift</Link><Link href="/interrupts">Pulse</Link></nav></header>{children}</div>;
}
function Panel({ label, title, children }: { label: string; title: string; children: any }) { return <section className="panel"><div className="panelHead"><span>{label}</span><h2>{title}</h2></div>{children}</section>; }
function Cards({ rows }: { rows: Row[] }) { return <div className="cards">{rows.map((r) => <article className={`card ${cx(r.state)}`} key={r.title}><b>{r.title}</b><small>{r.meta}</small><p>{r.detail}</p></article>)}</div>; }
function Metrics() { return <section className="metrics">{[["State", "RED", "red"], ["30m risk", "7", "red"], ["Blockers", "4", "red"], ["Staff gaps", "4", "red"], ["Flow", "HIGH", "amber"], ["Capacity", "TIGHT", "amber"]].map(([a,b,c]) => <div className={`metric ${cx(c)}`} key={a}><span>{a}</span><strong>{b}</strong></div>)}</section>; }
function Timeline() { return <div className="timeline"><div className="cell head">Lane</div>{slots.map((s) => <div className="cell head" key={s}>{s}</div>)}{lanes.map((lane, i) => <div className="row" key={lane}><div className="cell lane"><b>{lane}</b></div>{slots.map((s, j) => <div className="cell" key={lane+s}>{j === i % slots.length ? `Case ${String.fromCharCode(65 + i)} · ${s}` : ""}</div>)}</div>)}</div>; }
function Staff() { return <div className="staff">{staffRows.map((r) => <div className={`staffRow ${cx(r[5])}`} key={r[0]}><span>{r[0]}</span><span>{r[1]}</span><span>{r[2]}</span><span>{r[3]}</span><span>{r[4]}</span></div>)}</div>; }
function ResourceGrid() { return <div className="resourceGrid">{resourceRows.map((r) => <div className={`resource ${cx(r[3])}`} key={r[0]}><b>{r[0]}</b><strong>{r[1]}</strong><small>{r[2]}</small></div>)}</div>; }
function Rail() { return <aside className="rail"><Panel label="priority" title="Action rail"><Cards rows={actionRows} /></Panel><Panel label="audit" title="Decision trail"><div className="audit"><p>09:02 result escalated</p><p>09:05 cover clash detected</p><p>09:08 recovery capacity blocked</p><p>09:12 discharge signoff pending</p></div></Panel></aside>; }
function Layout({ children }: { children: any }) { return <div className="layout"><main>{children}</main><Rail /></div>; }

export function HospitalCommandDashboard({ user }: { user?: User }) { return <Screen title="Hospital command board" subtitle="Whole-hospital safety, ownership, pressure and next action control." focus={user?.role || "command"}><Metrics /><Layout><Panel label="timeline" title="Now to +120"><Timeline /></Panel><div className="two"><Panel label="staff" title="Allocation and overload"><Staff /></Panel><Panel label="rota" title="Gaps requiring intervention"><Cards rows={actionRows} /></Panel></div></Layout></Screen>; }
export function ClinicalDirectorDashboard({ user }: { user?: User }) { return <Screen title="Clinical Director risk dashboard" subtitle="Escalations, safety risks, staffing gaps and blocked ownership." focus={user?.role || "manager"}><Metrics /><Layout><Panel label="unsafe now" title="Risk map"><Cards rows={[actionRows[0], actionRows[1], interruptRows[2], flowRows[2]]} /></Panel><div className="two"><Panel label="staff" title="Overload"><Staff /></Panel><Panel label="capacity" title="Critical resources"><ResourceGrid /></Panel></div></Layout></Screen>; }
export function PatientFlowDashboard({ user }: { user?: User }) { return <Screen title="LucyFlow patient movement" subtitle="Where patients are stuck, who owns the blocker and what moves next." focus={user?.role || "flow"}><Layout><Panel label="flow" title="Movement blockers"><div className="flowCols"><FlowLane title="Triage" rows={[flowRows[0]]} /><FlowLane title="Diagnostics" rows={[flowRows[0], flowRows[1]]} /><FlowLane title="Theatre" rows={[flowRows[2]]} /><FlowLane title="Ward" rows={[flowRows[3]]} /><FlowLane title="Discharge" rows={[flowRows[3]]} /></div></Panel><Panel label="timeline" title="Movement timing"><Timeline /></Panel></Layout></Screen>; }
function FlowLane({ title, rows }: { title: string; rows: Row[] }) { return <div className="flowLane"><h3>{title}</h3><Cards rows={rows} /></div>; }
export function ResourcesDashboard({ user }: { user?: User }) { return <Screen title="LucyOps resource control" subtitle="Staff, rooms, theatre, imaging, ward, ICU and support capacity." focus={user?.role || "ops"}><Layout><Panel label="capacity" title="Resource status"><ResourceGrid /></Panel><div className="two"><Panel label="staff" title="Staff allocation"><Staff /></Panel><Panel label="rota" title="Coverage risk"><Cards rows={actionRows} /></Panel></div></Layout></Screen>; }
export function MyShiftDashboard({ user }: { user?: User }) { return <Screen title="My shift worklist" subtitle="Role-specific patient tasks, deadlines and handoffs." focus={user?.role || "shift"}><Layout><Panel label="worklist" title="Immediate work"><Cards rows={shiftRows} /></Panel><Panel label="handover" title="Inputs needed"><Cards rows={[actionRows[2], actionRows[3], flowRows[1]]} /></Panel></Layout></Screen>; }
export function InterruptionsDashboard({ user }: { user?: User }) { return <Screen title="LucyPulse interruptions desk" subtitle="Urgent events disrupting the plan: callbacks, result escalations, walk-ins and capacity shocks." focus={user?.role || "pulse"}><Layout><Panel label="interrupts" title="New urgent events"><Cards rows={interruptRows} /></Panel><Panel label="impact" title="Displaced planned work"><Cards rows={[flowRows[1], flowRows[2], actionRows[0], actionRows[1]]} /></Panel></Layout></Screen>; }

const css = `.ops{min-height:100vh;background:#07111f;color:#e6edf7;padding:22px;font-family:Inter,system-ui,sans-serif}.hero{display:flex;justify-content:space-between;gap:18px;padding:22px;border:1px solid #243b60;border-radius:24px;background:linear-gradient(135deg,#0e1b31,#08111f)}.hero span,.panelHead span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:900}.hero h1{margin:8px 0;font-size:clamp(34px,5vw,62px);line-height:.95}.hero p,.card p,.card small,.audit p,.resource small{color:#a7b5c8}.hero nav{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}.hero a{color:#e6edf7;text-decoration:none;border:1px solid #31557f;background:#10223c;padding:9px 12px;border-radius:999px;font-weight:800}.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:14px 0}.metric,.panel{background:#0b1728;border:1px solid #243b60;border-radius:20px;padding:14px}.metric span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.metric strong{font-size:28px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px}.layout main,.rail{display:grid;gap:14px;align-content:start}.panelHead{display:flex;justify-content:space-between;border-bottom:1px solid #243b60;margin-bottom:12px;padding-bottom:10px}.panelHead h2{margin:0;font-size:19px}.red{border-color:#ef4444!important;background:#2a0d16!important}.amber{border-color:#f59e0b!important;background:#2a1a08!important}.green{border-color:#22c55e!important;background:#071d13!important}.blue{border-color:#38bdf8!important;background:#071a2a!important}.cards{display:grid;gap:8px}.card{display:grid;gap:6px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:11px}.card p{margin:0}.timeline{display:grid;grid-template-columns:130px repeat(7,minmax(120px,1fr));gap:1px;background:#243b60;border-radius:16px;overflow:auto}.row{display:contents}.cell{min-height:62px;background:#091321;padding:9px}.head,.lane{background:#10223c;font-weight:900}.lane{position:sticky;left:0}.two{display:grid;grid-template-columns:1.25fr 1fr;gap:14px}.staff{display:grid;gap:6px}.staffRow{display:grid;grid-template-columns:1.25fr 1fr .45fr .55fr .65fr;gap:8px;padding:8px;border:1px solid #28466e;border-radius:12px;background:#091321}.resourceGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.resource{display:grid;gap:5px;border:1px solid #28466e;border-radius:15px;background:#091321;padding:12px}.resource strong{font-size:22px}.flowCols{display:grid;grid-template-columns:repeat(5,minmax(170px,1fr));gap:10px;overflow:auto}.flowLane{background:#091321;border:1px solid #243b60;border-radius:16px;padding:10px}.flowLane h3{margin:0 0 10px}.audit{display:grid;gap:8px}.audit p{margin:0;border-bottom:1px solid #1e3556;padding-bottom:7px}@media(max-width:1150px){.layout,.two{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.resourceGrid{grid-template-columns:repeat(2,1fr)}.timeline{grid-template-columns:130px repeat(7,140px)}.flowCols{grid-template-columns:repeat(5,180px)}}@media(max-width:640px){.ops{padding:10px}.hero{flex-direction:column}.metrics,.resourceGrid{grid-template-columns:1fr}.staffRow{grid-template-columns:1fr 1fr}.hero h1{font-size:34px}}`;
