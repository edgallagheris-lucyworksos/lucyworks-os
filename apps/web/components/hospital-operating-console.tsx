"use client";

import Link from "next/link";
import { highPressureWorkItems } from "@/lib/canonical-operational-work";

type Lane = {
  id: string;
  area: string;
  purpose: string;
  status: "red" | "amber" | "green";
  owner: string;
  blocker: string;
  next: string;
  route: string;
  pressure: string;
};

const lanes: Lane[] = [
  { id: "front-door", area: "Front door", purpose: "Referrals, owner calls, advice requests, consent and collections.", status: "red", owner: "coordinator / reception lead", blocker: "urgent referral waiting triage decision", next: "route to triage or service owner", route: "/lucy-intake", pressure: "8 waiting" },
  { id: "theatre", area: "Theatre", purpose: "Procedures, anaesthesia, kit, turnover and overruns.", status: "amber", owner: "theatre lead", blocker: "late consent / kit check", next: "confirm case order and runner cover", route: "/theatre", pressure: "5 rooms active" },
  { id: "imaging", area: "Imaging", purpose: "MRI, CT, X-ray, ultrasound, reports and scan-slot control.", status: "amber", owner: "imaging coordinator", blocker: "report ownership not confirmed", next: "assign reporter and hold emergency slot", route: "/imaging", pressure: "4 queued" },
  { id: "ward", area: "Ward", purpose: "Inpatients, beds, meds, obs, species separation and nurse workload.", status: "green", owner: "ward nurse lead", blocker: "bed forecast incomplete", next: "update expected discharge / transfer list", route: "/ward", pressure: "beds OK" },
  { id: "icu", area: "ICU / ECC", purpose: "Critical care, stabilisation, recovery escalation and overnight risk.", status: "red", owner: "ECC senior / ICU nurse", blocker: "oxygen / monitoring capacity", next: "senior review before next admission", route: "/icu-wards", pressure: "critical" },
  { id: "pharmacy", area: "Pharmacy", purpose: "Medication, stock, prescriptions, controlled drugs and discharge meds.", status: "amber", owner: "pharmacy / signing clinician", blocker: "prescription signoff backlog", next: "clear discharge meds first", route: "/lucy-pharm", pressure: "6 blocked" },
  { id: "people", area: "People / rota", purpose: "Who is working, who is overloaded, breaks, skills and safe cover.", status: "amber", owner: "ops manager", blocker: "break cover and late-case cover", next: "rebalance theatre/imaging/ward support", route: "/rota", pressure: "thin cover" },
];

const dayRows = [
  ["07:00", "handover", "triage list", "theatre prep", "MRI safety", "ward obs", "ICU review", "CD check"],
  ["08:00", "admissions", "urgent referrals", "T1-5 start", "CT/MRI slots", "beds released", "stabilise", "discharge meds"],
  ["09:00", "consults", "owner consent", "first cases", "reports", "rounds", "bloods", "signoff"],
  ["10:00", "advice calls", "estimate chase", "turnover", "ultrasound", "nurse load", "senior review", "stock gap"],
  ["11:00", "insurance", "late consent", "kit check", "delayed scan", "feeding/meds", "monitoring", "owner meds"],
  ["12:00", "lunch cover", "route new cases", "break cover", "emergency slot", "species split", "oxygen check", "CD check"],
  ["13:00", "owner updates", "routine queue", "afternoon plan", "second wave", "bed forecast", "transfer call", "batch meds"],
  ["14:00", "collections", "call-backs", "late-case decision", "report chase", "handover prep", "recovery space", "signoff"],
  ["15:00", "discharges", "billing/insurance", "recovery handoff", "emergency scan", "discharge ready", "overnight plan", "final meds"],
  ["16:00", "final calls", "tomorrow intake", "overrun close", "tomorrow scans", "evening cover", "night handover", "stock handover"],
];

function tone(status: Lane["status"]) {
  if (status === "red") return "lane red";
  if (status === "amber") return "lane amber";
  return "lane green";
}

function routeForArea(area: string) {
  if (area === "theatre") return "/theatre";
  if (area === "imaging") return "/imaging";
  if (area === "care") return "/icu-wards";
  if (area === "supply") return "/lucy-pharm";
  if (area === "front-door") return "/lucy-intake";
  return "/rota";
}

export function HospitalOperatingConsole() {
  const pressureRows = highPressureWorkItems();
  return <div className="hoc"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Hospital operating console</h1><p>One screen for the live truth: what is in the hospital, who owns it, what is blocked, and what happens next.</p></div><nav><Link href="/rota">Rota grid</Link><Link href="/lucy-intake">Intake</Link><Link href="/flow">Flow</Link><Link href="/my-shift">My Shift</Link><Link href="/resources">Resources</Link></nav></header><section className="strip"><div><b>Hospital state</b><strong>{pressureRows.length} active pressure rows</strong><small>Calculated from the shared operational work list.</small></div><div><b>Rule</b><strong>Every row needs owner + blocker + next action</strong><small>No dead cards. No decorative pages.</small></div><div><b>Action model</b><strong>Route → assign → start → block/complete</strong><small>Staff do not accept/decline normal work.</small></div></section><main className="layout"><section className="left"><h2>Operating lanes</h2>{lanes.map((lane) => <Link href={lane.route} className={tone(lane.status)} key={lane.id}><div><b>{lane.area}</b><small>{lane.purpose}</small></div><div><span>{lane.pressure}</span><span>{lane.owner}</span></div><p><b>Blocker:</b> {lane.blocker}</p><p><b>Next:</b> {lane.next}</p></Link>)}<section className="pressure"><h2>Canonical pressure rows</h2>{pressureRows.map((row) => <Link href={routeForArea(row.area)} key={row.id}><b>{row.item}</b><span>{row.area} / {row.owner}</span><small>{row.blocker} → {row.next}</small></Link>)}</section></section><section className="right"><div className="sheet-title"><h2>Day sheet</h2><p>Rota-style operating spreadsheet. Click through from lane cards or the rota grid.</p></div><div className="sheet"><div className="sheet-head"><b>Time</b><b>Coordinator</b><b>Front door</b><b>Theatre</b><b>Imaging</b><b>Ward</b><b>ICU</b><b>Pharmacy</b></div>{dayRows.map((row) => <div className="sheet-row" key={row[0]}>{row.map((cell, idx) => <Link href={idx === 0 ? "/schedule" : idx === 1 ? "/rota" : idx === 2 ? "/lucy-intake" : idx === 3 ? "/theatre" : idx === 4 ? "/imaging" : idx === 5 ? "/ward" : idx === 6 ? "/icu-wards" : "/lucy-pharm"} key={`${row[0]}-${idx}`}>{cell}</Link>)}</div>)}</div><section className="explain"><h2>What each area means</h2><p><b>Front door</b> decides what enters the system. <b>Flow</b> shows where the patient is stuck. <b>Rota</b> shows who can do the work safely. <b>My Shift</b> shows the named or role-routed tasks for a person.</p></section></section></main></div>;
}

const css = `.hoc{min-height:100vh;background:#030712;color:#e5e7eb;padding:16px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:18px;background:#060b16;border:1px solid #243447;border-radius:22px;padding:20px}header span{text-transform:uppercase;letter-spacing:.15em;color:#67e8f9;font-size:12px;font-weight:900}h1{font-size:clamp(40px,6vw,82px);line-height:.88;margin:8px 0}p,small{color:#a8b3c4}nav{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}a{color:#e5e7eb;text-decoration:none}nav a{border:1px solid #334155;background:#0f172a;border-radius:999px;padding:9px 12px;font-weight:800}.strip{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0}.strip div,.explain,.sheet-title{background:#07111f;border:1px solid #243447;border-radius:18px;padding:14px}.strip b,.strip small{display:block}.strip strong{display:block;font-size:18px;margin:6px 0}.layout{display:grid;grid-template-columns:390px minmax(900px,1fr);gap:12px}.left,.right{display:grid;gap:10px;align-content:start}.lane{display:grid;gap:9px;background:#0b1220;border:1px solid #334155;border-left-width:8px;border-radius:16px;padding:12px}.lane:hover,.sheet a:hover,.pressure a:hover{outline:2px solid #67e8f9}.lane>div{display:flex;justify-content:space-between;gap:12px}.lane span{font-size:12px;color:#cbd5e1}.red{border-left-color:#ef4444}.amber{border-left-color:#f59e0b}.green{border-left-color:#22c55e}.pressure{display:grid;gap:8px}.pressure a{display:grid;gap:4px;border:1px solid #334155;background:#07111f;border-radius:14px;padding:10px}.pressure span{font-size:12px;color:#cbd5e1}.sheet{min-width:980px;border:1px solid #243447;border-radius:16px;overflow:hidden}.sheet-head,.sheet-row{display:grid;grid-template-columns:80px repeat(7,minmax(120px,1fr))}.sheet-head b{background:#111827;color:#cbd5e1;padding:10px;border-right:1px solid #243447}.sheet a{min-height:56px;background:#07111f;border-top:1px solid #243447;border-right:1px solid #243447;padding:9px;font-size:13px}.explain{margin-top:10px}@media(max-width:1100px){.strip,.layout{grid-template-columns:1fr}.sheet{min-width:960px}}`;
