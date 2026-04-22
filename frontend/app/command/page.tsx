import Link from "next/link";
import { apiGet } from "@/lib/api";

type Pulse = {
  total_work_items: number;
  red_items: number;
  new_items: number;
  in_progress_items: number;
  unowned_items: number;
};

type WorkItem = {
  id: number;
  title: string;
  urgency: string;
  owner_role: string;
  status: string;
  linked_patient_name?: string;
  linked_episode_ref?: string;
};

export default async function CommandPage() {
  const pulse = await apiGet<Pulse>("/api/pulse");
  const items = await apiGet<WorkItem[]>("/api/work-items");

  return (
    <main style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 36 }}>Lucy Pulse / Command</h1>
          <p style={{ color: "#94a3b8" }}>Live operational view from real backend data.</p>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <Link href="/input">New input</Link>
          <Link href="/audit">Audit</Link>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginTop: 20 }}>
        {Object.entries(pulse).map(([key, value]) => (
          <div key={key} style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}>
            <div style={{ color: "#94a3b8", fontSize: 14 }}>{key.replaceAll("_", " ")}</div>
            <div style={{ fontSize: 32, marginTop: 8 }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 24, border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
        <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Work queue</div>
        <div>
          {items.map((item) => (
            <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <strong>{item.title}</strong>
                <span>{item.urgency.toUpperCase()} / {item.status}</span>
              </div>
              <div style={{ color: "#94a3b8", marginTop: 6 }}>
                owner role: {item.owner_role} {item.linked_patient_name ? `• patient: ${item.linked_patient_name}` : ""} {item.linked_episode_ref ? `• episode: ${item.linked_episode_ref}` : ""}
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
