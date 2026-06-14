"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type WorkItem = { id?: number; title?: string; urgency?: string; owner_role?: string; owner_user_id?: number | null; status?: string; description?: string; category?: string };
type QueueData = { work_items?: WorkItem[]; summary?: Record<string, number> };
type WorkCommand = "start" | "block" | "complete" | "return-to-queue";

async function getQueue(role: string): Promise<QueueData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/role-queues/my-shift?role=${encodeURIComponent(role)}`, { cache: "no-store" });
    return res.ok ? await res.json() : null;
  } catch { return null; }
}

async function sendWorkCommand(itemId: number, command: WorkCommand) {
  const res = await fetch(`${API_BASE}/api/actions/work-items/${itemId}/${command}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor_name: "LucyWorks UI", note: `${command} from My Shift` }),
  });
  if (!res.ok) throw new Error(`Work command failed: ${res.status}`);
  return res.json();
}

export function MyAssignedWorkBoard({ role = "nurse" }: { role?: string }) {
  const [data, setData] = useState<QueueData | null>(null);
  const [status, setStatus] = useState("ready");
  async function refresh() { setData(await getQueue(role)); }
  useEffect(() => { refresh(); }, [role]);
  async function run(item: WorkItem, command: WorkCommand) {
    if (!item.id) return;
    setStatus(`${command} ${item.title || item.id}`);
    try { await sendWorkCommand(item.id, command); await refresh(); setStatus("updated"); } catch { setStatus("backend unavailable"); }
  }
  const rows = data?.work_items || [];
  return <div className="assigned"><style>{css}</style><header><span>Role queue</span><h1>Assigned work</h1><p>Work arrives here from coordination. Staff start it, block it, complete it, or return wrong work to the queue. No accept/decline loop.</p><small>{status}</small></header><section className="grid">{rows.length ? rows.map((item) => <article className="card" key={item.id}><b>{item.title}</b><span>{item.urgency} · {item.status} · {item.category}</span><p>{item.description}</p><small>Role: {item.owner_role} · User: {item.owner_user_id || "role queue"}</small><div className="actions"><button onClick={() => run(item, "start")}>Start</button><button onClick={() => run(item, "block")}>Blocked</button><button onClick={() => run(item, "complete")}>Done</button><button onClick={() => run(item, "return-to-queue")}>Return to queue</button></div></article>) : <article className="card"><b>No open work found</b><p>Either the queue is clear or the backend is unavailable.</p></article>}</section></div>;
}

const css = `.assigned{min-height:100vh;background:#050b14;color:#e6edf7;padding:20px;font-family:Inter,system-ui,sans-serif}header{border:1px solid #274568;border-radius:24px;padding:22px;background:#07111f}header span{color:#5eead4;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}h1{font-size:clamp(36px,5vw,64px);line-height:.95;margin:8px 0}p,small,.card span{color:#a7b5c8}.grid{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:10px;margin-top:14px}.card{display:grid;gap:7px;border:1px solid #28466e;border-radius:14px;background:#101d31;padding:12px}.actions{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}.actions button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:999px;padding:8px;font-weight:800}@media(max-width:900px){.grid{grid-template-columns:1fr}}`;
