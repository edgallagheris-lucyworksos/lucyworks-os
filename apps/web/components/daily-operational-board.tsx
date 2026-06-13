"use client";

import Link from "next/link";
import { coreOperatingUnits, theatreUnits, type OperatingUnit } from "@/lib/hospital-operating-model";

type Status = "red" | "amber" | "green" | "blue";

type Action = {
  title: string;
  owner: string;
  due: string;
  impact: string;
  href: string;
  status: Status;
};

const pressureCards = [
  ["Hospital state", "RED", "red"],
  ["Pressure", "86/100", "red"],
  ["Unsafe blockers", "9", "red"],
  ["Unowned work", "5", "red"],
  ["Theatre pressure", "11 rooms", "amber"],
  ["Diagnostics", "MRI/CT/X-ray", "amber"],
  ["Beds", "ICU + ward tight", "amber"],
  ["Owner/insurance", "6 waiting", "amber"],
] as const;

const actions: Action[] = [
  { title: "Assign senior cover between MRI and Theatre 5", owner: "Clinical Director", due: "now", impact: "MRI delay pushes theatre recovery and owner updates", href: "/manager-dashboard", status: "red" },
  { title: "Confirm recovery acceptance for Theatre 1", owner: "Recovery nurse", due: "+10", impact: "Theatre 1 remains blocked until recovery capacity is confirmed", href: "/resources", status: "red" },
  { title: "Complete insurance pre-authorisation for urgent CT", owner: "Admin", due: "+20", impact: "CT slot is held but cannot proceed cleanly without cover decision", href: "/lucy-comms", status: "amber" },
  { title: "Release ward beds through discharge meds", owner: "Duty clinician + pharmacy", due: "+30", impact: "Ward beds stay blocked and ICU step-down is delayed", href: "/lucy-pharm", status: "amber" },
  { title: "Resolve lab result owner gap", owner: "Clinician", due: "+30", impact: "Clinical decision is waiting and patient cannot move lanes", href: "/lucy-clinical", status: "amber" },
];

const theatreStates = theatreUnits.map((unit, index) => ({
  ...unit,
  status: (["red", "green", "amber", "green", "red", "green", "green", "amber", "amber", "green", "amber"] as Status[])[index],
  state: ["Blocked", "Active", "Turnover", "Ready", "Held", "Active", "Ready", "Consent", "Staff gap", "Emergency", "Kit held"][index],
  caseRef: ["T1-041", "T2-014", "T3-009", "T4-032", "T5-022", "T6-018", "T7-027", "T8-006", "T9-019", "T10-001", "T11-011"][index],
}));

const timelineLanes = ["Triage", "MRI", "CT", "X-ray", "Lab", "Theatre", "Recovery", "ICU", "Ward", "Pharmacy", "Insurance", "Owner comms"];
const slots = ["Now", "+15", "+30", "+45", "+60", "+90", "+120"];

function statusClass(status: string) {
  if (status === "red") return "daily-red";
  if (status === "amber") return "daily-amber";
  if (status === "green") return "daily-green";
  return "daily-blue";
}

function Section({ title, label, children }: { title: string; label: string; children: React.ReactNode }) {
  return <section className="daily-panel"><div className="daily-panel-head"><span>{label}</span><h2>{title}</h2></div>{children}</section>;
}

function PressureStrip() {
  return <div className="daily-pressure">{pressureCards.map(([label, value, status]) => <div className={`daily-kpi ${statusClass(status)}`} key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}

function TheatreComplex() {
  return <div className="theatre-grid">{theatreStates.map((theatre) => <Link href="/resources" className={`theatre-card ${statusClass(theatre.status)}`} key={theatre.id}><b>{theatre.label}</b><strong>{theatre.state}</strong><span>{theatre.caseRef}</span><small>{theatre.blockers[0]}</small></Link>)}</div>;
}

function OperatingUnits() {
  const support = coreOperatingUnits.filter((unit) => !unit.id.startsWith("theatre-"));
  return <div className="unit-grid">{support.map((unit) => <UnitCard unit={unit} key={unit.id} />)}</div>;
}

function UnitCard({ unit }: { unit: OperatingUnit }) {
  const urgent = ["mri", "ct", "pharmacy", "insurance", "icu", "recovery"].includes(unit.id);
  return <Link href={unit.route} className={`unit-card ${urgent ? "daily-amber" : "daily-blue"}`}><b>{unit.label}</b><span>{unit.ownerRole}</span><small>{unit.tracks.slice(0, 4).join(" · ")}</small><em>{unit.blockers[0]}</em></Link>;
}

function ActionRail() {
  return <div className="action-list">{actions.map((action) => <Link href={action.href} className={`action-card ${statusClass(action.status)}`} key={action.title}><b>{action.title}</b><span>Owner: {action.owner}</span><span>Due: {action.due}</span><p>{action.impact}</p></Link>)}</div>;
}

function Timeline() {
  return <div className="daily-timeline"><div className="timeline-cell timeline-head">Lane</div>{slots.map((slot) => <div className="timeline-cell timeline-head" key={slot}>{slot}</div>)}{timelineLanes.map((lane, rowIndex) => <div className="timeline-row" key={lane}><div className="timeline-cell timeline-lane"><b>{lane}</b></div>{slots.map((slot, colIndex) => <Link href={lane === "Insurance" || lane === "Owner comms" ? "/lucy-comms" : lane === "Pharmacy" ? "/lucy-pharm" : lane === "Lab" ? "/lucy-clinical" : lane === "Theatre" || lane === "Recovery" || lane === "ICU" ? "/resources" : "/flow"} className="timeline-cell" key={`${lane}-${slot}`}>{colIndex === rowIndex % slots.length ? `${lane} task · ${slot}` : ""}</Link>)}</div>)}</div>;
}

export function DailyOperationalBoard() {
  return <div className="daily-board"><style>{css}</style><header className="daily-hero"><div><span>BVS-scale daily operations</span><h1>Daily operational control</h1><p>11 theatres, imaging, X-ray, labs, pharmacy, insurance, ward, ICU, recovery, owner comms and stock/equipment pressure in one working view.</p></div><div className="daily-hero-actions"><Link href="/interrupts">Open Pulse</Link><Link href="/resources">Resource control</Link><Link href="/lucy-gov">Audit trail</Link></div></header><PressureStrip /><div className="daily-layout"><main><Section label="theatre complex" title="11-theatre operating grid"><TheatreComplex /></Section><Section label="hospital units" title="Diagnostics, pharmacy, insurance, beds and support"><OperatingUnits /></Section><Section label="timeline" title="Now to +120 minutes"><Timeline /></Section></main><aside><Section label="priority" title="Decision and action rail"><ActionRail /></Section><Section label="audit" title="Latest operating decisions"><div className="audit-list"><Link href="/lucy-gov">09:02 CT result escalated</Link><Link href="/lucy-gov">09:05 Theatre/MRI cover clash</Link><Link href="/lucy-gov">09:08 Recovery capacity block</Link><Link href="/lucy-gov">09:12 Insurance pre-auth hold</Link></div></Section></aside></div></div>;
}

const css = `.daily-board{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}.daily-hero{display:flex;justify-content:space-between;gap:18px;border:1px solid #274568;border-radius:24px;padding:22px;background:linear-gradient(135deg,#0c182a,#07111f)}.daily-hero span,.daily-panel-head span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.daily-hero h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}.daily-hero p{max-width:900px;color:#a7b5c8}.daily-hero-actions{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}.daily-hero a,.action-card,.theatre-card,.unit-card,.timeline-cell,.audit-list a{color:#e6edf7;text-decoration:none}.daily-hero a{border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.daily-pressure{display:grid;grid-template-columns:repeat(8,1fr);gap:10px;margin:14px 0}.daily-kpi,.daily-panel{background:#0b1728;border:1px solid #243b60;border-radius:18px;padding:13px}.daily-kpi span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.daily-kpi strong{font-size:24px}.daily-layout{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:14px}.daily-layout main,aside{display:grid;gap:14px;align-content:start}.daily-panel-head{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid #243b60;padding-bottom:10px;margin-bottom:12px}.daily-panel-head h2{margin:0;font-size:19px}.daily-red{border-color:#ef4444!important;background:#2a0d16!important}.daily-amber{border-color:#f59e0b!important;background:#2a1a08!important}.daily-green{border-color:#22c55e!important;background:#071d13!important}.daily-blue{border-color:#38bdf8!important;background:#071a2a!important}.theatre-grid{display:grid;grid-template-columns:repeat(11,minmax(120px,1fr));gap:8px;overflow:auto}.theatre-card,.unit-card,.action-card{display:grid;gap:5px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:10px}.theatre-card strong,.unit-card b{font-size:18px}.theatre-card small,.unit-card small,.unit-card em,.action-card span,.action-card p{color:#a7b5c8;font-style:normal;margin:0}.unit-grid{display:grid;grid-template-columns:repeat(4,minmax(190px,1fr));gap:10px}.action-list,.audit-list{display:grid;gap:8px}.audit-list a{border-bottom:1px solid #1e3556;padding-bottom:8px;color:#a7b5c8}.daily-timeline{display:grid;grid-template-columns:150px repeat(7,minmax(125px,1fr));gap:1px;background:#243b60;border-radius:16px;overflow:auto}.timeline-row{display:contents}.timeline-cell{min-height:58px;background:#091321;padding:9px}.timeline-head,.timeline-lane{background:#10223c;font-weight:900}.timeline-lane{position:sticky;left:0}@media(max-width:1250px){.daily-layout{grid-template-columns:1fr}.daily-pressure{grid-template-columns:repeat(4,1fr)}.unit-grid{grid-template-columns:repeat(2,1fr)}.theatre-grid{grid-template-columns:repeat(11,130px)}.daily-timeline{grid-template-columns:150px repeat(7,140px)}}@media(max-width:700px){.daily-board{padding:10px}.daily-hero{flex-direction:column}.daily-pressure,.unit-grid{grid-template-columns:1fr}.daily-hero h1{font-size:36px}}`;
