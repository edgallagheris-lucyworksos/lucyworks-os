import { apiGet } from "@/lib/api";

type AuditEvent = {
  id: number;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: number;
  summary: string;
  created_at: string;
};

export default async function AuditPage() {
  const events = await apiGet<AuditEvent[]>("/api/audit");

  return (
    <main style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ fontSize: 36, marginTop: 0 }}>Audit</h1>
      <p style={{ color: "#94a3b8" }}>Every material action recorded from the backend.</p>
      <div style={{ marginTop: 20, border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
        {events.map((event) => (
          <div key={event.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <strong>{event.summary}</strong>
              <span>{new Date(event.created_at).toLocaleString()}</span>
            </div>
            <div style={{ color: "#94a3b8", marginTop: 6 }}>
              {event.actor_name} • {event.action} • {event.entity_type} #{event.entity_id}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
