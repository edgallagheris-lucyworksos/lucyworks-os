"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthGuard } from "@/components/auth-guard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type CheckResult = { label: string; ok: boolean; detail: string };

const primaryLinks = [
  { href: "/hospital-board", label: "Hospital board", detail: "Person / role / location / time. Start here." },
  { href: "/workspace", label: "Workspace", detail: "Queued operational work and ownership." },
  { href: "/actions", label: "Actions", detail: "Escalate, assign, hold, resolve and hand over." },
  { href: "/flow-state", label: "Flow state", detail: "Live gates, bottlenecks and movement." },
] as const;

const secondaryLinks = [
  { href: "/readiness", label: "Readiness" },
  { href: "/departments", label: "Departments" },
  { href: "/lucy-pharm", label: "Pharmacy" },
  { href: "/lucyhr", label: "LucyHR" },
  { href: "/lucypulse", label: "LucyPulse" },
  { href: "/directory", label: "Directory" },
] as const;

async function check(url: string, label: string): Promise<CheckResult> {
  try {
    const response = await fetch(`${API_BASE}${url}`, { cache: "no-store" });
    return { label, ok: response.ok, detail: response.ok ? "online" : `HTTP ${response.status}` };
  } catch {
    return { label, ok: false, detail: "offline" };
  }
}

function SystemControlInner() {
  const [checking, setChecking] = useState(false);
  const [results, setResults] = useState<CheckResult[]>([]);

  async function runChecks() {
    setChecking(true);
    const next = await Promise.all([
      check("/api/health", "Backend"),
      check("/api/day-control/blocks", "Day control"),
      check("/api/day-control/governance-gates", "Governance gates"),
    ]);
    setResults(next);
    setChecking(false);
  }

  const ok = results.filter((item) => item.ok).length;
  const fail = results.filter((item) => !item.ok).length;

  return <main className="sys"><style>{css}</style><header><div><span>LucyWorks OS</span><h1>Clinical operations control</h1><p>Use the hospital board first. Backend checks are secondary and do not own the screen.</p></div><Link href="/hospital-board" className="primary">Open hospital board</Link></header><section className="notice"><b>Better operating model</b><p>This page is now a launch surface, not a wall of failing API diagnostics. If the backend is offline, open the board and use local/synced day-control state while the API is fixed.</p></section><section className="cards">{primaryLinks.map((item) => <Link href={item.href} className="card" key={item.href}><small>Open</small><b>{item.label}</b><p>{item.detail}</p></Link>)}</section><section className="panel"><div className="panelHead"><div><b>Backend status</b><p>Optional check. Failure here should not make the product unusable.</p></div><button onClick={runChecks} disabled={checking}>{checking ? "Checking..." : "Check backend"}</button></div>{results.length ? <div className="checks"><strong>{ok} online / {fail} offline</strong>{results.map((item) => <div className="check" key={item.label}><span>{item.label}</span><em className={item.ok ? "ok" : "bad"}>{item.detail}</em></div>)}</div> : <p className="muted">No check run yet.</p>}</section><nav>{secondaryLinks.map((item) => <Link href={item.href} key={item.href}>{item.label}</Link>)}</nav></main>;
}

export default function SystemControlPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin"]}>{() => <SystemControlInner />}</AuthGuard>;
}

const css = `.sys{min-height:100vh;background:#f3f4f6;color:#0f172a;padding:14px;font-family:Inter,system-ui,sans-serif}header{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;background:#fff;border:1px solid #dbe3ef;border-radius:18px;padding:16px;box-shadow:0 10px 30px rgba(15,23,42,.06)}header span{display:block;color:#475569;text-transform:uppercase;letter-spacing:.14em;font-size:11px;font-weight:900}h1{font-size:clamp(28px,7vw,54px);line-height:.95;margin:6px 0;color:#111827}p{color:#475569;margin:6px 0 0}.primary,button{border:0;border-radius:12px;background:#0f172a;color:white;padding:12px 14px;text-decoration:none;font-weight:800;white-space:nowrap}.notice{margin:12px 0;background:#e0f2fe;border:1px solid #bae6fd;border-radius:14px;padding:12px}.notice b{display:block}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.card{display:block;background:#fff;border:1px solid #dbe3ef;border-radius:16px;padding:14px;text-decoration:none;color:#0f172a;min-height:125px}.card small{color:#2563eb;font-weight:900;text-transform:uppercase;letter-spacing:.12em}.card b{display:block;font-size:22px;margin-top:12px}.panel{margin-top:12px;background:#fff;border:1px solid #dbe3ef;border-radius:16px;padding:14px}.panelHead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.panelHead b{font-size:20px}.muted{color:#64748b}.checks{display:grid;gap:8px;margin-top:10px}.checks strong{font-size:14px}.check{display:flex;justify-content:space-between;gap:8px;border-top:1px solid #e5e7eb;padding-top:8px}.check em{font-style:normal;border-radius:999px;padding:3px 9px;font-size:12px;font-weight:800}.ok{background:#dcfce7;color:#166534}.bad{background:#fee2e2;color:#991b1b}nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}nav a{background:#fff;border:1px solid #dbe3ef;border-radius:999px;padding:9px 12px;color:#0f172a;text-decoration:none;font-weight:700}@media(max-width:700px){header,.panelHead{display:grid}.primary,button{width:100%;text-align:center}.card{min-height:auto}}`;