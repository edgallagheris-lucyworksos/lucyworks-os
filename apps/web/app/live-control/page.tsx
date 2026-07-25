"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { apiGet, apiJson, API_BASE } from "@/lib/api-client";

type Ack = { status: string; version: number; note?: string | null; acknowledgedByName?: string | null };
type LiveEvent = {
  eventRef: string; sequence: number; eventType: string; aggregateType: string; aggregateRef: string;
  payload: Record<string, unknown>; severity: string; actorName: string; actorRole: string;
  correlationId?: string | null; createdAt: string; acknowledgement?: Ack | null;
};
type RetryJob = { jobRef: string; envelopeRef: string; connectionRef: string; status: string; attemptCount: number; maximumAttempts: number; nextAttemptAt: string; lastError?: string | null; version: number };

const panel: React.CSSProperties = { background: "#0f172a", border: "1px solid #334155", borderRadius: 14, padding: 13 };
const button: React.CSSProperties = { border: 0, borderRadius: 8, padding: "9px 11px", minHeight: 42, background: "#0f766e", color: "white", fontWeight: 800, cursor: "pointer" };

export default function LiveControlPage() {
  return <AuthGuard allowedRoles={["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"]}>
    <LiveControl />
  </AuthGuard>;
}

function LiveControl() {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [jobs, setJobs] = useState<RetryJob[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const cursor = useRef(0);

  const load = useCallback(async () => {
    try {
      const [eventData, jobData] = await Promise.all([
        apiGet<{ events: LiveEvent[]; nextSequence: number }>("/api/v7/events?after_sequence=0&limit=250"),
        apiGet<{ jobs: RetryJob[] }>("/api/v7/integration-retries/jobs"),
      ]);
      setEvents(eventData.events || []);
      cursor.current = eventData.nextSequence || 0;
      setJobs(jobData.jobs || []);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load live control");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/api/v7/events/stream?after_sequence=${cursor.current}`, { withCredentials: true });
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = event => {
      try {
        const row = JSON.parse(event.data) as LiveEvent;
        if (!row.eventRef) return;
        cursor.current = Math.max(cursor.current, row.sequence || 0);
        setEvents(current => [...current.filter(item => item.eventRef !== row.eventRef), row].slice(-300));
      } catch { /* keepalive or malformed external event */ }
    };
    return () => source.close();
  }, []);

  async function acknowledge(row: LiveEvent, status: string) {
    const note = window.prompt(`${status} reason:`);
    if (!note) return;
    setBusy(true);
    try {
      const result = await apiJson<{ acknowledgement: Ack }>(`/api/v7/events/${row.eventRef}/acknowledgement`, { method: "PATCH", body: JSON.stringify({ expected_version: row.acknowledgement?.version || 0, status, note }) });
      setEvents(current => current.map(item => item.eventRef === row.eventRef ? { ...item, acknowledgement: result.acknowledgement } : item));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Acknowledgement failed");
    } finally { setBusy(false); }
  }

  async function runRetries() {
    setBusy(true);
    try {
      await apiJson("/api/v7/integration-retries/enqueue-failed", { method: "POST" });
      await apiJson("/api/v7/integration-retries/run-due?limit=50", { method: "POST" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Retry processing failed");
    } finally { setBusy(false); }
  }

  async function replay(job: RetryJob) {
    setBusy(true);
    try {
      await apiJson(`/api/v7/integration-retries/jobs/${job.jobRef}/replay`, { method: "POST" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Replay failed");
    } finally { setBusy(false); }
  }

  const unresolved = events.filter(row => ["red", "error", "critical"].includes(row.severity) && row.acknowledgement?.status !== "resolved");
  const deadLetters = jobs.filter(row => row.status === "dead_letter");

  return <main style={{ minHeight: "100vh", background: "#020617", color: "white", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ ...panel, background: "#071019" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".12em" }}>DURABLE CONTROL STREAM</span><h1 style={{ margin: "5px 0", fontSize: "clamp(34px,7vw,66px)", lineHeight: .95 }}>Live control</h1></div>
        <Link href="/system-control" style={{ color: "white" }}>← System control</Link>
      </div>
      <p style={{ color: "#94a3b8" }}>Database-backed events, reconnect replay, named acknowledgement, escalation and integration dead-letter recovery.</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><span style={{ color: connected ? "#86efac" : "#fca5a5" }}>Stream: {connected ? "connected" : "reconnecting"}</span><button style={button} disabled={busy} onClick={() => void load()}>Refresh</button><button style={{ ...button, background: "#2563eb" }} disabled={busy} onClick={() => void runRetries()}>Process integration retries</button></div>
    </header>
    {error && <section aria-live="assertive" style={{ ...panel, marginTop: 10, borderColor: "#ef4444", color: "#fecaca" }}>{error}</section>}

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 8, marginTop: 10 }}>
      <div style={panel}><small>Stored events</small><div style={{ fontSize: 30, fontWeight: 900 }}>{events.length}</div></div>
      <div style={{ ...panel, borderColor: unresolved.length ? "#ef4444" : "#22c55e" }}><small>Unresolved red events</small><div style={{ fontSize: 30, fontWeight: 900 }}>{unresolved.length}</div></div>
      <div style={{ ...panel, borderColor: deadLetters.length ? "#ef4444" : "#22c55e" }}><small>Dead letters</small><div style={{ fontSize: 30, fontWeight: 900 }}>{deadLetters.length}</div></div>
      <div style={panel}><small>Queued retries</small><div style={{ fontSize: 30, fontWeight: 900 }}>{jobs.filter(row => row.status === "queued").length}</div></div>
    </section>

    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,420px),1fr))", gap: 10, marginTop: 10 }}>
      <div style={{ display: "grid", gap: 8, alignContent: "start", minWidth: 0 }}>
        <h2 style={{ margin: 0 }}>Event stream</h2>
        {[...events].reverse().map(row => <article key={row.eventRef} style={{ ...panel, borderColor: ["red", "error", "critical"].includes(row.severity) ? "#ef4444" : row.severity === "warning" ? "#f59e0b" : "#334155", minWidth: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong>#{row.sequence} · {row.eventType.replaceAll("_", " ")}</strong><span>{row.severity.toUpperCase()}</span></div>
          <p style={{ color: "#cbd5e1", overflowWrap: "anywhere" }}>{row.aggregateType}: {row.aggregateRef}</p>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", background: "#020617", padding: 8, borderRadius: 8, maxHeight: 180, overflow: "auto" }}>{JSON.stringify(row.payload, null, 2)}</pre>
          <small style={{ color: "#94a3b8" }}>{new Date(row.createdAt).toLocaleString()} · {row.actorName} ({row.actorRole})</small>
          <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginTop: 8 }}>
            <button disabled={busy} style={button} onClick={() => void acknowledge(row, "acknowledged")}>Acknowledge</button>
            <button disabled={busy} style={{ ...button, background: "#a16207" }} onClick={() => void acknowledge(row, "escalated")}>Escalate</button>
            <button disabled={busy} style={{ ...button, background: "#2563eb" }} onClick={() => void acknowledge(row, "resolved")}>Resolve</button>
          </div>
          {row.acknowledgement && <p style={{ color: "#86efac", marginBottom: 0 }}>Status: {row.acknowledgement.status} · {row.acknowledgement.acknowledgedByName} · {row.acknowledgement.note}</p>}
        </article>)}
      </div>

      <aside style={{ display: "grid", gap: 8, alignContent: "start", minWidth: 0 }}>
        <h2 style={{ margin: 0 }}>Integration reliability</h2>
        {jobs.map(job => <article key={job.jobRef} style={{ ...panel, borderColor: job.status === "dead_letter" ? "#ef4444" : "#334155" }}>
          <strong>{job.connectionRef}</strong><p style={{ margin: "6px 0" }}>{job.status} · attempt {job.attemptCount}/{job.maximumAttempts}</p><small style={{ color: "#94a3b8", overflowWrap: "anywhere" }}>{job.envelopeRef}</small>{job.lastError && <p style={{ color: "#fecaca", overflowWrap: "anywhere" }}>{job.lastError}</p>}{job.status === "dead_letter" && <button disabled={busy} style={button} onClick={() => void replay(job)}>Queue controlled replay</button>}
        </article>)}
      </aside>
    </section>
  </main>;
}
