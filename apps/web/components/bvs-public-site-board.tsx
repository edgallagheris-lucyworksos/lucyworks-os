"use client";

import Link from "next/link";
import { bvsPublicCapacityAreas, bvsPublicTeamScale, bvsPublicWorkforceGroups } from "@/lib/bvs-public-operating-scale";
import { bvsPublicPathways } from "@/lib/bvs-public-pathways";
import { bvsPublicRoleMap } from "@/lib/bvs-public-role-map";
import { bvsServiceWorkflows } from "@/lib/bvs-service-workflows";

function route(module: string) {
  if (module === "LucyFlow") return "/flow";
  if (module === "LucyOps") return "/resources";
  if (module === "LucyComms") return "/lucy-comms";
  if (module === "LucyPharm") return "/lucy-pharm";
  if (module === "LucyKnowledge") return "/lucy-knowledge";
  return "/lucy-clinical";
}

export function BvsPublicSiteBoard() {
  return <div className="bvs"><style>{css}</style><header><div><span>BVS public website model</span><h1>BVS public operating map</h1><p>Public facts converted into LucyWorks services, pathways, role queues and configurable capacity areas.</p></div><nav><Link href="/lucy-clinical">Clinical</Link><Link href="/flow">Flow</Link><Link href="/resources">Resources</Link></nav></header><section className="kpis"><div><span>Public team</span><b>{bvsPublicTeamScale.publicMinimumTeamSize}+</b></div><div><span>Services</span><b>{bvsServiceWorkflows.length}</b></div><div><span>Pathways</span><b>{bvsPublicPathways.length}</b></div><div><span>Role groups</span><b>{bvsPublicRoleMap.length}</b></div></section><main><section><h2>Public pathways</h2><div className="grid">{bvsPublicPathways.map((item) => <Link className="card" href={route(item.lucyModule)} key={item.id}><b>{item.label}</b><small>{item.publicEvidence}</small><span>{item.queueTargets.join(" · ")}</span></Link>)}</div></section><section><h2>Role and escalation map</h2><div className="grid">{bvsPublicRoleMap.map((item) => <article className="card" key={item.id}><b>{item.publicRoleGroup}</b><small>{item.publicEvidence}</small><span>{item.queueTarget}</span></article>)}</div></section><section><h2>Capacity areas</h2><div className="grid">{bvsPublicCapacityAreas.map((item) => <article className="card" key={item.id}><b>{item.label}</b><small>{item.publicCapacity === null ? "capacity unpublished" : `capacity ${item.publicCapacity}`}</small><span>{item.tracks.join(" · ")}</span></article>)}</div></section><section><h2>Workforce groups</h2><div className="grid">{bvsPublicWorkforceGroups.map((item) => <article className="card" key={item.id}><b>{item.label}</b><small>{item.evidence}</small><span>{item.queueTargets.join(" · ")}</span></article>)}</div></section></main></div>;
}

const css = `.bvs{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}header{display:flex;justify-content:space-between;gap:18px;border:1px solid #274568;border-radius:24px;padding:22px;background:#07111f}header span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:900}h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}p,small{color:#a7b5c8}nav{display:flex;gap:8px;flex-wrap:wrap}a{color:#e6edf7;text-decoration:none}nav a{border:1px solid #31557f;background:#10223c;border-radius:999px;padding:9px 12px;font-weight:800}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}.kpis div,section{background:#0b1728;border:1px solid #243b60;border-radius:18px;padding:14px}.kpis span{display:block;color:#9fb0c6;text-transform:uppercase;font-size:11px}.kpis b{font-size:28px}.grid{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:10px}.card{display:grid;gap:7px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:12px}.card span{font-size:12px;color:#5eead4;text-transform:uppercase;font-weight:900}@media(max-width:900px){.grid,.kpis{grid-template-columns:1fr}header{flex-direction:column}}`;
