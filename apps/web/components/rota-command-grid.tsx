"use client";

import Link from "next/link";

type RotaCell = {
  time: string;
  theatre: string;
  imaging: string;
  ward: string;
  icu: string;
  reception: string;
  pharmacy: string;
  risk: string;
};

const rows: RotaCell[] = [
  { time: "07:00", theatre: "Prep list / anaesthesia check", imaging: "MRI safety list", ward: "Morning obs", icu: "Critical handover", reception: "Admissions open", pharmacy: "Controlled-drug check", risk: "overnight blockers" },
  { time: "08:00", theatre: "Theatre 1-5 allocation", imaging: "CT/MRI slots", ward: "Beds released", icu: "Ventilator / oxygen readiness", reception: "Urgent referrals", pharmacy: "Discharge meds queue", risk: "capacity pressure" },
  { time: "09:00", theatre: "First procedures start", imaging: "Report ownership", ward: "Inpatient rounds", icu: "ECC stabilisation", reception: "Owner calls", pharmacy: "Stock gaps", risk: "late consent" },
  { time: "10:00", theatre: "Kit / runner coverage", imaging: "Ultrasound / X-ray", ward: "Nurse task load", icu: "Senior review", reception: "Advice requests", pharmacy: "Prescription signoff", risk: "staff overload" },
  { time: "11:00", theatre: "Turnaround / cleaning", imaging: "Delayed scan list", ward: "Feeding / meds", icu: "Bloods / monitoring", reception: "Insurance queries", pharmacy: "Owner meds ready", risk: "diagnostic delay" },
  { time: "12:00", theatre: "Lunch cover", imaging: "Emergency slot hold", ward: "Species separation", icu: "Break protection", reception: "Referral admin", pharmacy: "Controlled meds", risk: "break failure" },
  { time: "13:00", theatre: "Afternoon theatre plan", imaging: "CT/MRI second wave", ward: "Bed forecast", icu: "Transfer decisions", reception: "Owner updates", pharmacy: "Discharge batching", risk: "bed conflict" },
  { time: "14:00", theatre: "Late-case decision", imaging: "Report chasing", ward: "Nurse handover prep", icu: "Recovery capacity", reception: "Consent chase", pharmacy: "Medication blockers", risk: "late procedure" },
  { time: "15:00", theatre: "Recovery handoff", imaging: "Emergency imaging", ward: "Discharge readiness", icu: "Overnight plan", reception: "Collections", pharmacy: "Final meds", risk: "owner delay" },
  { time: "16:00", theatre: "Close-down / overrun", imaging: "Tomorrow scan list", ward: "Evening staffing", icu: "Night handover", reception: "Final calls", pharmacy: "Stock handover", risk: "overnight staffing" },
];

const columns: { key: keyof RotaCell; label: string; route: string; explains: string }[] = [
  { key: "time", label: "Time", route: "/schedule", explains: "timeline anchor" },
  { key: "theatre", label: "Theatre", route: "/theatre", explains: "procedures, anaesthesia, kit and turnover" },
  { key: "imaging", label: "Imaging", route: "/imaging", explains: "MRI, CT, X-ray, ultrasound and report ownership" },
  { key: "ward", label: "Ward", route: "/ward", explains: "inpatient care, beds, species separation and nurse load" },
  { key: "icu", label: "ICU/ECC", route: "/icu-wards", explains: "critical patients, stabilisation and overnight risk" },
  { key: "reception", label: "Front door", route: "/lucy-intake", explains: "referrals, owner calls, consent and collections" },
  { key: "pharmacy", label: "Pharmacy", route: "/lucy-pharm", explains: "meds, stock, signoff and discharge blockers" },
  { key: "risk", label: "Risk", route: "/pulse", explains: "what can break the day" },
];

export function RotaCommandGrid() {
  return <div className="rota"><style>{css}</style><header><div><span>LucyRota</span><h1>Hospital rota grid</h1><p>This is the operating spreadsheet: time down the side, departments across the top, and every cell links to the area that owns the blocker.</p></div><nav><Link href="/lucy-intake">Intake</Link><Link href="/flow">Flow</Link><Link href="/my-shift">My Shift</Link><Link href="/resources">Resources</Link></nav></header><section className="explain"><b>How to read it</b><p>Click a department cell to open the working section. Use the risk column to see what needs escalation before the day breaks.</p></section><div className="grid" role="table"><div className="head" role="row">{columns.map((col) => <div key={col.key} role="columnheader"><b>{col.label}</b><small>{col.explains}</small></div>)}</div>{rows.map((row) => <div className="row" role="row" key={row.time}>{columns.map((col) => <Link className={col.key === "risk" ? "cell risk" : "cell"} href={col.route} key={col.key}><b>{row[col.key]}</b><small>{col.route}</small></Link>)}</div>)}</div></div>;
}

const css = `.rota{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}header{display:flex;justify-content:space-between;gap:20px;border:1px solid #274568;border-radius:24px;padding:22px;background:#07111f}header span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}h1{font-size:clamp(38px,6vw,78px);line-height:.9;margin:8px 0}p,small{color:#9fb0c6}nav{display:flex;gap:8px;flex-wrap:wrap}a{color:#e6edf7;text-decoration:none}nav a{border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.explain{border:1px solid #274568;border-radius:18px;background:#0b1728;padding:14px;margin:14px 0}.grid{min-width:1180px;border:1px solid #274568;border-radius:18px;overflow:hidden}.head,.row{display:grid;grid-template-columns:90px repeat(7,minmax(145px,1fr))}.head div{background:#13233a;padding:10px;border-right:1px solid #274568}.cell{min-height:74px;border-top:1px solid #274568;border-right:1px solid #274568;background:#0b1728;padding:10px;display:grid;align-content:start;gap:8px}.cell:hover{outline:2px solid #5eead4;position:relative;z-index:2}.risk{background:#23111a}.cell b{font-size:13px}.cell small,.head small{display:block;font-size:11px;margin-top:4px}.rota{overflow:auto}@media(max-width:900px){.rota{padding:10px}header{flex-direction:column}.grid{min-width:1040px}}`;
