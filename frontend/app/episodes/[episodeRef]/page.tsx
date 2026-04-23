"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Episode = {
  id: number;
  episode_ref: string;
  patient_id: number;
  status: string;
  current_section_name?: string | null;
  current_room_name?: string | null;
  current_phase: string;
};

type Patient = {
  id: number;
  patient_name: string;
  species: string;
  owner_name: string;
  owner_phone?: string | null;
  weight_kg?: number | null;
};

type Admission = {
  id: number;
  episode_id: number;
  admitted_to: string;
  admitted_at: string;
  status: string;
};

type Handover = {
  id: number;
  episode_id: number;
  from_owner: string;
  to_owner: string;
  note: string;
  acknowledged: boolean;
};

type ResultReview = {
  id: number;
  episode_id: number;
  result_type: string;
  review_owner: string;
  status: string;
};

type RoomState = {
  id: number;
  room_name: string;
  room_type: string;
  department: string;
  state: string;
  current_episode_ref?: string | null;
  next_episode_ref?: string | null;
  cleaning_due_minutes?: number | null;
};

type WorkItem = {
  id: number;
  title: string;
  urgency: string;
  owner_role: string;
  status: string;
  section_name?: string | null;
  room_name?: string | null;
  patient_location_label?: string | null;
  linked_episode_ref?: string | null;
};

export default function EpisodeDetailPage() {
  const params = useParams<{ episodeRef: string }>();
  const episodeRef = params.episodeRef;

  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [admissions, setAdmissions] = useState<Admission[]>([]);
  const [handovers, setHandovers] = useState<Handover[]>([]);
  const [results, setResults] = useState<ResultReview[]>([]);
  const [roomStates, setRoomStates] = useState<RoomState[]>([]);
  const [workItems, setWorkItems] = useState<WorkItem[]>([]);

  useEffect(() => {
    async function load() {
      const [episodesRes, patientsRes, admissionsRes, handoversRes, resultsRes, roomStatesRes, workItemsRes] = await Promise.all([
        fetch(`${API_BASE}/api/episodes`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/patients`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/admissions`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/handovers`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/results`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/room-states`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/work-items`, { cache: "no-store" }),
      ]);
      setEpisodes(await episodesRes.json());
      setPatients(await patientsRes.json());
      setAdmissions(await admissionsRes.json());
      setHandovers(await handoversRes.json());
      setResults(await resultsRes.json());
      setRoomStates(await roomStatesRes.json());
      setWorkItems(await workItemsRes.json());
    }
    load();
  }, []);

  const episode = useMemo(() => episodes.find((item) => item.episode_ref === episodeRef), [episodes, episodeRef]);
  const patient = useMemo(() => patients.find((item) => item.id === episode?.patient_id), [patients, episode]);
  const episodeAdmissions = admissions.filter((item) => item.episode_id === episode?.id);
  const episodeHandovers = handovers.filter((item) => item.episode_id === episode?.id);
  const episodeResults = results.filter((item) => item.episode_id === episode?.id);
  const episodeWorkItems = workItems.filter((item) => item.linked_episode_ref === episodeRef);
  const episodeRoomState = roomStates.find((item) => item.current_episode_ref === episodeRef || item.next_episode_ref === episodeRef);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Episode detail" subtitle={episodeRef}>
          {!episode ? <p>Loading episode...</p> : null}
          {episode ? (
            <div style={{ display: "grid", gap: 16 }}>
              <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <h2 style={{ marginTop: 0 }}>Case truth</h2>
                <div style={{ color: "#94a3b8" }}>
                  {patient ? `${patient.patient_name} (${patient.species}) • owner ${patient.owner_name} • ${patient.owner_phone || "no phone"}` : "patient loading"}
                </div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>
                  phase {episode.current_phase} • status {episode.status} • section {episode.current_section_name || "-"} • room {episode.current_room_name || "-"}
                </div>
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <h3 style={{ marginTop: 0 }}>Room state</h3>
                <div style={{ color: "#94a3b8" }}>
                  {episodeRoomState ? `${episodeRoomState.room_name} • ${episodeRoomState.state} • next ${episodeRoomState.next_episode_ref || "-"} • cleaning due ${episodeRoomState.cleaning_due_minutes ?? "-"}` : "No room state found"}
                </div>
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Admissions</div>
                {episodeAdmissions.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div>{item.admitted_to}</div>
                    <div style={{ color: "#94a3b8" }}>{item.status} • {new Date(item.admitted_at).toLocaleString()}</div>
                  </div>
                ))}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Handovers</div>
                {episodeHandovers.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div>{item.from_owner} → {item.to_owner}</div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.note}</div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>acknowledged {String(item.acknowledged)}</div>
                  </div>
                ))}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Results</div>
                {episodeResults.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div>{item.result_type}</div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.status} • review owner {item.review_owner}</div>
                  </div>
                ))}
              </section>

              <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Work items</div>
                {episodeWorkItems.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{item.title}</strong>
                      <span>{item.urgency.toUpperCase()} / {item.status}</span>
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>
                      {item.section_name || "-"} • {item.room_name || "-"} • {item.patient_location_label || "-"} • owner {item.owner_role}
                    </div>
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
