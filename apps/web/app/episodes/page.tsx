"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
};

export default function EpisodesPage() {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);

  useEffect(() => {
    async function load() {
      const [episodeRes, patientRes] = await Promise.all([
        fetch(`${API_BASE}/api/episodes`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/patients`, { cache: "no-store" }),
      ]);
      setEpisodes(await episodeRes.json());
      setPatients(await patientRes.json());
    }
    load();
  }, []);

  const patientById = new Map(patients.map((patient) => [patient.id, patient]));

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Episodes" subtitle="Patient and visit truth list">
          <div style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            {episodes.map((episode) => {
              const patient = patientById.get(episode.patient_id);
              return (
                <Link key={episode.id} href={`/episodes/${episode.episode_ref}`} style={{ display: "block", padding: 16, borderTop: "1px solid #1f2937" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{episode.episode_ref}</strong>
                    <span>{episode.status} / {episode.current_phase}</span>
                  </div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>
                    {patient ? `${patient.patient_name} (${patient.species}) • owner ${patient.owner_name} • ` : ""}
                    {episode.current_section_name || "-"} • {episode.current_room_name || "-"}
                  </div>
                </Link>
              );
            })}
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
