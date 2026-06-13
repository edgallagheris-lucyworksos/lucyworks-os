"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { bvsFlowStages, moduleRoute } from "@/lib/bvs-flow-map";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
type FlowData = { summary?: Record<string, number>; slots?: Array<{ blocks?: any[] }> };
type PulseData = { state?: string; pressure_score?: number; red_conflicts?: number; amber_conflicts?: number; conflicts?: Array<{ department?: string; detail?: string; next_action?: string; severity?: string; type?: string }> };

function cls(value: string) { return value === "red" ? "red" : value === "amber" ? "amber" : value === "green" ? "green" : "blue"; }
function lower(value: unknown) { return String(value || "").toLowerCase(); }
function num(value: unknown) { const n = typeof value === "number" ? value : Number(value); return Number.isFinite(n) ? n : 0; }
function sourceLabel(source: string) { return source === "public_verified" ? "public verified" : "configurable"; }
function severity(value?: string) { const v = lower(value); return v.includes("red") || v.includes("high") || v.includes("critical") ? "red" : v.includes("amber") || v.includes("medium") ? "amber" : "blue"; }
async function getJson<T>(path: string): Promise<T | null> { try { const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" }); return res.ok ? await res.json() : null; } catch { return null; } }

function stageConflicts(stageId: string, pulse: PulseData | null) {
  const token = stageId.split("-")[0];
  return (pulse?.conflicts || []).filter((item) => `${lower(item.department)} ${lower(item.detail)} ${lower(item.type)} ${lower(item.next_action)}`.includes(token));
}

function StageCard({ stage, pulse }: { stage: typeof bvsFlowStages[number]; pulse: PulseData | null }) {
  const hits = stageConflicts(stage.id, pulse);
  const status = hits.find((hit) => severity(hit.severity) === "red") ? "red" : hits.length ? "amber" : stage.source === "public_verified" ? "blue" : "green";
  const live = hits[0];
  return <Link href={moduleRoute(stage.targetModule)} className={`stage ${cls(status)}`}><b>{stage.label}</b><span>{stage.lane} · {sourceLabel(stage.source)} · {stage.ownerRole}</span><p>{live?.next_action || live?.detail || stage.commonBlockers.join(" · ")}</p><small>Next: {stage.nextActions[0]}</small></Link>;
}

function Kpis({ flow, pulse }: { flow: FlowData | null; pulse: PulseData | null }) {
  const summary = flow?.summary || {};
  const red = num(pulse?.red_conflicts || summary.red_slots);
  const amber = num(pulse?.amber_conflicts || summary.amber_slots);
  const pressure = num(pulse?.pressure_score) || Math.min(100, red * 15 + amber * 6);
  const cards = [["Flow pressure", `${pressure}/100`, pressure >= 70 ? "red" : pressure >= 35 ? "amber" : "green"], ["Flow stages", String(bvsFlowStages.length), "blue"], ["Red blockers", String(red), red ? "red" : "green"], ["Amber blockers", String(amber), amber ? "amber" : "green"], ["Active slots", String(num(summary.active_slots)), "blue"], ["Schedule blocks", String(num(summary.schedule_blocks)), "blue"]] as const;
  return <section className="kpis">{cards.map(([label, value, tone]) => <div className={cls(tone)} key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>;
}

export function BvsFlowBoard() {
  const [flow, setFlow] = useState<FlowData | null>(null);
  const [pulse, setPulse] = useState<PulseData | null>(null);
  const [updated, setUpdated] = useState("fallback mode");
  useEffect(() => { let mounted = true; async function load() { const [dash, live] = await Promise.all([getJson<FlowData>("/api/dashboard/intelligence"), getJson<PulseData>("/api/conflict-engine/pulse")]); if (!mounted) return; setFlow(dash); setPulse(live); setUpdated(dash || live ? new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "fallback mode"); } load(); const timer = window.setInterval(load, 30000); return () => { mounted = false; window.clearInterval(timer); }; }, []);
  return <div className="flow"><style>{css}</style><header className="hero"><div><span>BVS flow map · {updated}</span><h1>LucyFlow patient movement</h1><p>Arrival, ECC stabilisation, imaging, service ownership, theatre/interventional work, recovery, ICU, ward, owner update and discharge.</p></div><nav><Link href="/hospital-board">Daily</Link><Link href="/resources">Resources</Link><Link href="/lucy-clinical">Clinical</Link></nav></header><Kpis flow={flow} pulse={pulse} /><div className="layout"><main><section className="panel"><h2>BVS movement pathway</h2><div className="stages">{bvsFlowStages.map((stage) => <StageCard key={stage.id} stage={stage} pulse={pulse} />)}</div></section></main><aside><section className="panel"><h2>Flow rule</h2><p>Every patient must have a current lane, named owner, blocker, destination and next action before movement is treated as safe.</p></section><section className="panel"><h2>High-friction points</h2>{["triage ownership", "ECC capacity", "imaging slot", "clinical owner", "procedure room", "recovery destination", "owner update", "discharge meds"].map((item) => <p className="line" key={item}>{item}</p>)}</section></aside></div></div>;
}

const css = `.flow{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}.hero{display:flex;justify-content:space-between;gap:18px;border:1px solid #274568;border-radius:24px;padding:22px;background:linear-gradient(135deg,#0c182a,#07111f)}.hero span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.hero h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}.hero p,.stage p,.stage span,.stage small,.panel p,.line{color:#a7b5c8}.hero nav{display:flex;gap:8px;flex-wrap:wrap}.hero a,.stage{color:#e6edf7;text-decoration:none}.hero a{border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:14px 0}.kpis div,.panel{background:#0b1728;border:1px solid #243b60;border-radius:18px;padding:14px}.kpis span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.kpis strong{font-size:28px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:14px}.stages{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:10px}.stage{display:grid;gap:7px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:12px}.red{border-color:#ef4444!important;background:#2a0d16!important}.amber{border-color:#f59e0b!important;background:#2a1a08!important}.green{border-color:#22c55e!important;background:#071d13!important}.blue{border-color:#38bdf8!important;background:#071a2a!important}.line{border-bottom:1px solid #1e3556;margin:0;padding:8px 0}@media(max-width:1100px){.layout{grid-template-columns:1fr}.stages{grid-template-columns:repeat(2,1fr)}.kpis{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.flow{padding:10px}.hero{flex-direction:column}.stages,.kpis{grid-template-columns:1fr}}`;
