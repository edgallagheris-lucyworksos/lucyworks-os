"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Admission = { id: number; episode_id: number; admitted_to: string; admitted_at: string; status: string };
type Episode = { id: number; episode_ref: string; patient_id: number; current_section_name?: string | null; current_room_name?: string | null; current_phase: string; status: string };
type Patient = { id: number; patient_name: string; species: string; owner_name: string; owner_phone?: string | null };

function when(value: string) {
  return new Date(value).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function AdmissionsPage() {
  const [admissions, setAdmissions] = useState<Admission[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);

  useEffect(() => {
    async function load() {
      const [a, e, p] = await Promise.all([
        fetch(`${API_BASE}/api/admissions`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/episodes`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/patients`, { cache: "no-store" }),
      ]);
      setAdmissions(await a.json());
      setEpisodes(await e.json());
      setPatients(await p.json());
    }
    load();
  }, []);

  const episodeById = useMemo(() => new Map(episodes.map((x) => [x.id, x])), [episodes]);
  const patientById = useMemo(() => new Map(patients.map((x) => [x.id, x])), [patients]);
  const active = admissions.filter((x) => x.status !== "closed");
  const wardCount = active.filter((x) => x.admitted_to === "ICU" || x.admitted_to === "Wards").length;

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Admissions" subtitle="Admitted patient flow and inpatient ownership">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Active admissions</div><div style={{ fontSize: 34 }}>{active.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>ICU / Wards</div><div style={{ fontSize: 34 }}>{wardCount}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Total records</div><div style={{ fontSize: 34 }}>{admissions.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Admissions list</div>
            {admissions.map((admission) => {
              const episode = episodeById.get(admission.episode_id);
              const patient = episode ? patientById.get(episode.patient_id) : undefined;
              return (
                <div key={admission.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <strong>{patient ? `${patient.patient_name} (${patient.species})` : "Unknown patient"}</strong>
                    <span>{admission.status} • {when(admission.admitted_at)}</span>
                  </div>
                  <div style={{ color: "#94a3b8", marginTop: 6 }}>
                    admitted to {admission.admitted_to} • owner {patient?.owner_name || "-"} • current {episode?.current_section_name || "-"} / {episode?.current_room_name || "-"} • phase {episode?.current_phase || "-"}
                  </div>
                  {episode ? <div style={{ marginTop: 8 }}><Link href={`/episodes/${episode.episode_ref}`}>Open episode {episode.episode_ref}</Link></div> : null}
                </div>
              );
            })}
            {!admissions.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No admissions returned.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
