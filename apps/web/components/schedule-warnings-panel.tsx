"use client";

import { detectDayControlRisks } from "@/lib/day-control-risks";
import { useDayControlStore } from "@/lib/day-control-store";

export function ScheduleWarningsPanel() {
  const { blocks } = useDayControlStore();
  const warnings = detectDayControlRisks(blocks);
  const red = warnings.filter((item) => item.level === "red").length;
  const amber = warnings.filter((item) => item.level === "amber").length;

  return <section className="swp"><style>{css}</style><header><span>Warnings</span><h2>{red} red / {amber} amber</h2><p>Detected from the saved 15-minute schedule.</p></header><div>{warnings.length ? warnings.slice(0, 8).map((item) => <article key={item.id} className={item.level}><b>{item.title}</b><small>{item.detail}</small></article>) : <article className="blue"><b>No warnings</b><small>No blocker, update, cover or clash warnings detected.</small></article>}</div></section>;
}

const css = `.swp{display:grid;gap:10px;margin:10px 0;border:1px solid #28466e;border-radius:16px;background:#07111f;padding:12px;color:#e6edf7}.swp header{border:0;background:transparent;padding:0}.swp span{color:#67e8f9;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.swp h2{margin:4px 0;font-size:24px}.swp p,.swp small{color:#a7b5c8}.swp div{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:8px}.swp article{border:1px solid #31557f;background:#10223c;border-radius:12px;padding:10px}.swp article b{display:block;margin-bottom:4px}.red{border-left:5px solid #ef4444!important}.amber{border-left:5px solid #f59e0b!important}.blue{border-left:5px solid #38bdf8!important}@media(max-width:1100px){.swp div{grid-template-columns:1fr}}`;
