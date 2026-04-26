"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type EpisodeCommand = {
  episode: any;
  patient: any;
  admissions: any[];
  handovers: any[];
  results: any[];
  schedule_blocks: any[];
  message_threads: any[];
  work_items: any[];
  room_state?: any | null;
  conflicts: any[];
};

type StaffLoad = {
  staff_member_id: number;
  name: string;
  role: string;
  skills: string;
  on_shift: boolean;
  active_blocks: number;
  assigned_block_ids: number[];
};

function time(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function EpisodeDetailPage() {
  const params = useParams<{ episodeRef: string }>();
  const episodeRef = params.episodeRef;
  const [data, setData] = useState<EpisodeCommand | null>(null);
  const [staffLoad, setStaffLoad] = useState<StaffLoad[]>([]);
  const [status, setStatus] = useState("");

  async function load() {
    const [episodeRes, staffRes] = await Promise.all([
      fetch(`${API_BASE}/api/episode-command/${episodeRef}`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/staff-load`, { cache: "no-store" }),
    ]);
    setData(await episodeRes.json());
    setStaffLoad(await staffRes.json());
  }

  useEffect(() => {
    load();
  }, [episodeRef]);

  const staffById = useMemo(() => {
    const map: Record<number, StaffLoad> = {};
    for (const s of staffLoad) map[s.staff_member_id] = s;
    return map;
  }, [staffLoad]);

  async function shiftBlock(blockId: number, minutes: number) {
    setStatus(`Shifting block chain ${minutes} minutes...`);
    await fetch(`${API_BASE}/api/schedule/block/${blockId}/shift`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutes, actor_name: "Episode Command" }),
    });
    setStatus("Schedule updated.");
    await load();
  }

  async function allocateStaff(blockId: number, staffId: string) {
    if (!staffId) return;
    setStatus("Assigning staff...");
    const res = await fetch(`${API_BASE}/api/staff/allocate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schedule_block_id: blockId, staff_member_id: Number(staffId), actor_name: "Episode Command" }),
    });
    const body = await res.json();
    setStatus(body.status === "conflict" ? `Staff conflict: ${body.detail}` : `Assigned ${body.staff}.`);
    await load();
  }

  async function convertConflict(conflict: any) {
    setStatus("Creating work from conflict...");
    await fetch(`${API_BASE}/api/conflicts/to-work?conflict_type=${encodeURIComponent(conflict.type)}&severity=${encodeURIComponent(conflict.severity)}&detail=${encodeURIComponent(conflict.detail)}`, { method: "POST" });
    setStatus("Conflict converted to work.");
    await load();
  }

  async function markResultReviewed(resultId: number) {
    setStatus("Marking result reviewed...");
    await fetch(`${API_BASE}/api/results/${resultId}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "reviewed", actor_name: "Episode Command", required_action: "Reviewed from episode command" }),
    });
    setStatus("Result reviewed.");
    await load();
  }

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Episode Command" subtitle={episodeRef}>
          {status ? <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, marginBottom: 16, background: "#0f172a" }}>{status}</div> : null}
          {!data ? <p>Loading episode command...</p> : null}
          {data ? (
            <div style={{ display: "grid", gap: 16 }}>
              <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <h2 style={{ marginTop: 0 }}>Case control</h2>
                <div style={{ color: "#f8fafc", fontSize: 20 }}>{data.patient?.patient_name} • {data.patient?.species}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>Owner {data.patient?.owner_name} • {data.patient?.owner_phone || "no phone"}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>Phase {data.episode.current_phase} • status {data.episode.status} • {data.episode.current_section_name || "-"} / {data.episode.current_room_name || "-"}</div>
              </section>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                <div style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Conflicts</div><div style={{ fontSize: 32 }}>{data.conflicts.length}</div></div>
                <div style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Schedule blocks</div><div style={{ fontSize: 32 }}>{data.schedule_blocks.length}</div></div>
                <div style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Results</div><div style={{ fontSize: 32 }}>{data.results.length}</div></div>
                <div style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Messages</div><div style={{ fontSize: 32 }}>{data.message_threads.length}</div></div>
              </div>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <h3 style={{ marginTop: 0 }}>Staff load</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                  {staffLoad.map((s) => (
                    <div key={s.staff_member_id} style={{ border: "1px solid #334155", borderRadius: 12, padding: 12 }}>
                      <strong>{s.name}</strong>
                      <div style={{ color: "#94a3b8", marginTop: 4 }}>{s.role} • {s.on_shift ? "on shift" : "off shift"} • {s.active_blocks} blocks</div>
                    </div>
                  ))}
                </div>
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <h3 style={{ marginTop: 0 }}>Room state</h3>
                <div style={{ color: "#94a3b8" }}>{data.room_state ? `${data.room_state.room_name} • ${data.room_state.state} • next ${data.room_state.next_episode_ref || "-"}` : "No room state found"}</div>
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Timeline controls</div>
                {data.schedule_blocks.map((block) => {
                  const assigned = block.assigned_staff_member_id ? staffById[block.assigned_staff_member_id] : null;
                  return (
                    <div key={block.id} style={{ padding: 16, borderTop: "1px solid #1f2937", display: "grid", gap: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                        <strong>{time(block.starts_at)} → {time(block.ends_at)} • {block.block_type}</strong>
                        <span>{block.room_name || "unassigned"} • {assigned ? `assigned ${assigned.name}` : block.owner_role || "no owner"}</span>
                      </div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button onClick={() => shiftBlock(block.id, -15)} style={{ padding: "8px 10px", borderRadius: 10 }}>-15 min</button>
                        <button onClick={() => shiftBlock(block.id, 15)} style={{ padding: "8px 10px", borderRadius: 10 }}>+15 min</button>
                        <select onChange={(e) => allocateStaff(block.id, e.target.value)} defaultValue="" style={{ padding: "8px 10px", borderRadius: 10 }}>
                          <option value="">Assign staff</option>
                          {staffLoad.map((s) => <option key={s.staff_member_id} value={s.staff_member_id}>{s.name} • {s.role} • {s.active_blocks} active</option>)}
                        </select>
                      </div>
                    </div>
                  );
                })}
                {!data.schedule_blocks.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No schedule blocks linked yet.</div> : null}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Conflicts affecting this episode</div>
                {data.conflicts.map((conflict, index) => (
                  <div key={`${conflict.type}-${index}`} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <strong>{conflict.type}</strong>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{conflict.severity} • {conflict.detail}</div>
                    <button onClick={() => convertConflict(conflict)} style={{ marginTop: 10, padding: "8px 10px", borderRadius: 10, background: "#14b8a6", color: "#020617", border: 0 }}>Convert to work</button>
                  </div>
                ))}
                {!data.conflicts.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No conflicts linked to this episode.</div> : null}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Results</div>
                {data.results.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <strong>{item.result_type}</strong>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.status} • owner {item.review_owner} • action {item.required_action || "-"}</div>
                    {item.status !== "reviewed" ? <button onClick={() => markResultReviewed(item.id)} style={{ marginTop: 10, padding: "8px 10px", borderRadius: 10 }}>Mark reviewed</button> : null}
                  </div>
                ))}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Messages</div>
                {data.message_threads.map((thread) => (
                  <div key={thread.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <strong>{thread.subject}</strong>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{thread.source_type} • {thread.status} • {thread.owner_role}</div>
                  </div>
                ))}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Work</div>
                {data.work_items.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <strong>{item.title}</strong>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.urgency} • {item.status} • owner {item.owner_role}</div>
                  </div>
                ))}
              </section>
            </div>
          ) : null}
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
