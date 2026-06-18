"use client";

import { useState } from "react";
import { QueueDetailDrawer } from "@/components/queue-detail-drawer";
import type { OperationalTarget } from "@/lib/operational-actions";
import { scheduledWorkBlocks, type ScheduledWorkBlock } from "@/lib/day-control-work";

function roleMatches(role: string, block: ScheduledWorkBlock) {
  const value = `${block.lane} ${block.who} ${block.what}`.toLowerCase();
  const r = role.toLowerCase();
  if (r.includes("nurse")) return value.includes("nursing") || value.includes("care") || value.includes("handover");
  if (r.includes("admin")) return value.includes("client") || value.includes("intake");
  if (r.includes("clinician") || r.includes("clinical")) return value.includes("decision") || value.includes("review") || value.includes("signoff");
  if (r.includes("ops")) return value.includes("break") || value.includes("cover") || value.includes("capacity");
  return block.status === "red" || block.status === "amber";
}

function toTarget(block: ScheduledWorkBlock): OperationalTarget {
  return { id: block.id, label: `${block.time} / ${block.what}`, type: "my_timed_work", lane: block.lane, source: "my-shift", ownerRole: block.who, blocker: block.blocker, nextAction: block.next, route: block.route };
}

export function MyTimedWorkBoard({ role = "nurse" }: { role?: string }) {
  const [selected, setSelected] = useState<OperationalTarget | null>(null);
  const timed = scheduledWorkBlocks.filter((block) => roleMatches(role, block));
  return <section className="mtw"><style>{css}</style><header><span>15-minute day grid</span><h2>Timed work</h2><p>Same source as the day-control grid. This prevents My Shift becoming a separate fake task list.</p></header>{timed.map((block) => <button type="button" key={block.id} className={`row ${block.status}`} onClick={() => setSelected(toTarget(block))}><b>{block.time} · {block.what}</b><span>{block.lane} · {block.who}</span><small>{block.blocker} → {block.next}</small></button>)}<QueueDetailDrawer target={selected} onClose={() => setSelected(null)} /></section>;
}

const css = `.mtw{display:grid;gap:8px;margin:14px 0;border:1px solid #28466e;border-radius:18px;background:#07111f;padding:12px;color:#e6edf7}.mtw header{border:0;padding:0;background:transparent}.mtw span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.mtw p,.mtw small,.row span{color:#a7b5c8}.row{display:grid;gap:4px;border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:12px;padding:10px;text-align:left}.row:hover{outline:2px solid #67e8f9}.red{border-left:5px solid #ef4444}.amber{border-left:5px solid #f59e0b}.green{border-left:5px solid #22c55e}.blue{border-left:5px solid #38bdf8}`;
