"use client";

import { useEffect, useState } from "react";
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

function time(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function EpisodeDetailPage() {
  const params = useParams<{ episodeRef: string }>();
  const episodeRef = params.episodeRef;
  const [data, setData] = useState<EpisodeCommand | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/episode-command/${episodeRef}`, { cache: "no-store" });
      setData(await res.json());
    }
    load();
  }, [episodeRef]);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Episode Command" subtitle={episodeRef}>
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
                <h3 style={{ marginTop: 0 }}>Room state</h3>
                <div style={{ color: "#94a3b8" }}>{data.room_state ? `${data.room_state.room_name} • ${data.room_state.state} • next ${data.room_state.next_episode_ref || "-"}` : "No room state found"}</div>
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Timeline</div>
                {data.schedule_blocks.map((block) => (
                  <div key={block.id} style={{ padding: 16, borderTop: "1px solid #1f2937", display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{time(block.starts_at)} → {time(block.ends_at)} • {block.block_type}</strong>
                    <span>{block.room_name || "unassigned"} • {block.owner_role || "no owner"}</span>
                  </div>
                ))}
                {!data.schedule_blocks.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No schedule blocks linked yet.</div> : null}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Conflicts affecting this episode</div>
                {data.conflicts.map((conflict, index) => (
                  <div key={`${conflict.type}-${index}`} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <strong>{conflict.type}</strong>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{conflict.severity} • {conflict.detail}</div>
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
