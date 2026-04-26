"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

type Card = {
  key: string;
  label: string;
  value: number;
  tone: string;
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

type RoomGroup = {
  room_name: string;
  section_name?: string | null;
  live: number;
  red: number;
  items: WorkItem[];
};

type TheatreBoard = {
  cards: Card[];
  room_groups: RoomGroup[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function toneBorder(tone: string): string {
  if (tone === "critical") return "1px solid #7f1d1d";
  if (tone === "warning") return "1px solid #78350f";
  if (tone === "stable") return "1px solid #14532d";
  if (tone === "info") return "1px solid #1e3a8a";
  return "1px solid #1f2937";
}

function TheatreInner() {
  const [board, setBoard] = useState<TheatreBoard | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/theatre-board`, { cache: "no-store" });
      setBoard(await res.json());
    }
    load();
  }, []);

  return (
    <HospitalShell title="Theatre / Recovery Board" subtitle="Live theatre pressure, prep blockers, and recovery handoffs">
      {!board ? <p>Loading theatre board...</p> : null}

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

          <div style={{ display: "grid", gap: 16, marginTop: 24 }}>
            {board.room_groups.map((group) => (
              <section key={group.room_name} style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
                <div style={{ padding: 16, background: "#0f172a", display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <strong>{group.section_name} / {group.room_name}</strong>
                  <span>live {group.live} • red {group.red}</span>
                </div>
                {group.items.map((item) => (
                  <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <strong>{item.title}</strong>
                      <span>{item.urgency.toUpperCase()} / {item.status}</span>
                    </div>
                    <div style={{ color: "#94a3b8", marginTop: 6 }}>
                      {item.patient_location_label ? `location: ${item.patient_location_label} • ` : ""}
                      {item.linked_patient_name ? `patient: ${item.linked_patient_name} • ` : ""}
                      {item.linked_episode_ref ? `episode: ${item.linked_episode_ref} • ` : ""}
                      owner role: {item.owner_role}
                    </div>
                    {item.linked_episode_ref ? (
                      <div style={{ marginTop: 8 }}>
                        <Link href={`/episodes/${item.linked_episode_ref}`}>Open episode</Link>
                      </div>
                    ) : null}
                  </div>
                ))}
              </section>
            ))}
          </div>
        </>
      ) : null}
    </HospitalShell>
  );
}

export default function TheatrePage() {
  return <AuthGuard allowedRoles={["ops_manager", "clinician", "nurse"]}>{() => <TheatreInner />}</AuthGuard>;
}
