"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type DirectorCard = {
  key: string;
  label: string;
  value: number;
  tone: string;
};

type SectionPressure = {
  section_name: string;
  live: number;
  red: number;
  unowned: number;
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
  linked_patient_name?: string | null;
  linked_episode_ref?: string | null;
};

type DirectorBoard = {
  cards: DirectorCard[];
  section_pressure: SectionPressure[];
  priority_items: WorkItem[];
};

function toneBorder(tone: string): string {
  if (tone === "critical") return "1px solid #7f1d1d";
  if (tone === "warning") return "1px solid #78350f";
  if (tone === "stable") return "1px solid #14532d";
  if (tone === "info") return "1px solid #1e3a8a";
  return "1px solid #1f2937";
}

function CommandInner() {
  const [board, setBoard] = useState<DirectorBoard | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/director-board`, { cache: "no-store" });
      setBoard(await res.json());
    }
    load();
  }, []);

  return (
    <HospitalShell title="Clinical Director / Command" subtitle="Whole-hospital visibility and priority work">
      {!board ? <p>Loading command board...</p> : null}

      {board ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
            {board.cards.map((card) => (
              <div key={card.key} style={{ border: toneBorder(card.tone), borderRadius: 18, padding: 16, background: "#0f172a" }}>
                <div style={{ color: "#94a3b8", fontSize: 14 }}>{card.label}</div>
                <div style={{ fontSize: 34, marginTop: 8 }}>{card.value}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16, marginTop: 24 }}>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
              <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Priority board</div>
              <div>
                {board.priority_items.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{item.title}</strong>
                      <span>{item.urgency.toUpperCase()} / {item.status}</span>
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>
                      {item.section_name ? `section: ${item.section_name} • ` : ""}
                      {item.room_name ? `room: ${item.room_name} • ` : ""}
                      {item.patient_location_label ? `location: ${item.patient_location_label} • ` : ""}
                      {item.linked_patient_name ? `patient: ${item.linked_patient_name} • ` : ""}
                      {item.linked_episode_ref ? `episode: ${item.linked_episode_ref}` : ""}
                    </div>
                    {item.linked_episode_ref ? (
                      <div style={{ marginTop: 8 }}>
                        <Link href={`/episodes/${item.linked_episode_ref}`}>Open episode</Link>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>

            <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
              <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Section pressure</div>
              <div>
                {board.section_pressure.map((section) => (
                  <div key={section.section_name} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{section.section_name}</strong>
                      <span>live {section.live}</span>
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>
                      red {section.red} • unowned {section.unowned}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      ) : null}
    </HospitalShell>
  );
}

export default function CommandPage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinician"]}>{() => <CommandInner />}</AuthGuard>;
}
