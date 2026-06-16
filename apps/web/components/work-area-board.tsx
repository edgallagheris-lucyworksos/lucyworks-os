"use client";

import Link from "next/link";

export type WorkAreaRow = {
  id: string;
  item: string;
  patient: string;
  owner: string;
  status: "red" | "amber" | "green" | "blue";
  blocker: string;
  next: string;
  due: string;
  route: string;
};

export type WorkAreaBoardProps = {
  area: string;
  purpose: string;
  explanation: string;
  rows: WorkAreaRow[];
  links?: { label: string; href: string }[];
};

function rowClass(status: WorkAreaRow["status"]) {
  return `work-row ${status}`;
}

export function WorkAreaBoard({ area, purpose, explanation, rows, links = [] }: WorkAreaBoardProps) {
  return <div className="wab"><style>{css}</style><header><div><span>{area}</span><h1>{area}</h1><p>{purpose}</p></div><nav>{links.map((link) => <Link href={link.href} key={link.href}>{link.label}</Link>)}<Link href="/hospital-board">Hospital board</Link><Link href="/rota">Rota</Link><Link href="/flow">Flow</Link></nav></header><section className="explain"><b>What this area is for</b><p>{explanation}</p><small>Every row must show owner, blocker and next action. If it does not, it is not operationally useful.</small></section><section className="table"><div className="table-head"><b>Item</b><b>Patient / task</b><b>Owner</b><b>Status</b><b>Blocker</b><b>Next action</b><b>Due</b><b>Open</b></div>{rows.map((row) => <div className={rowClass(row.status)} key={row.id}><span>{row.item}</span><span>{row.patient}</span><span>{row.owner}</span><span>{row.status.toUpperCase()}</span><span>{row.blocker}</span><span>{row.next}</span><span>{row.due}</span><Link href={row.route}>open</Link></div>)}</section><section className="actions"><b>Allowed actions</b><p>Coordinator or lead can assign/reassign/route. Assigned staff can start, block, complete or escalate. Decline is only for safety or impossible-capacity reasons and must create an audit trail.</p></section></div>;
}

const css = `.wab{min-height:100vh;background:#030712;color:#e5e7eb;padding:16px;font-family:Inter,system-ui,sans-serif;overflow:auto}header{display:flex;justify-content:space-between;gap:18px;background:#060b16;border:1px solid #243447;border-radius:22px;padding:20px}header span{text-transform:uppercase;letter-spacing:.14em;color:#67e8f9;font-size:12px;font-weight:900}h1{font-size:clamp(40px,6vw,76px);line-height:.9;margin:8px 0}p,small{color:#a8b3c4}nav{display:flex;gap:8px;flex-wrap:wrap;align-content:flex-start}a{color:#e5e7eb;text-decoration:none}nav a,.work-row a{border:1px solid #334155;background:#0f172a;border-radius:999px;padding:8px 11px;font-weight:800}.explain,.actions{border:1px solid #243447;background:#07111f;border-radius:18px;padding:14px;margin:12px 0}.table{min-width:1180px;border:1px solid #243447;border-radius:18px;overflow:hidden}.table-head,.work-row{display:grid;grid-template-columns:1.1fr 1.4fr 1fr .75fr 1.4fr 1.6fr .7fr .6fr}.table-head b{background:#111827;color:#cbd5e1;padding:10px;border-right:1px solid #243447}.work-row>*{padding:10px;border-top:1px solid #243447;border-right:1px solid #243447;background:#07111f;font-size:13px}.work-row:hover>*{background:#0f172a}.red>*{border-left:4px solid #ef4444}.amber>*{border-left:4px solid #f59e0b}.green>*{border-left:4px solid #22c55e}.blue>*{border-left:4px solid #38bdf8}@media(max-width:900px){.wab{padding:10px}header{flex-direction:column}.table{min-width:1080px}}`;
