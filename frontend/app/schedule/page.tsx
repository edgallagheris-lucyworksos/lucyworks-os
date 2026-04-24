"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ScheduleBlock = {
  id: number;
  episode_id: number;
  block_type: string;
  room_name?: string | null;
  owner_role?: string | null;
  starts_at: string;
  ends_at: string;
  status: string;
};

function colour(blockType: string) {
  if (blockType === "prep") return "#3b82f6";
  if (blockType === "anaesthesia") return "#a855f7";
  if (blockType === "procedure") return "#ef4444";
  if (blockType === "recovery") return "#22c55e";
  if (blockType === "cleaning") return "#f59e0b";
  return "#64748b";
}

function timeLabel(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function SchedulePage() {
  const [blocks, setBlocks] = useState<ScheduleBlock[]>([]);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/schedule-blocks`, { cache: "no-store" });
      setBlocks(await res.json());
    }
    load();
  }, []);

  const rooms = useMemo(() => Array.from(new Set(blocks.map((b) => b.room_name || "Unassigned"))).sort(), [blocks]);
  const grouped = useMemo(() => {
    const map: Record<string, ScheduleBlock[]> = {};
    for (const block of blocks) {
      const room = block.room_name || "Unassigned";
      map[room] = map[room] || [];
      map[room].push(block);
    }
    for (const room of Object.keys(map)) {
      map[room].sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
    }
    return map;
  }, [blocks]);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse"]}>
      {() => (
        <HospitalShell title="Schedule" subtitle="Room-based procedure timeline">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
            <div style={{ color: "#94a3b8" }}>Prep → Anaesthesia → Procedure → Recovery → Cleaning</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["prep", "anaesthesia", "procedure", "recovery", "cleaning"].map((item) => (
                <span key={item} style={{ border: `1px solid ${colour(item)}`, borderRadius: 999, padding: "6px 10px" }}>{item}</span>
              ))}
            </div>
          </div>

          <div style={{ display: "grid", gap: 16 }}>
            {rooms.map((room) => (
              <section key={room} style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden", background: "#0f172a" }}>
                <div style={{ padding: 14, borderBottom: "1px solid #1f2937", display: "flex", justifyContent: "space-between" }}>
                  <strong>{room}</strong>
                  <span style={{ color: "#94a3b8" }}>{grouped[room]?.length || 0} blocks</span>
                </div>
                <div style={{ padding: 14, display: "grid", gap: 10 }}>
                  {(grouped[room] || []).map((block) => (
                    <div key={block.id} style={{ border: `1px solid ${colour(block.block_type)}`, borderRadius: 14, padding: 12, display: "grid", gridTemplateColumns: "130px 1fr 120px", gap: 12, alignItems: "center" }}>
                      <strong>{timeLabel(block.starts_at)} → {timeLabel(block.ends_at)}</strong>
                      <div>
                        <div style={{ fontWeight: 700 }}>{block.block_type.toUpperCase()}</div>
                        <div style={{ color: "#94a3b8" }}>episode #{block.episode_id} • owner {block.owner_role || "unassigned"}</div>
                      </div>
                      <Link href="/episodes" style={{ textAlign: "right" }}>Open cases</Link>
                    </div>
                  ))}
                  {!grouped[room]?.length ? <div style={{ color: "#94a3b8" }}>No schedule blocks.</div> : null}
                </div>
              </section>
            ))}
            {!rooms.length ? <div style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16 }}>No schedule blocks yet. Generate a procedure schedule from the API to populate this view.</div> : null}
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
