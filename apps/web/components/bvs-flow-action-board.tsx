"use client";

import Link from "next/link";
import { useState } from "react";
import { bvsFlowStages } from "@/lib/bvs-flow-map";
import { OperationalDetailDrawer } from "@/components/operational-detail-drawer";
import type { OperationalTarget } from "@/lib/operational-actions";

function sourceLabel(source: string) { return source === "public_verified" ? "public verified" : "configurable"; }
function target(stage: typeof bvsFlowStages[number]): OperationalTarget { return { id: stage.id, label: stage.label, type: "flow-stage", lane: stage.lane, source: stage.source, ownerRole: stage.ownerRole, blocker: stage.commonBlockers[0], nextAction: stage.nextActions[0] }; }

export function BvsFlowActionBoard() {
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  return <div className="flow"><style>{css}</style><header><div><span>BVS flow action loop</span><h1>LucyFlow patient movement</h1><p>Click a stage to assign, escalate, resolve, handover, hold or request review.</p></div><nav><Link href="/hospital-board">Daily</Link><Link href="/resources">Resources</Link><Link href="/lucy-clinical">Clinical</Link></nav></header><main><section className="kpis"><div><span>Stages</span><strong>{bvsFlowStages.length}</strong></div><div><span>Rule</span><strong>Owner + blocker + next</strong></div></section><section className="grid">{bvsFlowStages.map((stage) => <button key={stage.id} type="button" onClick={() => setSelected(target(stage))} className="card"><b>{stage.label}</b><span>{stage.lane} · {sourceLabel(stage.source)}</span><p>{stage.commonBlockers.join(" · ")}</p><small>Next: {stage.nextActions[0]}</small></button>)}</section></main><OperationalDetailDrawer target={selected} onClose={() => setSelected(null)} /></div>;
}

const css = `.flow{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}header{display:flex;justify-content:space-between;gap:18px;border:1px solid #274568;border-radius:24px;padding:22px;background:#07111f}header span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}p,small,.card span{color:#a7b5c8}nav{display:flex;gap:8px;flex-wrap:wrap}nav a{color:#e6edf7;text-decoration:none;border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:14px 0}.kpis div{background:#0b1728;border:1px solid #243b60;border-radius:18px;padding:14px}.kpis span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.grid{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:10px}.card{display:grid;gap:7px;text-align:left;color:#e6edf7;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:12px}.card:hover{outline:2px solid #5eead4}@media(max-width:900px){.grid{grid-template-columns:1fr}header{flex-direction:column}}`;
