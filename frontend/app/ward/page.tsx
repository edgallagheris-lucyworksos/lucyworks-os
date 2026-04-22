import Link from "next/link";
import { apiGet } from "@/lib/api";

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

type WardBoard = {
  cards: Card[];
  room_groups: RoomGroup[];
};

function toneBorder(tone: string): string {
  if (tone === "critical") return "1px solid #7f1d1d";
  if (tone === "warning") return "1px solid #78350f";
  if (tone === "stable") return "1px solid #14532d";
  if (tone === "info") return "1px solid #1e3a8a";
  return "1px solid #1f2937";
}

export default async function WardPage() {
  const board = await apiGet<WardBoard>("/api/ward-board");

  return (
    <main style={{ padding: 24, maxWidth: 1280, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 36 }}>Ward / ICU Board</h1>
          <p style={{ color: "#94a3b8" }}>Inpatient pressure, bays, rooms, and blockers.</p>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link href="/command">Command</Link>
          <Link href="/queues">Queues</Link>
          <Link href="/audit">Audit</Link>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12, marginTop: 20 }}>
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
              </div>
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}
