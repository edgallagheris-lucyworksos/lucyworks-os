"use client";

import Link from "next/link";
import { useDayControlStore } from "@/lib/day-control-store";

export function RotaPressurePanel() {
  const { blocks } = useDayControlStore();
  const pressure = blocks.filter((block) => block.lane === "breaks" || block.blocker !== "none");
  return <section className="rpp"><style>{css}</style><header><span>Day-grid pressure</span><h2>Staff cover and blocker pressure</h2><p>These rows come from the same saved 15-minute day grid, so rota pressure is not a separate story.</p></header><div>{pressure.map((block) => <Link key={block.id} href={block.route}><b>{block.time} · {block.what}</b><span>{block.lane} · {block.who}</span><small>{block.blocker} → {block.next}</small></Link>)}</div></section>;
}

const css = `.rpp{display:grid;gap:10px;margin-bottom:14px;border:1px solid #28466e;border-radius:18px;background:#07111f;padding:12px;color:#e6edf7}.rpp header{border:0;background:transparent;padding:0}.rpp span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.rpp p,.rpp small,.rpp a span{color:#a7b5c8}.rpp div{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:8px}.rpp a{display:grid;gap:4px;border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:12px;padding:10px;text-decoration:none}.rpp a:hover{outline:2px solid #67e8f9}@media(max-width:900px){.rpp div{grid-template-columns:1fr}}`;
