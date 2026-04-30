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
  assigned_staff_member_id?: number | null;
  starts_at: string;
  ends_at: string;
  status: string;
};

type Episode = { id: number; episode_ref: string; current_phase?: string | null; current_section_name?: string | null; current_room_name?: string | null };
type StaffLoad = { staff_member_id: number; name: string; role: string; skills: string; on_shift: boolean; active_blocks: number; assigned_block_ids: number[] };
type Pulse = { system_risk_level: string; case_pressure: number; resource_pressure: number; staff_pressure: number; capacity_pressure: number; execution_pressure: number; conflict_count: number; ethics_pressure: number; triage_pressure: number; lucy_care_pressure: number; owner_comms_pressure: number };
type AlertPayload = { total_alerts: number; high_alerts: number; alerts: any[] };
type RoomState = { id: number; room_name: string; department: string; state: string; current_episode_ref?: string | null; next_episode_ref?: string | null };

function startOfDay(date = new Date()) {
  const d = new Date(date);
  d.setHours(7, 0, 0, 0);
  return d;
}

function addMinutes(date: Date, minutes: number) {
  return new Date(date.getTime() + minutes * 60_000);
}

function timeLabel(date: Date | string) {
  return new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function overlaps(slotStart: Date, slotEnd: Date, block: ScheduleBlock) {
  const a = new Date(block.starts_at);
  const b = new Date(block.ends_at);
  return a < slotEnd && b > slotStart;
}

function blockTone(type: string) {
  if (type === "prep") return "#3b82f6";
  if (type === "anaesthesia") return "#a855f7";
  if (type === "procedure") return "#ef4444";
  if (type === "recovery") return "#22c55e";
  if (type === "cleaning") return "#f59e0b";
  return "#64748b";
}

function riskBorder(risk?: string) {
  if (risk === "red") return "1px solid #7f1d1d";
  if (risk === "amber") return "1px solid #78350f";
  return "1px solid #14532d";
}

export default function DashboardPage() {
  const [blocks, setBlocks] = useState<ScheduleBlock[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [staff, setStaff] = useState<StaffLoad[]>([]);
  const [pulse, setPulse] = useState<Pulse | null>(null);
  const [alerts, setAlerts] = useState<AlertPayload | null>(null);
  const [rooms, setRooms] = useState<RoomState[]>([]);
  const [selected, setSelected] = useState<{ slot: Date; blocks: ScheduleBlock[] } | null>(null);

  async function load() {
    const [blocksRes, episodesRes, staffRes, pulseRes, alertsRes, roomsRes] = await Promise.all([
      fetch(`${API_BASE}/api/schedule-blocks`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/episodes`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/staff-load`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/pulse`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/alerts`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/room-states`, { cache: "no-store" }),
    ]);
    setBlocks(await blocksRes.json());
    setEpisodes(await episodesRes.json());
    setStaff(await staffRes.json());
    setPulse(await pulseRes.json());
    setAlerts(await alertsRes.json());
    setRooms(await roomsRes.json());
  }

  useEffect(() => { load(); }, []);

  const episodeById = useMemo(() => { const map: Record<number, Episode> = {}; for (const ep of episodes) map[ep.id] = ep; return map; }, [episodes]);
  const staffById = useMemo(() => { const map: Record<number, StaffLoad> = {}; for (const s of staff) map[s.staff_member_id] = s; return map; }, [staff]);
  const slotRows = useMemo(() => {
    const start = startOfDay();
    return Array.from({ length: 56 }, (_, i) => {
      const slot = addMinutes(start, i * 15);
      const end = addMinutes(slot, 15);
      const active = blocks.filter((block) => overlaps(slot, end, block));
      return { slot, end, active };
    });
  }, [blocks]);

  const byRoom = useMemo(() => {
    const names = Array.from(new Set([...rooms.map((r) => r.room_name), ...blocks.map((b) => b.room_name || "Unassigned")])).sort();
    return names;
  }, [rooms, blocks]);

  const openSelected = selected?.blocks || [];

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => (
      <HospitalShell title="Operational Dashboard" subtitle="15-minute hospital control grid">
        <div style={{ display: "grid", gap: 16 }}>
          <section className="lw-card" style={{ padding: 18, border: riskBorder(pulse?.system_risk_level) }}>
            <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 16, alignItems: "end" }}>
              <div>
                <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Hospital live command</div>
                <h1 style={{ margin: "8px 0 0", fontSize: 38, letterSpacing: "-0.05em" }}>Main operational dashboard</h1>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>Every 15-minute slot is clickable. Click a slot to see procedure, cleaning, staff owner, room, episode and next action.</p>
              </div>
              <button onClick={load} className="lw-btn-primary" style={{ borderRadius: 14, padding: "12px 14px" }}>Refresh live state</button>
            </div>
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            {[
              ["Risk", pulse?.system_risk_level?.toUpperCase() || "-"],
              ["Alerts", `${alerts?.total_alerts ?? 0} / high ${alerts?.high_alerts ?? 0}`],
              ["Case pressure", pulse?.case_pressure ?? 0],
              ["Resource", pulse?.resource_pressure ?? 0],
              ["Staff", pulse?.staff_pressure ?? 0],
              ["Execution", pulse?.execution_pressure ?? 0],
              ["Conflicts", pulse?.conflict_count ?? 0],
              ["Rooms", rooms.length],
            ].map(([label, value]) => <div key={String(label)} className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 28, fontWeight: 900 }}>{value}</div></div>)}
          </section>

          <section className="lw-card" style={{ overflow: "hidden" }}>
            <div style={{ padding: 14, borderBottom: "1px solid #1f2937", display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>15-minute control grid</strong>
              <span style={{ color: "#94a3b8" }}>Rooms across columns, time down the left</span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <div style={{ minWidth: Math.max(980, 130 + byRoom.length * 170), display: "grid", gridTemplateColumns: `120px repeat(${byRoom.length}, minmax(160px, 1fr))` }}>
                <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>Time</div>
                {byRoom.map((room) => <div key={room} style={{ padding: 10, borderBottom: "1px solid #1f2937", borderLeft: "1px solid #1f2937", fontWeight: 800 }}>{room}</div>)}
                {slotRows.map((row) => (
                  <div key={row.slot.toISOString()} style={{ display: "contents" }}>
                    <button onClick={() => setSelected({ slot: row.slot, blocks: row.active })} style={{ padding: 10, border: 0, borderBottom: "1px solid #1f2937", background: "rgba(15,23,42,0.84)", color: "#f8fafc", textAlign: "left" }}>{timeLabel(row.slot)}</button>
                    {byRoom.map((room) => {
                      const active = row.active.filter((block) => (block.room_name || "Unassigned") === room);
                      return (
                        <button key={`${row.slot.toISOString()}-${room}`} onClick={() => setSelected({ slot: row.slot, blocks: active })} style={{ minHeight: 54, padding: 8, border: 0, borderLeft: "1px solid #1f2937", borderBottom: "1px solid #1f2937", background: active.length ? "rgba(20,184,166,0.08)" : "rgba(15,23,42,0.35)", textAlign: "left" }}>
                          {active.map((block) => {
                            const ep = episodeById[block.episode_id];
                            const assigned = block.assigned_staff_member_id ? staffById[block.assigned_staff_member_id] : null;
                            return <div key={block.id} style={{ borderLeft: `4px solid ${blockTone(block.block_type)}`, paddingLeft: 8, marginBottom: 6, color: "#f8fafc" }}><strong>{block.block_type}</strong><div style={{ color: "#94a3b8", fontSize: 12 }}>{ep?.episode_ref || `#${block.episode_id}`} • {assigned?.name || block.owner_role || "unowned"}</div></div>;
                          })}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="lw-card" style={{ padding: 16 }}>
            <h2 style={{ marginTop: 0 }}>Selected 15-minute slot</h2>
            {!selected ? <p style={{ color: "#94a3b8" }}>Click any time/room cell to inspect what is happening.</p> : null}
            {selected ? <div style={{ display: "grid", gap: 10 }}>
              <div style={{ color: "#94a3b8" }}>Slot: {timeLabel(selected.slot)} → {timeLabel(addMinutes(selected.slot, 15))}</div>
              {!openSelected.length ? <div style={{ color: "#94a3b8" }}>No scheduled block in this selected slot.</div> : null}
              {openSelected.map((block) => {
                const ep = episodeById[block.episode_id];
                const assigned = block.assigned_staff_member_id ? staffById[block.assigned_staff_member_id] : null;
                return <div key={block.id} style={{ border: `1px solid ${blockTone(block.block_type)}`, borderRadius: 14, padding: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{block.block_type.toUpperCase()} • {timeLabel(block.starts_at)}–{timeLabel(block.ends_at)}</strong>
                    <span>{block.room_name || "Unassigned"}</span>
                  </div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>Episode {ep?.episode_ref || block.episode_id} • phase {ep?.current_phase || "-"} • section {ep?.current_section_name || "-"}</div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>Owner {block.owner_role || "unowned"} • assigned {assigned?.name || "not assigned"}</div>
                  <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    {ep ? <Link href={`/episodes/${ep.episode_ref}`} className="lw-pill">Open episode</Link> : null}
                    <Link href="/schedule" className="lw-pill">Open schedule</Link>
                    <Link href="/command" className="lw-pill">Open command</Link>
                  </div>
                </div>;
              })}
            </div> : null}
          </section>
        </div>
      </HospitalShell>
    )}</AuthGuard>
  );
}
