"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type AuditEvent = { id: string; time: string; blockId: string; action: string; actor: string; reason?: string | null };

export function DayControlAuditPanel() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    fetch(`${API_BASE}/api/day-control/audit`).then((response) => response.json()).then((data) => {
      setEvents(Array.isArray(data.audit) ? data.audit.slice(-10).reverse() : []);
      setStatus("ready");
    }).catch(() => setStatus("offline"));
  }, []);

  return <section className="audit"><style>{css}</style><header><span>Audit</span><h2>Day-control actions</h2><p>{status === "offline" ? "Backend offline; local board still works." : "Latest persisted block actions."}</p></header>{events.length ? events.map((event) => <article key={event.id}><b>{event.action}</b><small>{event.time} · {event.actor} · {event.blockId}</small></article>) : <article><b>No audit events yet</b><small>Actions will appear here after backend action calls are made.</small></article>}</section>;
}

const css = `.audit{display:grid;gap:8px;border:1px solid #28466e;border-radius:16px;background:#07111f;padding:12px;color:#e6edf7}.audit header{border:0;background:transparent;padding:0}.audit span{color:#67e8f9;text-transform:uppercase;letter-spacing:.13em;font-weight:900;font-size:12px}.audit h2{margin:4px 0}.audit p,.audit small{color:#a7b5c8}.audit article{border:1px solid #31557f;background:#10223c;border-radius:12px;padding:10px}.audit article b{display:block}`;
