"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type RealtimeStatus = {
  generated_at?: string;
  stream?: string;
  published_buffer_count?: number;
  snapshot_event_count?: number;
  event_types?: string[];
};

export default function RealtimeStatusPage() {
  const [status, setStatus] = useState<RealtimeStatus>({});
  const [generated, setGenerated] = useState<any[]>([]);
  const [published, setPublished] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [statusRes, eventsRes] = await Promise.all([
        fetch(`${API_BASE}/api/realtime/status`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/realtime/events`, { cache: "no-store" }),
      ]);
      const statusData = await statusRes.json().catch(() => ({}));
      const eventsData = await eventsRes.json().catch(() => ({}));
      if (!statusRes.ok) throw new Error(JSON.stringify(statusData));
      if (!eventsRes.ok) throw new Error(JSON.stringify(eventsData));
      setStatus(statusData);
      setGenerated(eventsData.generated || []);
      setPublished(eventsData.published || []);
    } catch {
      setError("Realtime API unavailable. Backend or API base needs checking.");
      setStatus({ stream: "unavailable", published_buffer_count: 0, snapshot_event_count: 0, event_types: [] });
      setGenerated([]);
      setPublished([]);
    } finally {
      setLoading(false);
    }
  }

  async function publishTestEvent() {
    await fetch(`${API_BASE}/api/realtime/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: "manual_update",
        title: "UI live event",
        detail: "Published from the realtime status screen",
        severity: "info",
        source: "realtime_status_ui",
        entity_type: "system",
        entity_id: 0,
        actor_name: "LucyWorks UI",
      }),
    });
    await load();
  }

  useEffect(() => { load(); }, []);

  const allEvents = [...generated, ...published].slice(0, 40);

  return (
    <AuthGuard allowedRoles={["ops_manager", "clinical_director", "clinician", "nurse", "admin", "pca"]}>
      {() => (
        <HospitalShell title="Realtime" subtitle="live event stream and operational update status">
          <div className="lw-neo-page">
            <section className="lw-hero-panel">
              <div className="lw-hero-content">
                <span className="lw-eyebrow">LucyWorks / realtime layer</span>
                <h1>Realtime Status</h1>
                <p>Live event snapshot for Pulse, conflicts, work queues, scheduler changes, audit events and manual updates.</p>
                {error ? <div className="lw-banner warn">{error}</div> : null}
              </div>
              <div className="lw-hero-actions">
                <button className="lw-glow-button" onClick={load}>{loading ? "Refreshing" : "Refresh"}</button>
                <button className="lw-glow-button" onClick={publishTestEvent}>Publish test event</button>
              </div>
            </section>

            <section className="lw-neo-kpis">
              <div className="lw-neo-kpi safe"><span>Stream</span><strong>{status.stream || "—"}</strong></div>
              <div className="lw-neo-kpi"><span>Snapshot events</span><strong>{status.snapshot_event_count ?? generated.length}</strong></div>
              <div className="lw-neo-kpi"><span>Published buffer</span><strong>{status.published_buffer_count ?? published.length}</strong></div>
              <div className="lw-neo-kpi"><span>Event types</span><strong>{status.event_types?.length || 0}</strong></div>
            </section>

            <section className="lw-command-grid">
              <main className="lw-command-main">
                <div className="lw-section-title"><div><span>event rail</span><h2>Live operational events</h2></div><small>{allEvents.length} visible</small></div>
                <div className="lw-case-stack">
                  {allEvents.map((event, index) => (
                    <div className={`lw-case-card ${event.severity === "red" ? "danger" : event.severity === "amber" ? "warn" : "info"}`} key={event.id || index}>
                      <div className="lw-case-top"><span>{event.event_type || "event"}</span><small>{event.source || "system"}</small></div>
                      <h3>{event.title || "Realtime event"}</h3>
                      <p>{event.detail || "No detail supplied."}</p>
                      <div className="lw-case-meta"><span>{event.severity || "info"}</span><span>{event.entity_type || "system"}</span><span>{event.created_at || status.generated_at || "now"}</span></div>
                    </div>
                  ))}
                </div>
              </main>
              <aside className="lw-command-side">
                <div className="lw-section-title"><div><span>stream endpoint</span><h2>SSE ready</h2></div></div>
                <div className="lw-action-strip safe"><span>GET</span><div><strong>/api/realtime/stream</strong><small>Server-Sent Events endpoint for frontend live updates.</small></div></div>
                {(status.event_types || []).map((type) => <div className="lw-action-strip info" key={type}><span>TYPE</span><div><strong>{type}</strong><small>Realtime channel available.</small></div></div>)}
              </aside>
            </section>
          </div>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
