"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, apiJson } from "@/lib/api-client";

type Dashboard = {
  configuration: Array<Record<string, any>>;
  claims: Array<Record<string, any>>;
  workforce: Array<Record<string, any>>;
  competencies: Array<Record<string, any>>;
  replayRuns: Array<Record<string, any>>;
};

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 16, padding: 16, boxShadow: "0 6px 18px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", background: "white", color: "#0f172a" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "9px 12px", background: "#0f766e", color: "white", fontWeight: 800, cursor: "pointer" };

function pretty(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

export function BvsValidationTools() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await apiGet<Dashboard>("/api/bvs-v6/dashboard"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load BVS validation data");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function act(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(path, init);
      setMessage(success);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation action failed");
    } finally { setBusy(false); }
  }

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div><span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".12em", textTransform: "uppercase" }}>LucyWorks OS · governed validation</span><h1 style={{ margin: "5px 0", fontSize: "clamp(34px,7vw,66px)", lineHeight: .95 }}>BVS validation tools</h1></div>
        <Link href="/hospital-configuration" style={{ color: "white", textDecoration: "none", border: "1px solid #334155", borderRadius: 9, padding: "8px 11px", alignSelf: "start" }}>← Configuration workspace</Link>
      </div>
      <p style={{ color: "#94a3b8", maxWidth: 920 }}>Approve authoritative configuration, record scoped competencies and import anonymised historical events. Every mutation is versioned and evidence-attributed.</p>
    </header>

    {error && <div style={{ ...panel, borderColor: "#fca5a5", color: "#991b1b", marginTop: 10 }}>{error}</div>}
    {message && <div style={{ ...panel, borderColor: "#86efac", color: "#166534", marginTop: 10 }}>{message}</div>}
    {!data ? <section style={{ ...panel, marginTop: 10 }}>Loading…</section> : <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
      <ConfigurationRegister data={data} busy={busy} act={act} />
      <ClaimReview data={data} busy={busy} act={act} />
      <CompetencyRegister data={data} busy={busy} act={act} />
      <ReplayImporter data={data} busy={busy} act={act} />
    </div>}
  </main>;
}

function ConfigurationRegister({ data, busy, act }: { data: Dashboard; busy: boolean; act: (path: string, init: RequestInit, success: string) => Promise<void> }) {
  const [selectedKey, setSelectedKey] = useState("");
  const selected = useMemo(() => data.configuration.find(item => `${item.entityType}:${item.entityRef}` === selectedKey), [data.configuration, selectedKey]);
  const [name, setName] = useState("");
  const [attributes, setAttributes] = useState("{}");
  const [verificationStatus, setVerificationStatus] = useState("unverified");
  const [sourceRef, setSourceRef] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (!selected) return;
    setName(String(selected.name || ""));
    setAttributes(pretty(selected.attributes));
    setVerificationStatus(String(selected.verificationStatus || "unverified"));
    setSourceRef(String(selected.authoritativeSourceRef || ""));
    setReason("");
  }, [selected]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    let parsed: Record<string, unknown>;
    try { parsed = JSON.parse(attributes); } catch { throw new Error("Configuration attributes must be valid JSON"); }
    if (verificationStatus === "verified" && (!sourceRef.trim() || !reason.trim())) {
      throw new Error("Verified configuration requires an authoritative source reference and review reason");
    }
    await act(`/api/bvs-v6/configuration/${selected.entityType}/${selected.entityRef}`, {
      method: "PUT",
      body: JSON.stringify({ expectedVersion: selected.version, name, attributes: parsed, operationalStatus: selected.operationalStatus, verificationStatus, authoritativeSourceRef: sourceRef || undefined, reason }),
    }, "Authoritative configuration record updated.");
  }

  return <section style={panel}><h2 style={{ marginTop: 0 }}>Authoritative configuration register</h2><p style={{ color: "#475569" }}>Select a provisional record, edit its structured attributes and verify it only against approved hospital evidence.</p><form onSubmit={submit} style={{ display: "grid", gap: 8 }}><select required style={field} value={selectedKey} onChange={event => setSelectedKey(event.target.value)}><option value="">Select configuration record</option>{data.configuration.map(item => <option key={`${item.entityType}:${item.entityRef}`} value={`${item.entityType}:${item.entityRef}`}>{item.entityType} · {item.name} · v{item.version}</option>)}</select>{selected && <><input required style={field} value={name} onChange={event => setName(event.target.value)} /><textarea required style={{ ...field, minHeight: 150, fontFamily: "monospace" }} value={attributes} onChange={event => setAttributes(event.target.value)} /><select style={field} value={verificationStatus} onChange={event => setVerificationStatus(event.target.value)}><option value="unverified">Unverified</option><option value="provisional">Provisional</option><option value="verified">Verified</option><option value="retired">Retired</option></select><input style={field} placeholder="Authoritative evidence or document reference" value={sourceRef} onChange={event => setSourceRef(event.target.value)} /><textarea style={{ ...field, minHeight: 65 }} placeholder="Review reason and what was checked" value={reason} onChange={event => setReason(event.target.value)} /><button disabled={busy} style={{ ...button, justifySelf: "start" }}>Save versioned configuration</button></>}</form></section>;
}

function ClaimReview({ data, busy, act }: { data: Dashboard; busy: boolean; act: (path: string, init: RequestInit, success: string) => Promise<void> }) {
  const [form, setForm] = useState<Record<string, { status: string; evidence: string; notes: string }>>({});
  async function submit(item: Record<string, any>) {
    const current = form[item.claimRef] || { status: item.status, evidence: "", notes: "" };
    if (current.status === "verified" && !current.evidence.trim()) throw new Error("Verified claims require an evidence reference");
    await act(`/api/bvs-v6/claims/${item.claimRef}`, { method: "PATCH", body: JSON.stringify({ expectedVersion: item.version, status: current.status, evidenceRef: current.evidence || undefined, notes: current.notes, reason: current.notes || `Claim marked ${current.status}` }) }, "Configuration claim reviewed.");
  }
  return <section style={panel}><h2 style={{ marginTop: 0 }}>Configuration-claim decisions</h2>{data.claims.map(item => { const current = form[item.claimRef] || { status: item.status, evidence: "", notes: "" }; return <div key={item.claimRef} style={{ borderTop: "1px solid #e2e8f0", padding: "11px 0", display: "grid", gap: 7 }}><strong>{item.entityRef}.{item.fieldName} = {JSON.stringify(item.claimedValue)}</strong><div style={{ color: "#475569" }}>{item.sourceType} · {item.notes}</div><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 7 }}><select style={field} value={current.status} onChange={event => setForm({ ...form, [item.claimRef]: { ...current, status: event.target.value } })}><option value="disputed">Disputed</option><option value="verified">Verified</option><option value="rejected">Rejected</option><option value="superseded">Superseded</option></select><input style={field} placeholder="Evidence reference" value={current.evidence} onChange={event => setForm({ ...form, [item.claimRef]: { ...current, evidence: event.target.value } })} /><input style={field} placeholder="Review notes" value={current.notes} onChange={event => setForm({ ...form, [item.claimRef]: { ...current, notes: event.target.value } })} /></div><button disabled={busy} style={{ ...button, justifySelf: "start" }} onClick={() => submit(item)}>Record claim decision</button></div>; })}</section>;
}

function CompetencyRegister({ data, busy, act }: { data: Dashboard; busy: boolean; act: (path: string, init: RequestInit, success: string) => Promise<void> }) {
  const [form, setForm] = useState({ staffRef: "", competencyRef: "", scopeRef: "hospital", level: "supervised", status: "provisional", evidenceSummary: "", validFrom: "", validUntil: "" });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (form.status === "verified" && !form.evidenceSummary.trim()) throw new Error("Verified competency requires evidence");
    await act(`/api/bvs-v6/workforce/${encodeURIComponent(form.staffRef)}/competencies/${encodeURIComponent(form.competencyRef)}/${encodeURIComponent(form.scopeRef)}`, { method: "PUT", body: JSON.stringify({ level: form.level, status: form.status, evidenceSummary: form.evidenceSummary || undefined, validFrom: form.validFrom || undefined, validUntil: form.validUntil || undefined, reason: form.evidenceSummary || "Competency record maintained" }) }, "Scoped competency recorded.");
    setForm({ staffRef: "", competencyRef: "", scopeRef: "hospital", level: "supervised", status: "provisional", evidenceSummary: "", validFrom: "", validUntil: "" });
  }
  return <section style={panel}><h2 style={{ marginTop: 0 }}>Competency and privilege register</h2><form onSubmit={submit} style={{ display: "grid", gap: 8 }}><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 8 }}><select required style={field} value={form.staffRef} onChange={event => setForm({ ...form, staffRef: event.target.value })}><option value="">Select workforce profile</option>{data.workforce.map(item => <option key={item.staffRef} value={item.staffRef}>{item.displayName} · {item.primaryRoleRef}</option>)}</select><input required style={field} placeholder="Competency reference" value={form.competencyRef} onChange={event => setForm({ ...form, competencyRef: event.target.value })} /><input required style={field} placeholder="Scope: hospital, service or area" value={form.scopeRef} onChange={event => setForm({ ...form, scopeRef: event.target.value })} /><select style={field} value={form.level} onChange={event => setForm({ ...form, level: event.target.value })}><option value="observed">Observed only</option><option value="supervised">Supervised</option><option value="independent">Independent</option><option value="supervisor">Supervisor</option></select><select style={field} value={form.status} onChange={event => setForm({ ...form, status: event.target.value })}><option value="provisional">Provisional</option><option value="verified">Verified</option><option value="suspended">Suspended</option><option value="expired">Expired</option></select><input type="date" style={field} value={form.validFrom} onChange={event => setForm({ ...form, validFrom: event.target.value })} /><input type="date" style={field} value={form.validUntil} onChange={event => setForm({ ...form, validUntil: event.target.value })} /></div><textarea style={{ ...field, minHeight: 70 }} placeholder="Assessment, certificate or privilege evidence" value={form.evidenceSummary} onChange={event => setForm({ ...form, evidenceSummary: event.target.value })} /><button disabled={busy || !form.staffRef} style={{ ...button, justifySelf: "start" }}>Save competency</button></form><div style={{ marginTop: 10 }}>{data.competencies.map(item => <div key={`${item.staffRef}:${item.competencyRef}:${item.scopeRef}`} style={{ borderTop: "1px solid #e2e8f0", padding: "8px 0" }}><strong>{item.staffRef}</strong> · {item.competencyRef} · {item.scopeRef} · {item.status} · v{item.version}</div>)}</div></section>;
}

function ReplayImporter({ data, busy, act }: { data: Dashboard; busy: boolean; act: (path: string, init: RequestInit, success: string) => Promise<void> }) {
  const today = new Date().toISOString().slice(0, 10);
  const [sourceDate, setSourceDate] = useState(today);
  const [eventsJson, setEventsJson] = useState("[\n  {\n    \"eventRef\": \"example-1\",\n    \"occurredAt\": \"2026-07-24T09:00:00Z\",\n    \"eventType\": \"delay\",\n    \"areaRef\": \"mri\",\n    \"payload\": {\n      \"expectedAlert\": true,\n      \"lucyworksDetected\": true,\n      \"decisionLatencyMinutes\": 5\n    }\n  }\n]");
  async function submit(event: FormEvent) {
    event.preventDefault();
    let events: Array<Record<string, unknown>>;
    try { events = JSON.parse(eventsJson); } catch { throw new Error("Replay events must be valid JSON"); }
    if (!Array.isArray(events) || events.length === 0) throw new Error("Replay import requires a non-empty JSON array");
    await act("/api/bvs-v6/historical-replays", { method: "POST", body: JSON.stringify({ sourceDate, dataClassification: "anonymised", events }) }, "Anonymised historical replay imported and analysed.");
  }
  return <section style={panel}><h2 style={{ marginTop: 0 }}>Anonymised historical-event importer</h2><p style={{ color: "#475569" }}>Paste an anonymised event array. Identifiable patient, owner or staff data must not be entered until the hospital approves a lawful process.</p><form onSubmit={submit} style={{ display: "grid", gap: 8 }}><input required type="date" style={field} value={sourceDate} onChange={event => setSourceDate(event.target.value)} /><textarea required style={{ ...field, minHeight: 260, fontFamily: "monospace" }} value={eventsJson} onChange={event => setEventsJson(event.target.value)} /><button disabled={busy} style={{ ...button, justifySelf: "start" }}>Import and analyse replay</button></form><div style={{ marginTop: 10 }}>{data.replayRuns.map(item => <div key={item.runRef} style={{ borderTop: "1px solid #e2e8f0", padding: "8px 0" }}><strong>{item.runRef}</strong> · {item.sourceDate} · {item.status} · {item.eventCount} events</div>)}</div></section>;
}
