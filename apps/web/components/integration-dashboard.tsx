"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Connection = {
  id: number;
  connectionRef: string;
  integrationType: string;
  vendor: string;
  direction: string;
  status: string;
  premisesRef: string;
  endpointUrl?: string | null;
  secretEnv: string;
  storePayload: boolean;
  accountableOwner: string;
  createdBy: string;
  lastReceivedAt?: string | null;
  lastProcessedAt?: string | null;
  lastError?: string | null;
};

type Envelope = {
  id: number;
  envelopeRef: string;
  connectionRef: string;
  messageType: string;
  externalEventId?: string | null;
  payloadHash: string;
  payloadStored: boolean;
  status: string;
  internalRecordType?: string | null;
  internalRecordRef?: string | null;
  evidenceEventRef?: string | null;
  error?: string | null;
  receivedAt?: string | null;
  processedAt?: string | null;
};

type Dashboard = {
  summary: {
    connections: number;
    activeConnections: number;
    failedConnections: number;
    processedMessages: number;
    failedMessages: number;
  };
  connections: Connection[];
  recentEnvelopes: Envelope[];
};

const emptyDashboard: Dashboard = {
  summary: { connections: 0, activeConnections: 0, failedConnections: 0, processedMessages: 0, failedMessages: 0 },
  connections: [],
  recentEnvelopes: [],
};

function when(value?: string | null) {
  return value ? new Date(value).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "never";
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["failed", "suspended", "disabled"].includes(normal)) return "red";
  if (["draft", "paused", "received"].includes(normal)) return "amber";
  return "green";
}

export function IntegrationDashboard() {
  const [data, setData] = useState<Dashboard>(emptyDashboard);
  const [status, setStatus] = useState("loading");
  const [form, setForm] = useState({
    connectionRef: "",
    integrationType: "pims",
    vendor: "",
    secretEnv: "",
    accountableOwner: "Hospital Operations",
    status: "draft",
    storePayload: false,
  });

  async function refresh() {
    setStatus("refreshing");
    try {
      const response = await apiFetch("/api/integrations/dashboard", { cache: "no-store" });
      if (!response.ok) throw new Error(`integration dashboard unavailable: ${response.status}`);
      setData(await response.json());
      setStatus("live database");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "offline");
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function createConnection(event: FormEvent) {
    event.preventDefault();
    setStatus("creating connection");
    try {
      const response = await apiFetch("/api/integrations/connections", {
        method: "POST",
        body: JSON.stringify({
          connectionRef: form.connectionRef || undefined,
          integrationType: form.integrationType,
          vendor: form.vendor,
          secretEnv: form.secretEnv,
          accountableOwner: form.accountableOwner,
          status: form.status,
          storePayload: form.storePayload,
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `connection creation failed: ${response.status}`);
      setForm({ connectionRef: "", integrationType: "pims", vendor: "", secretEnv: "", accountableOwner: "Hospital Operations", status: "draft", storePayload: false });
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "connection creation failed");
    }
  }

  return <main className="integrationDash"><style>{css}</style>
    <header>
      <div><span>LucyWorks OS</span><h1>External integrations</h1><p>Governed PIMS, imaging, laboratory and HR connections. Secrets remain in deployment environment variables; LucyWorks stores hashes, provenance and normalised operational records.</p></div>
      <nav><a href="/control-plane">Control plane</a><a href="/patient-care">Patient care</a><a href="/compliance">Compliance</a><button onClick={() => void refresh()}>Refresh</button></nav>
    </header>

    <section className="kpis">
      <article className="green"><b>{data.summary.activeConnections}</b><small>active connections</small></article>
      <article className={data.summary.failedConnections ? "red" : "green"}><b>{data.summary.failedConnections}</b><small>connections with errors</small></article>
      <article className="green"><b>{data.summary.processedMessages}</b><small>processed messages</small></article>
      <article className={data.summary.failedMessages ? "red" : "green"}><b>{data.summary.failedMessages}</b><small>failed messages</small></article>
      <article className="amber"><b>{data.summary.connections}</b><small>registered connections</small></article>
    </section>

    <section className="layout">
      <article className="panel">
        <h2>Register connection</h2>
        <form onSubmit={(event) => void createConnection(event)}>
          <label>Connection reference<input value={form.connectionRef} onChange={(event) => setForm({ ...form, connectionRef: event.target.value })} placeholder="e.g. pims-main" /></label>
          <label>Integration type<select value={form.integrationType} onChange={(event) => setForm({ ...form, integrationType: event.target.value })}><option value="pims">PIMS</option><option value="imaging">Imaging / PACS</option><option value="laboratory">Laboratory</option><option value="hr">HR / workforce</option></select></label>
          <label>Vendor<input required value={form.vendor} onChange={(event) => setForm({ ...form, vendor: event.target.value })} placeholder="system or supplier name" /></label>
          <label>Signing secret environment variable<input required value={form.secretEnv} onChange={(event) => setForm({ ...form, secretEnv: event.target.value })} placeholder="PIMS_WEBHOOK_SECRET" /></label>
          <label>Accountable owner<input required value={form.accountableOwner} onChange={(event) => setForm({ ...form, accountableOwner: event.target.value })} /></label>
          <label>Status<select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="draft">draft</option><option value="active">active</option><option value="paused">paused</option></select></label>
          <label className="check"><input type="checkbox" checked={form.storePayload} onChange={(event) => setForm({ ...form, storePayload: event.target.checked })} /> Store raw payloads</label>
          <button type="submit">Register governed connection</button>
          <small>{status}</small>
        </form>
      </article>

      <article className="panel wide">
        <h2>Connection health</h2>
        {data.connections.length ? data.connections.map((item) => <div className={`row ${tone(item.lastError ? "failed" : item.status)}`} key={item.id}>
          <div><strong>{item.vendor}</strong><span>{item.connectionRef} · {item.integrationType} · owner {item.accountableOwner}</span><p>Secret: {item.secretEnv} · payload retention {item.storePayload ? "enabled" : "disabled"}</p>{item.lastError ? <p className="error">{item.lastError}</p> : null}</div>
          <aside><b>{item.status}</b><small>received {when(item.lastReceivedAt)}</small><small>processed {when(item.lastProcessedAt)}</small></aside>
        </div>) : <p className="empty">No integration connections registered.</p>}
      </article>

      <article className="panel full">
        <h2>Recent integration envelopes</h2>
        {data.recentEnvelopes.length ? data.recentEnvelopes.map((item) => <div className={`row ${tone(item.status)}`} key={item.id}>
          <div><strong>{item.messageType}</strong><span>{item.connectionRef} · external {item.externalEventId || "ID not supplied"}</span><p>{item.internalRecordType || "evidence"} {item.internalRecordRef || ""} · evidence {item.evidenceEventRef || "not created"}</p><code>{item.payloadHash.slice(0, 24)}…</code>{item.error ? <p className="error">{item.error}</p> : null}</div>
          <aside><b>{item.status}</b><small>{when(item.receivedAt)}</small><small>raw payload {item.payloadStored ? "stored" : "not stored"}</small></aside>
        </div>) : <p className="empty">No integration messages received.</p>}
      </article>
    </section>
  </main>;
}

const css = `.integrationDash{min-height:100vh;background:#eef2f7;color:#111827;padding:14px;font-family:Inter,system-ui,sans-serif}.integrationDash *{box-sizing:border-box}.integrationDash header{display:flex;justify-content:space-between;gap:16px;background:#fff;border:1px solid #d7dee9;border-radius:20px;padding:18px;box-shadow:0 12px 30px rgba(15,23,42,.07)}.integrationDash header span{display:block;color:#0f766e;font-size:11px;font-weight:900;letter-spacing:.16em;text-transform:uppercase}.integrationDash h1{font-size:clamp(34px,7vw,68px);line-height:.94;margin:6px 0}.integrationDash p{color:#475569;margin:5px 0}.integrationDash nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.integrationDash a,.integrationDash button{border:1px solid #cbd5e1;border-radius:999px;background:#fff;color:#0f172a;padding:9px 12px;text-decoration:none;font-weight:800;cursor:pointer}.integrationDash button{background:#0f172a;color:#fff}.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px;margin:12px 0}.kpis article,.panel{background:#fff;border:1px solid #d7dee9;border-radius:17px;padding:13px}.kpis article{border-top:5px solid #94a3b8}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{font-size:32px;display:block}.kpis small{color:#64748b}.layout{display:grid;grid-template-columns:minmax(280px,.35fr) 1fr;gap:12px}.panel.full{grid-column:1/-1}.panel h2{margin:0 0 10px}.panel form{display:grid;gap:9px}.panel label{display:grid;gap:4px;color:#475569;font-size:12px;font-weight:800}.panel .check{display:flex;align-items:center;gap:8px}.panel input,.panel select{width:100%;border:1px solid #cbd5e1;border-radius:10px;padding:9px;background:white;color:#0f172a;font:inherit}.row{display:flex;justify-content:space-between;gap:12px;border:1px solid #e2e8f0;border-left:6px solid #64748b;border-radius:13px;padding:10px;margin-bottom:8px;background:#fff}.row.red{border-left-color:#dc2626;background:#fff7f7}.row.amber{border-left-color:#f59e0b;background:#fffbeb}.row.green{border-left-color:#16a34a;background:#f6fff8}.row strong,.row span,.row small,.row code{display:block}.row span,.row small{color:#64748b;font-size:12px;margin-top:3px}.row code{color:#475569;margin-top:5px}.row aside{text-align:right;min-width:145px}.row aside b{text-transform:capitalize}.error{color:#b91c1c!important}.empty{color:#64748b}@media(max-width:900px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.layout{grid-template-columns:1fr}.panel.full{grid-column:auto}.integrationDash header{display:grid}.row{display:grid}.row aside{text-align:left}}`;
