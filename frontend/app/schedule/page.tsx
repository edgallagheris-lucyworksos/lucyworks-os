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

type Episode = { id: number; episode_ref: string };
type ProcedureTemplate = { name: string; department: string; prep_min: number; anaesthesia_min: number; procedure_min: number; recovery_min: number; cleaning_min: number; risk: string };
type Department = { name: string; short_name: string; rooms: string[] };
type Catalogue = { departments: Department[]; procedure_templates: ProcedureTemplate[] };

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

function totalMinutes(p?: ProcedureTemplate) {
  if (!p) return 0;
  return p.prep_min + p.anaesthesia_min + p.procedure_min + p.recovery_min + p.cleaning_min;
}

function defaultStart() {
  const d = new Date();
  d.setMinutes(0, 0, 0);
  d.setHours(d.getHours() + 1);
  return d.toISOString().slice(0, 16);
}

export default function SchedulePage() {
  const [blocks, setBlocks] = useState<ScheduleBlock[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [episodeRef, setEpisodeRef] = useState("EP-1042");
  const [procedureName, setProcedureName] = useState("CT scan");
  const [roomName, setRoomName] = useState("CT");
  const [startTime, setStartTime] = useState(defaultStart());
  const [status, setStatus] = useState("");

  async function load() {
    const [blockRes, episodeRes, catalogueRes] = await Promise.all([
      fetch(`${API_BASE}/api/schedule-blocks`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/episodes`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/operating-catalogue`, { cache: "no-store" }),
    ]);
    const episodeData = await episodeRes.json();
    const catalogueData = await catalogueRes.json();
    setBlocks(await blockRes.json());
    setEpisodes(episodeData);
    setCatalogue(catalogueData);
    if (episodeData[0] && !episodeRef) setEpisodeRef(episodeData[0].episode_ref);
  }

  useEffect(() => { load(); }, []);

  const selectedProcedure = useMemo(() => catalogue?.procedure_templates.find((p) => p.name === procedureName), [catalogue, procedureName]);
  const roomsForProcedure = useMemo(() => {
    if (!catalogue || !selectedProcedure) return [];
    const dept = catalogue.departments.find((d) => d.name === selectedProcedure.department || d.short_name === selectedProcedure.department);
    return dept?.rooms || [];
  }, [catalogue, selectedProcedure]);
  const episodeById = useMemo(() => { const map: Record<number, Episode> = {}; for (const episode of episodes) map[episode.id] = episode; return map; }, [episodes]);
  const rooms = useMemo(() => Array.from(new Set(blocks.map((b) => b.room_name || "Unassigned"))).sort(), [blocks]);
  const grouped = useMemo(() => {
    const map: Record<string, ScheduleBlock[]> = {};
    for (const block of blocks) {
      const room = block.room_name || "Unassigned";
      map[room] = map[room] || [];
      map[room].push(block);
    }
    for (const room of Object.keys(map)) map[room].sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
    return map;
  }, [blocks]);

  async function generateFromTemplate() {
    if (!episodeRef || !procedureName || !startTime) return;
    setStatus("Generating schedule from operating catalogue...");
    const res = await fetch(`${API_BASE}/api/operating-catalogue/schedule-from-template`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_ref: episodeRef, procedure_name: procedureName, room_name: roomName || "Unassigned", start_time: new Date(startTime).toISOString(), actor_name: "Schedule UI" }),
    });
    const body = await res.json();
    if (!res.ok) {
      setStatus(`Could not generate schedule: ${body.detail || res.statusText}`);
      return;
    }
    setStatus(`Generated ${body.template.name}: ${body.total_minutes} minutes across ${body.blocks.length} blocks.`);
    await load();
  }

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse"]}>{() => (
      <HospitalShell title="Schedule" subtitle="Catalogue-driven procedure timeline">
        {status ? <section className="lw-card" style={{ padding: 12, marginBottom: 16 }}>{status}</section> : null}

        <section className="lw-card" style={{ padding: 18, marginBottom: 16 }}>
          <div style={{ color: "#14b8a6", fontWeight: 900, letterSpacing: "0.08em", textTransform: "uppercase" }}>No-typing schedule builder</div>
          <h2 style={{ margin: "8px 0" }}>Generate procedure blocks from the operating catalogue</h2>
          <p style={{ color: "#94a3b8" }}>Pick the case, procedure template, room and start time. LucyWorks creates prep, anaesthesia, procedure, recovery and cleaning blocks, updates the episode, and audits the action.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
            <label>Episode<br /><select value={episodeRef} onChange={(e) => setEpisodeRef(e.target.value)} style={{ width: "100%", borderRadius: 12, padding: 10 }}>{episodes.map((e) => <option key={e.id} value={e.episode_ref}>{e.episode_ref}</option>)}</select></label>
            <label>Procedure<br /><select value={procedureName} onChange={(e) => { setProcedureName(e.target.value); const proc = catalogue?.procedure_templates.find((p) => p.name === e.target.value); const dept = catalogue?.departments.find((d) => d.name === proc?.department || d.short_name === proc?.department); if (dept?.rooms[0]) setRoomName(dept.rooms[0]); }} style={{ width: "100%", borderRadius: 12, padding: 10 }}>{catalogue?.procedure_templates.map((p) => <option key={p.name} value={p.name}>{p.name} • {p.department}</option>)}</select></label>
            <label>Room<br /><select value={roomName} onChange={(e) => setRoomName(e.target.value)} style={{ width: "100%", borderRadius: 12, padding: 10 }}>{roomsForProcedure.length ? roomsForProcedure.map((r) => <option key={r} value={r}>{r}</option>) : <option value={roomName}>{roomName || "Unassigned"}</option>}</select></label>
            <label>Start time<br /><input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} style={{ width: "100%", borderRadius: 12, padding: 10 }} /></label>
          </div>
          {selectedProcedure ? <div style={{ marginTop: 12, color: "#94a3b8" }}>Timing: prep {selectedProcedure.prep_min} • anaesthesia {selectedProcedure.anaesthesia_min} • procedure {selectedProcedure.procedure_min} • recovery {selectedProcedure.recovery_min} • cleaning {selectedProcedure.cleaning_min} = {totalMinutes(selectedProcedure)} min. Guardrail: {selectedProcedure.risk}</div> : null}
          <button onClick={generateFromTemplate} className="lw-btn-primary" style={{ marginTop: 14, borderRadius: 14, padding: "12px 14px" }}>Generate schedule</button>
        </section>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <div style={{ color: "#94a3b8" }}>Prep → Anaesthesia → Procedure → Recovery → Cleaning</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{["prep", "anaesthesia", "procedure", "recovery", "cleaning"].map((item) => <span key={item} style={{ border: `1px solid ${colour(item)}`, borderRadius: 999, padding: "6px 10px" }}>{item}</span>)}</div>
        </div>

        <div style={{ display: "grid", gap: 16 }}>
          {rooms.map((room) => (
            <section key={room} className="lw-card" style={{ overflow: "hidden" }}>
              <div style={{ padding: 14, borderBottom: "1px solid #1f2937", display: "flex", justifyContent: "space-between" }}><strong>{room}</strong><span style={{ color: "#94a3b8" }}>{grouped[room]?.length || 0} blocks</span></div>
              <div style={{ padding: 14, display: "grid", gap: 10 }}>
                {(grouped[room] || []).map((block) => { const episode = episodeById[block.episode_id]; return <div key={block.id} style={{ border: `1px solid ${colour(block.block_type)}`, borderRadius: 14, padding: 12, display: "grid", gridTemplateColumns: "130px 1fr 140px", gap: 12, alignItems: "center" }}><strong>{timeLabel(block.starts_at)} → {timeLabel(block.ends_at)}</strong><div><div style={{ fontWeight: 700 }}>{block.block_type.toUpperCase()}</div><div style={{ color: "#94a3b8" }}>episode {episode?.episode_ref || `#${block.episode_id}`} • owner {block.owner_role || "unassigned"}</div></div><Link href={episode ? `/episodes/${episode.episode_ref}` : "/episodes"} style={{ textAlign: "right" }}>Open episode</Link></div>; })}
                {!grouped[room]?.length ? <div style={{ color: "#94a3b8" }}>No schedule blocks.</div> : null}
              </div>
            </section>
          ))}
          {!rooms.length ? <div className="lw-card" style={{ padding: 16 }}>No schedule blocks yet. Use the builder above to generate the chain from the operating catalogue.</div> : null}
        </div>
      </HospitalShell>
    )}</AuthGuard>
  );
}
