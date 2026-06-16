"use client";

import Link from "next/link";
import { bvsPublicPathways } from "@/lib/bvs-public-pathways";

type IntakeLane = {
  id: string;
  label: string;
  description: string;
  sources: string[];
  queue: string;
};

const intakeLanes: IntakeLane[] = [
  { id: "incoming", label: "Incoming", description: "New call, form, advice request or walk-in source before clinical ownership is clear.", sources: ["urgent-referral", "routine-referral", "request-advice", "owner-consult-journey"], queue: "role_queue" },
  { id: "triage", label: "Triage needed", description: "Urgency, species, service and immediate safety decision required.", sources: ["urgent-referral", "request-advice"], queue: "escalation_queue" },
  { id: "owner-consent", label: "Owner / consent / estimate", description: "Owner communication, consent, estimate, insurance or deposit is blocking the next movement.", sources: ["owner-consult-journey", "insurance-payment"], queue: "owner_comms_queue" },
  { id: "diagnostics", label: "Waiting diagnostics", description: "Case needs MRI, CT, X-ray, ultrasound, lab, report ownership or imaging capacity.", sources: ["owner-consult-journey", "routine-referral", "teer-cardiology"], queue: "imaging_queue" },
  { id: "clinical-owner", label: "Waiting clinical owner", description: "Consultant, service head, resident/intern or senior clinician needs to own the plan.", sources: ["routine-referral", "request-advice", "teer-cardiology"], queue: "clinical_owner_or_senior" },
  { id: "bed-capacity", label: "Bed / ward / ICU", description: "Patient needs ward, ICU, recovery, isolation or species-separated holding.", sources: ["urgent-referral", "teer-cardiology", "aftercare-discharge"], queue: "bed_capacity_queue" },
  { id: "procedure-ready", label: "Ready for procedure", description: "Theatre, anaesthesia, kit, imaging or interventional slot must be aligned.", sources: ["teer-cardiology", "owner-consult-journey"], queue: "theatre_queue" },
  { id: "discharge", label: "Discharge / collection", description: "Medication, payment, report, owner update or collection time is blocking leaving hospital.", sources: ["aftercare-discharge", "insurance-payment"], queue: "pharmacy_queue" },
];

function pathway(id: string) {
  return bvsPublicPathways.find((item) => item.id === id);
}

export function LucyIntakeBoard() {
  return <div className="intake"><style>{css}</style><header><div><span>LucyIntake</span><h1>Front-door coordinator</h1><small>front-door coordinator</small><p>Every public BVS intake route becomes a hospital lane: urgent referral, routine referral, advice, owner consult, insurance, diagnostics, procedure and discharge.</p></div><nav><Link href="/flow">Flow</Link><Link href="/my-shift">My Shift</Link><Link href="/bvs-public-map">BVS Map</Link></nav></header><section className="kpis"><div><span>Pathways</span><b>{bvsPublicPathways.length}</b></div><div><span>Lanes</span><b>{intakeLanes.length}</b></div><div><span>Rule</span><b>coordinate then route</b></div><div><span>Unknowns</span><b>bed capacity configurable</b></div></section><main className="lanes">{intakeLanes.map((lane) => <section className="lane" key={lane.id}><h2>{lane.label}</h2><p>{lane.description}</p><small>Destination: {lane.queue}</small><div className="cards">{lane.sources.map((source) => { const item = pathway(source); if (!item) return null; return <article className="card" key={source}><b>{item.label}</b><span>{item.lucyModule}</span><p>{item.blockers.join(" · ")}</p><small>{item.queueTargets.join(" · ")}</small></article>; })}</div></section>)}</main></div>;
}

const css = `.intake{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}header{display:flex;justify-content:space-between;gap:18px;border:1px solid #274568;border-radius:24px;padding:22px;background:#07111f}header span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:900}h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}p,small,.card span{color:#a7b5c8}nav{display:flex;gap:8px;flex-wrap:wrap}a{color:#e6edf7;text-decoration:none}nav a{border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}.kpis div,.lane{background:#0b1728;border:1px solid #243b60;border-radius:18px;padding:14px}.kpis span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.kpis b{font-size:22px}.lanes{display:grid;grid-template-columns:repeat(4,minmax(220px,1fr));gap:10px}.lane h2{margin-top:0}.cards{display:grid;gap:8px}.card{display:grid;gap:6px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:12px}.card span{font-size:12px;color:#5eead4;text-transform:uppercase;font-weight:900}@media(max-width:1200px){.lanes{grid-template-columns:repeat(2,1fr)}.kpis{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.intake{padding:10px}header{flex-direction:column}.lanes,.kpis{grid-template-columns:1fr}}`;
