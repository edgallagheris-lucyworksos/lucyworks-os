"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { ClinicalDirectorReadPanel } from "@/components/clinical-director-read";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Block = {
  block_id: number;
  block_type: string;
  starts_at: string;
  ends_at: string;
  room: { name?: string | null; state?: string | null; department?: string | null };
  owner_role?: string | null;
  assigned_staff?: { name: string; role: string; skills: string } | null;
  episode?: { episode_ref: string; phase?: string | null; section?: string | null; patient?: { name?: string | null; species?: string | null; owner_name?: string | null } } | null;
  procedure?: { name?: string | null; department?: string | null } | null;
  operating?: { template?: any; required_roles?: string[]; room_options?: string[]; readiness_gates?: string[]; dependency_layers?: any[]; blockers_to_watch?: string[]; total_minutes?: number; schedule_chain?: any[] } | null;
  dependency?: { can_start: boolean; risk: string; cannot_start_reason?: string | null; hard_failures: any[]; warnings: any[]; next_action?: any | null; checks: Record<string, boolean> } | null;
  pressure: { hard_blocks: any[]; warnings: any[] };
  next_action?: any | null;
};

type Slot = { slot_index: number; starts_at: string; ends_at: string; active_count: number; hard_block_count: number; warning_count: number; risk: "red" | "amber" | "green"; blocks: Block[] };
type Dashboard = { summary: Record<string, number>; rooms: { room_name: string; department: string; state: string }[]; slots: Slot[] };

function t(value: string) { return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function bg(risk?: string) { if (risk === "red") return "rgba(127,29,29,0.28)"; if (risk === "amber") return "rgba(120,53,15,0.24)"; return "rgba(15,23,42,0.34)"; }
function tone(type?: string) { if (type === "anaesthesia") return "#a855f7"; if (type === "procedure") return "#ef4444"; if (type === "recovery") return "#22c55e"; if (type === "cleaning") return "#f59e0b"; return "#3b82f6"; }

function CheckGrid({ checks }: { checks?: Record<string, boolean> }) {
  const entries = Object.entries(checks || {});
  if (!entries.length) return null;
  return <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8, marginTop: 10 }}>{entries.map(([key, ok]) => <div key={key} style={{ border: ok ? "1px solid #14532d" : "1px solid #7f1d1d", borderRadius: 10, padding: 8 }}><strong>{ok ? "OK" : "FAIL"}</strong><div style={{ color: "#94a3b8", fontSize: 12 }}>{key.replaceAll("_", " ")}</div></div>)}</div>;
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [selected, setSelected] = useState<{ slot: Slot; room: string; blocks: Block[] } | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    const res = await fetch(`${API_BASE}/api/dashboard/intelligence`, { cache: "no-store" });
    if (!res.ok) { setError("Dashboard intelligence failed to load."); return; }
    setData(await res.json());
  }

  useEffect(() => { load(); }, []);
  const rooms = useMemo(() => data ? Array.from(new Set([...data.rooms.map((r) => r.room_name), ...data.slots.flatMap((s) => s.blocks.map((b) => b.room.name || "Unassigned"))])).sort() : [], [data]);

  return <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>{() => <HospitalShell title="Clinical Director Dashboard" subtitle="Command read, 15-minute grid, slot dependency intelligence"><div style={{ display: "grid", gap: 16 }}>
    <ClinicalDirectorReadPanel />
    {error ? <section className="lw-card" style={{ padding: 14, border: "1px solid #7f1d1d" }}>{error}</section> : null}

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
      {[["Active slots", data?.summary?.active_slots ?? 0], ["Red slots", data?.summary?.red_slots ?? 0], ["Amber slots", data?.summary?.amber_slots ?? 0], ["Alerts", `${data?.summary?.alerts ?? 0} / high ${data?.summary?.high_alerts ?? 0}`], ["Conflicts", data?.summary?.conflicts ?? 0], ["Open work", data?.summary?.open_work ?? 0], ["Blocks", data?.summary?.schedule_blocks ?? 0], ["Rooms", data?.summary?.rooms ?? 0]].map(([label, value]) => <div key={String(label)} className="lw-card" style={{ padding: 14 }}><div style={{ color: "#94a3b8" }}>{label}</div><div style={{ fontSize: 28, fontWeight: 900 }}>{value}</div></div>)}
    </section>

    <section className="lw-card" style={{ overflow: "hidden" }}><div style={{ padding: 14, borderBottom: "1px solid #1f2937", display: "flex", gap: 12, justifyContent: "space-between", flexWrap: "wrap" }}><strong>15-minute hospital control grid</strong><button className="lw-pill" onClick={load}>Refresh grid</button><span style={{ color: "#94a3b8" }}>Click a cell to inspect can-start state, failures, roles, gates and next action.</span></div><div style={{ overflowX: "auto" }}><div style={{ minWidth: Math.max(980, 120 + rooms.length * 190), display: "grid", gridTemplateColumns: `120px repeat(${rooms.length}, minmax(180px, 1fr))` }}>
      <div style={{ padding: 10, borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>Time</div>{rooms.map((room) => <div key={room} style={{ padding: 10, borderLeft: "1px solid #1f2937", borderBottom: "1px solid #1f2937", fontWeight: 800 }}>{room}</div>)}
      {(data?.slots || []).map((slot) => <div key={slot.slot_index} style={{ display: "contents" }}><button onClick={() => setSelected({ slot, room: "All rooms", blocks: slot.blocks })} style={{ padding: 10, border: 0, borderBottom: "1px solid #1f2937", background: bg(slot.risk), color: "#f8fafc", textAlign: "left" }}><strong>{t(slot.starts_at)}</strong><div style={{ color: "#94a3b8", fontSize: 11 }}>{slot.active_count} active • {slot.hard_block_count} hard • {slot.warning_count} warn</div></button>{rooms.map((room) => { const blocks = slot.blocks.filter((b) => (b.room.name || "Unassigned") === room); const hard = blocks.reduce((n, b) => n + (b.pressure?.hard_blocks?.length || 0), 0); const warn = blocks.reduce((n, b) => n + (b.pressure?.warnings?.length || 0), 0); const risk = hard ? "red" : warn ? "amber" : blocks.length ? "green" : "empty"; return <button key={`${slot.slot_index}-${room}`} onClick={() => setSelected({ slot, room, blocks })} style={{ minHeight: 62, padding: 8, border: 0, borderLeft: "1px solid #1f2937", borderBottom: "1px solid #1f2937", background: blocks.length ? bg(risk) : "rgba(15,23,42,0.24)", textAlign: "left" }}>{blocks.map((block) => <div key={block.block_id} style={{ borderLeft: `4px solid ${tone(block.block_type)}`, paddingLeft: 8, marginBottom: 6, color: "#f8fafc" }}><strong>{block.block_type}</strong><div style={{ color: "#94a3b8", fontSize: 12 }}>{block.episode?.episode_ref || "no episode"} • {block.dependency?.can_start ? "can start" : "blocked"}</div>{hard || warn ? <div style={{ color: "#fca5a5", fontSize: 11 }}>{hard} hard • {warn} warn</div> : null}</div>)}</button>; })}</div>)}
    </div></div></section>

    <section className="lw-card" style={{ padding: 16 }}><h2 style={{ marginTop: 0 }}>Selected 15-minute slot</h2>{!selected ? <p style={{ color: "#94a3b8" }}>No slot selected.</p> : <div style={{ display: "grid", gap: 12 }}><div style={{ color: "#94a3b8" }}>{t(selected.slot.starts_at)} → {t(selected.slot.ends_at)} • {selected.room} • {selected.slot.risk}</div>{!selected.blocks.length ? <div style={{ color: "#94a3b8" }}>No scheduled work in this cell.</div> : null}{selected.blocks.map((block) => <article key={block.block_id} style={{ border: `1px solid ${tone(block.block_type)}`, borderRadius: 14, padding: 14 }}>
      <strong>{block.block_type.toUpperCase()} • {t(block.starts_at)}–{t(block.ends_at)}</strong>
      <div style={{ marginTop: 10, border: block.dependency?.can_start ? "1px solid #14532d" : "1px solid #7f1d1d", borderRadius: 12, padding: 10 }}><strong>{block.dependency?.can_start ? "CAN START" : "CANNOT START"}</strong><div style={{ color: "#94a3b8", marginTop: 4 }}>Risk {block.dependency?.risk || "-"} • {block.dependency?.cannot_start_reason || "No blocking dependency reason"}</div></div>
      <CheckGrid checks={block.dependency?.checks} />
      <div style={{ color: "#94a3b8", marginTop: 10 }}>Room {block.room.name || "-"} • state {block.room.state || "-"}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>Episode {block.episode?.episode_ref || "-"} • patient {block.episode?.patient?.name || "-"} • owner {block.episode?.patient?.owner_name || "-"}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>Procedure {block.procedure?.name || "-"} • family {block.operating?.template?.family || "-"} • anaesthesia {block.operating?.template?.anaesthesia_level || "-"} • recovery {block.operating?.template?.recovery_class || "-"} • cleaning {block.operating?.template?.cleaning_standard || "-"}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>Required roles: {(block.operating?.required_roles || []).join(" • ") || "-"}</div><div style={{ color: "#94a3b8", marginTop: 6 }}>Assigned: {block.assigned_staff?.name || "not assigned"} • owner role {block.owner_role || "unowned"}</div>
      {block.next_action ? <div style={{ marginTop: 10, border: "1px solid #78350f", borderRadius: 12, padding: 10 }}><strong>Next action</strong><div style={{ color: "#cbd5e1", marginTop: 4 }}>{block.next_action.section || block.next_action.type} • {block.next_action.detail} • owner {block.next_action.owner_role}</div></div> : null}
      {block.dependency?.hard_failures?.length ? <div style={{ marginTop: 10 }}><strong>Dependency hard failures</strong>{block.dependency.hard_failures.map((x, i) => <div key={i} style={{ color: "#fca5a5", marginTop: 4 }}>{x.type}: {x.detail} • owner {x.owner_role}</div>)}</div> : null}
      {block.dependency?.warnings?.length ? <div style={{ marginTop: 10 }}><strong>Dependency warnings</strong>{block.dependency.warnings.map((x, i) => <div key={i} style={{ color: "#fbbf24", marginTop: 4 }}>{x.type}: {x.detail} • owner {x.owner_role}</div>)}</div> : null}
      {block.operating?.readiness_gates?.length ? <div style={{ marginTop: 10 }}><strong>Readiness gates</strong><div style={{ color: "#94a3b8", marginTop: 4 }}>{block.operating.readiness_gates.slice(0, 14).join(" • ")}</div></div> : null}
      {block.pressure?.hard_blocks?.length ? <div style={{ marginTop: 10 }}><strong>All hard blockers</strong>{block.pressure.hard_blocks.map((x, i) => <div key={i} style={{ color: "#fca5a5", marginTop: 4 }}>{x.section || x.type}: {x.detail} • owner {x.owner_role}</div>)}</div> : null}
      <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>{block.episode?.episode_ref ? <Link href={`/episodes/${block.episode.episode_ref}`} className="lw-pill">Open episode</Link> : null}<Link href="/schedule" className="lw-pill">Schedule</Link><Link href="/queues" className="lw-pill">Queues</Link></div>
    </article>)}</div>}</section>
  </div></HospitalShell>}</AuthGuard>;
}
