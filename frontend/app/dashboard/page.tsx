"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type DashboardBlock = {
  block_id: number;
  block_type: string;
  starts_at: string;
  ends_at: string;
  status: string;
  room: { name?: string | null; state?: string | null; department?: string | null };
  owner_role?: string | null;
  assigned_staff?: { id: number; name: string; role: string; skills: string } | null;
  episode?: { episode_id: number; episode_ref: string; phase?: string | null; section?: string | null; room?: string | null; patient?: { name?: string | null; species?: string | null; owner_name?: string | null } } | null;
  procedure?: { name?: string | null; department?: string | null; case_procedure_id?: number | null } | null;
  operating?: { template?: any; family?: any; anaesthesia?: any; recovery?: any; cleaning?: any } | null;
  pressure: { hard_blocks: any[]; warnings: any[]; counts: Record<string, number>; next_action?: any | null };
  next_action?: any | null;
};

type DashboardSlot = {
  slot_index: number;
  starts_at: string;
  ends_at: string;
  active_count: number;
  hard_block_count: number;
  warning_count: number;
  risk: "red" | "amber" | "green";
  blocks: DashboardBlock[];
};

type DashboardIntelligence = {
  generated_at: string;
  dashboard_basis: string;
  summary: Record<string, number>;
  rooms: { room_name: string; department: string; state: string }[];
  slots: DashboardSlot[];
  conflicts: any[];
  alerts: any[];
};

function timeLabel(date: Date | string) {
  return new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

function riskBg(risk?: string) {
  if (risk === "red") return "rgba(127,29,29,0.26)";
  if (risk === "amber") return "rgba(120,53,15,0.24)";
  return "rgba(15,23,42,0.35)";
}

export default function DashboardPage() {
  const [intel, setIntel] = useState<DashboardIntelligence | null>(null);
  const [selected, setSelected] = useState<{ slot: DashboardSlot; room: string; blocks: DashboardBlock[] } | null>(null);

  async function load() {
    const res = await fetch(`${API_BASE}/api/dashboard/intelligence`, { cache: "no-store" });
    if (res.ok) setIntel(await res.json());
  }

  useEffect(() => { load(); }, []);

  const rooms = useMemo(() => {
    if (!intel) return [];
    const names = Array.from(new Set([...intel.rooms.map((r) => r.room_name), ...intel.slots.flatMap((s) => s.blocks.map((b) => b.room.name || "Unassigned"))]));
    return names.sort();
  }, [intel]);

  const selectedBlocks = selected?.blocks || [];
  const selectedHard = selectedBlocks.flatMap((b) => b.pressure?.hard_blocks || []);
  const selectedWarnings = selectedBlocks.flatMap((b) => b.pressure?.warnings || []);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => (
      <HospitalShell title="Operational Dashboard" subtitle="15-minute live hospital command grid">
        <div style={{ display: "grid", gap: 16 }}>
          <section className="lw-card" style={{ padding: 18, border: riskBorder((intel?.summary?.red_slots || 0) > 0 ? "red" : (intel?.summary?.amber_slots || 0) > 0 ? "amber" : "green") }}>
            <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 16, alignItems: "end" }}>
              <div>
                <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>Dashboard-first operating spine</div>
                <h1 style={{ margin: "8px 0 0", fontSize: 38, letterSpacing: "-0.05em" }}>Main operational dashboard</h1>
                <p style={{ color: "#94a3b8", marginBottom: 0 }}>This page is fed by the central dashboard intelligence API. Slots carry case, procedure, room, staff, operating standards, blockers, warnings and next action.</p>
              </div>
              <button onClick={load} className="lw-btn-primary" style={{ borderRadius: 14, padding: "12px 14px" }}>Refresh live state</button>
            </div>
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            {[
              ["Active slots", intel?.summary?.active_slots ?? 0],
              ["Red slots", intel?.summary?.red_slots ?? 0],
              ["Amber slots", intel?.summary?.amber_slots ?? 0],
              ["Alerts", `${intel?.summary?.alerts ?? 0} / high ${intel?.summary?.high_alerts ?? 0}`],
              ["Conflicts", intel?.summary?.conflicts ?? 0],
              ["Open work", intel?.summary?.open_work ?? 0],
              ["Blocks", intel?.summary?.schedule_blocks ?? 0],
              ["Rooms", intel?.summary?.rooms ?? 0],
            ].map(([label, value]) => <div key={String(label)} className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 28, fontWeight: 900 }}>{value}</div></div>)}
          </section>

          <section className="lw-card" style={{ overflow: "hidden" }}>
            <div style={{ padding: 14, borderBottom: "1px solid #1f2937", display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>15-minute dashboard control grid</strong>
              <span style={{ color: "#94a3b8" }}>Red/amber cells include slot-level blocker pressure from the linked episode.</span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <div style={{ minWidth: Math.max(980, 130 + rooms.length * 190), display: "grid", gridTemplateColumns: `120px repeat(${rooms.length}, minmax(180px, 1fr))` }}>
                <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>Time</div>
                {rooms.map((room) => <div key={room} style={{ padding: 10, borderBottom: "1px solid #1f2937", borderLeft: "1px solid #1f2937", fontWeight: 800 }}>{room}</div>)}
                {(intel?.slots || []).map((slot) => (
                  <div key={slot.slot_index} style={{ display: "contents" }}>
                    <button onClick={() => setSelected({ slot, room: "All rooms", blocks: slot.blocks })} style={{ padding: 10, border: 0, borderBottom: "1px solid #1f2937", background: riskBg(slot.risk), color: "#f8fafc", textAlign: "left" }}>
                      <strong>{timeLabel(slot.starts_at)}</strong>
                      <div style={{ color: "#94a3b8", fontSize: 11 }}>{slot.active_count} active • {slot.hard_block_count} hard • {slot.warning_count} warn</div>
                    </button>
                    {rooms.map((room) => {
                      const active = slot.blocks.filter((block) => (block.room.name || "Unassigned") === room);
                      const hard = active.reduce((sum, block) => sum + (block.pressure?.hard_blocks?.length || 0), 0);
                      const warn = active.reduce((sum, block) => sum + (block.pressure?.warnings?.length || 0), 0);
                      const cellRisk = hard ? "red" : warn ? "amber" : active.length ? "green" : "empty";
                      return (
                        <button key={`${slot.slot_index}-${room}`} onClick={() => setSelected({ slot, room, blocks: active })} style={{ minHeight: 62, padding: 8, border: 0, borderLeft: "1px solid #1f2937", borderBottom: "1px solid #1f2937", background: active.length ? riskBg(cellRisk) : "rgba(15,23,42,0.28)", textAlign: "left" }}>
                          {active.map((block) => (
                            <div key={block.block_id} style={{ borderLeft: `4px solid ${blockTone(block.block_type)}`, paddingLeft: 8, marginBottom: 6, color: "#f8fafc" }}>
                              <strong>{block.block_type}</strong>
                              <div style={{ color: "#94a3b8", fontSize: 12 }}>{block.episode?.episode_ref || "no episode"} • {block.assigned_staff?.name || block.owner_role || "unowned"}</div>
                              {(block.pressure?.hard_blocks?.length || 0) + (block.pressure?.warnings?.length || 0) > 0 ? <div style={{ color: "#fca5a5", fontSize: 11 }}>{block.pressure.hard_blocks.length} hard • {block.pressure.warnings.length} warn</div> : null}
                            </div>
                          ))}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="lw-card" style={{ padding: 16 }}>
            <h2 style={{ marginTop: 0 }}>Selected dashboard slot</h2>
            {!selected ? <p style={{ color: "#94a3b8" }}>Click any time/room cell to inspect procedure, operating standards, blockers and next action.</p> : null}
            {selected ? <div style={{ display: "grid", gap: 12 }}>
              <div style={{ color: "#94a3b8" }}>Slot: {timeLabel(selected.slot.starts_at)} → {timeLabel(selected.slot.ends_at)} • {selected.room} • risk {selected.slot.risk}</div>
              {!selectedBlocks.length ? <div style={{ color: "#94a3b8" }}>No scheduled work in this selected cell.</div> : null}
              {selectedBlocks.map((block) => (
                <div key={block.block_id} style={{ border: `1px solid ${blockTone(block.block_type)}`, borderRadius: 14, padding: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{block.block_type.toUpperCase()} • {timeLabel(block.starts_at)}–{timeLabel(block.ends_at)}</strong>
                    <span>{block.room.name || "Unassigned"} • {block.room.state || "no room state"}</span>
                  </div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>Episode {block.episode?.episode_ref || "-"} • patient {block.episode?.patient?.name || "-"} • owner {block.episode?.patient?.owner_name || "-"}</div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>Procedure {block.procedure?.name || "-"} • family {block.operating?.template?.family || "-"} • anaesthesia {block.operating?.template?.anaesthesia_level || "-"} • recovery {block.operating?.template?.recovery_class || "-"} • cleaning {block.operating?.template?.cleaning_standard || "-"}</div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>Owner role {block.owner_role || "unowned"} • assigned {block.assigned_staff?.name || "not assigned"}</div>
                  {block.next_action ? <div style={{ marginTop: 10, border: "1px solid #78350f", borderRadius: 12, padding: 10 }}><strong>Next action</strong><div style={{ color: "#94a3b8", marginTop: 4 }}>{block.next_action.section} • {block.next_action.urgency} • {block.next_action.detail} • owner {block.next_action.owner_role}</div></div> : null}
                  {block.pressure?.hard_blocks?.length ? <div style={{ marginTop: 10 }}><strong>Hard blockers</strong>{block.pressure.hard_blocks.map((item, index) => <div key={`${item.type}-${index}`} style={{ color: "#fca5a5", marginTop: 4 }}>{item.section}: {item.detail} • owner {item.owner_role}</div>)}</div> : null}
                  {block.pressure?.warnings?.length ? <div style={{ marginTop: 10 }}><strong>Warnings</strong>{block.pressure.warnings.map((item, index) => <div key={`${item.type}-${index}`} style={{ color: "#fbbf24", marginTop: 4 }}>{item.section}: {item.detail} • owner {item.owner_role}</div>)}</div> : null}
                  <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    {block.episode?.episode_ref ? <Link href={`/episodes/${block.episode.episode_ref}`} className="lw-pill">Open episode</Link> : null}
                    <Link href="/schedule" className="lw-pill">Schedule</Link>
                    <Link href="/command" className="lw-pill">Command</Link>
                    <Link href="/queues" className="lw-pill">Queues</Link>
                  </div>
                </div>
              ))}
              {(selectedHard.length || selectedWarnings.length) ? <div className="lw-card" style={{ padding: 14 }}><strong>Slot pressure summary</strong><div style={{ color: "#94a3b8", marginTop: 6 }}>Hard blockers {selectedHard.length} • warnings {selectedWarnings.length}</div></div> : null}
            </div> : null}
          </section>
        </div>
      </HospitalShell>
    )}</AuthGuard>
  );
}
