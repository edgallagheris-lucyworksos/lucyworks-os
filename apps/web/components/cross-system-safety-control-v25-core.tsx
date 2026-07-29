"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";

export const safetyControlRoles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];

type Owner = { subject?: string | null; name?: string | null; role?: string | null };
type RecordRow = {
  recordRef: string; recordType: string; domain: string; confidentiality: string; severity: string; status: string;
  title: string; summary: string; protectiveSummary?: string | null; patientRef?: string | null; episodeRef?: string | null;
  safetyHoldRequested: boolean; accountableOwner: Owner; clinicalOwner: Owner; independentOwner: Owner;
  rootCause?: string | null; recurrenceControls: string[]; version: number; dueAt?: string | null;
};
type ActionRow = {
  recordRef: string; actionRef: string; actionType: string; title: string; description: string; owner: Owner;
  status: string; completionEvidence?: string | null; requiresIndependentVerification: boolean;
  verificationStatus: string; version: number;
};
type Bundle = { record: RecordRow; actions: ActionRow[]; closureGate: { eligible: boolean; blockers: { code: string; message: string }[] } };
type Indicator = { recordRef: string; title: string; summary: string; severity: string; status: string; confidentiality: string; safetyHoldRequested: boolean; ownerRole?: string | null };
type Contracts = { recordTypes: string[]; domains: string[]; confidentiality: string[]; severities: string[]; principles: string[] };

const field = { width: "100%", padding: 10, border: "1px solid #cbd5e1", borderRadius: 9, background: "white", color: "#0f172a" } as const;
const press = { border: 0, borderRadius: 9, padding: "10px 13px", fontWeight: 850, cursor: "pointer" } as const;
const roles = ["clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];
function words(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()); }
function edge(value: string) { return ["red", "critical"].includes(value) ? "#b91c1c" : value === "amber" ? "#d97706" : "#047857"; }

export function CrossSystemSafetyControlV25() {
  const [contracts, setContracts] = useState<Contracts | null>(null);
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [selected, setSelected] = useState("");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [status, setStatus] = useState("Loading authenticated safety state");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({ recordType: "patient_safety", domain: "patient", confidentiality: "standard", severity: "amber", title: "", summary: "", protectiveSummary: "", patientRef: "", episodeRef: "", affectedStaffSubject: "", safetyHoldRequested: false });
  const [action, setAction] = useState({ actionType: "protective", title: "", description: "", ownerSubject: "", ownerName: "", ownerRole: "ops_manager" });
  const [evidence, setEvidence] = useState("");
  const [reason, setReason] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [controls, setControls] = useState("");

  const refresh = useCallback(async () => {
    const [contractData, recordData, indicatorData] = await Promise.all([
      apiGet<Contracts>("/api/v25/safety/contracts"),
      apiGet<{ records: RecordRow[] }>("/api/v25/safety/records"),
      apiGet<{ indicators: Indicator[] }>("/api/v25/safety/board-indicators"),
    ]);
    setContracts(contractData); setRecords(recordData.records); setIndicators(indicatorData.indicators);
    setSelected(current => current || recordData.records[0]?.recordRef || "");
  }, []);
  const load = useCallback(async (recordRef: string) => {
    if (!recordRef) { setBundle(null); return; }
    setBundle(await apiGet<Bundle>(`/api/v25/safety/records/${encodeURIComponent(recordRef)}?reason=Safety%20command%20review`));
  }, []);

  useEffect(() => { refresh().then(() => setStatus("Live safety state")).catch(error => setStatus(error instanceof Error ? error.message : "Safety control unavailable")); }, [refresh]);
  useEffect(() => { void load(selected).catch(error => setStatus(error instanceof Error ? error.message : "Record unavailable")); }, [selected, load]);

  const counts = useMemo(() => ({ open: indicators.length, red: indicators.filter(row => ["red", "critical"].includes(row.severity)).length, holds: indicators.filter(row => row.safetyHoldRequested).length, restricted: indicators.filter(row => row.confidentiality !== "standard").length }), [indicators]);

  async function run(label: string, task: () => Promise<void>, ref = selected) {
    try { setBusy(true); setStatus(`${label} in progress`); await task(); await refresh(); if (ref) await load(ref); setStatus(`${label} completed`); }
    catch (error) { setStatus(error instanceof Error ? error.message : `${label} failed`); }
    finally { setBusy(false); }
  }

  async function report() {
    if (draft.title.trim().length < 4 || draft.summary.trim().length < 8) { setStatus("A clear title and summary are required"); return; }
    let ref = "";
    await run("Safety report", async () => {
      const result = await apiPost<Bundle>("/api/v25/safety/records", {
        ...draft, patientRef: draft.patientRef || undefined, episodeRef: draft.episodeRef || undefined,
        affectedStaffSubject: draft.affectedStaffSubject || undefined,
        immediateRisk: ["red", "critical"].includes(draft.severity),
      });
      ref = result.record.recordRef; setSelected(ref); setBundle(result);
      setDraft(current => ({ ...current, title: "", summary: "", protectiveSummary: "", patientRef: "", episodeRef: "", affectedStaffSubject: "", safetyHoldRequested: false }));
    }, ref);
    if (ref) await load(ref);
  }

  async function addAction() {
    if (!bundle || action.title.trim().length < 4 || !action.ownerSubject || !action.ownerName) { setStatus("Action title and named owner are required"); return; }
    await run("Safety action", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/actions`, {
        actionType: action.actionType, title: action.title, description: action.description,
        owner: { subject: action.ownerSubject, name: action.ownerName, role: action.ownerRole },
      });
      setAction(current => ({ ...current, title: "", description: "" }));
    });
  }

  async function complete(row: ActionRow) {
    if (evidence.trim().length < 8) { setStatus("Completion evidence must explain what was done"); return; }
    await run("Action completion", async () => {
      await apiJson(`/api/v25/safety/records/${encodeURIComponent(bundle!.record.recordRef)}/actions/${encodeURIComponent(row.actionRef)}/complete`, { method: "PATCH", body: JSON.stringify({ expectedVersion: row.version, completionEvidence: evidence }) });
      setEvidence("");
    });
  }

  async function verify(row: ActionRow, decision: "verified" | "rejected") {
    if (evidence.trim().length < 8) { setStatus("Independent verification note is required"); return; }
    await run("Action verification", async () => {
      await apiJson(`/api/v25/safety/records/${encodeURIComponent(bundle!.record.recordRef)}/actions/${encodeURIComponent(row.actionRef)}/verify`, { method: "PATCH", body: JSON.stringify({ expectedVersion: row.version, decision, note: evidence }) });
      setEvidence("");
    });
  }

  async function escalate() {
    if (!bundle || reason.trim().length < 8) { setStatus("Escalation reason is required"); return; }
    await run("Escalation", async () => { await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/escalations`, { reason, to: { role: "governance_lead" } }); });
  }

  async function reviewClosure() {
    if (!bundle || reason.trim().length < 8) { setStatus("Independent review reason is required"); return; }
    await run("Closure review", async () => { await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/closure-review`, { decision: "approved", reason }); });
  }

  async function closeRecord() {
    if (!bundle || reason.trim().length < 8) { setStatus("Closure reason is required"); return; }
    await run("Record closure", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/close`, { expectedVersion: bundle.record.version, rootCause, recurrenceControls: controls.split("\n").map(value => value.trim()).filter(Boolean), reason });
    });
  }

  return <main style={{ minHeight: "100vh", background: "#e8edf3", color: "#0f172a", padding: 10, fontFamily: "Inter,system-ui,sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}><span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>LUCYWORKS SAFETY CONTROL · V25</span><h1 style={{ fontSize: "clamp(36px,8vw,70px)", lineHeight: .94, margin: "7px 0" }}>Protect first. Name the owner. Prove the fix.</h1><p style={{ maxWidth: 950, color: "#b8c5d4" }}>One authenticated route for patient incidents, staff welfare, conduct, safeguarding, complaints and mixed operational events. General boards receive the protective consequence, not confidential HR detail.</p><div style={{ display: "flex", gap: 10 }}><Link href="/workspace" style={{ color: "white" }}>Patient Command</Link><Link href="/hospital-board" style={{ color: "white" }}>Hospital Today</Link><Link href="/system-control" style={{ color: "white" }}>System Control</Link></div></header>

    <section style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 8, marginTop: 8 }}>{Object.entries(counts).map(([label, value]) => <article key={label} style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 12, padding: 11 }}><small style={{ color: "#64748b", fontWeight: 850 }}>{words(label)}</small><strong style={{ display: "block", fontSize: 28 }}>{value}</strong></article>)}</section>
    <p style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 10, padding: 10, fontWeight: 750 }}>{status}</p>

    <section style={{ display: "grid", gridTemplateColumns: "minmax(280px,.85fr) minmax(0,1.55fr)", gap: 9 }}>
      <aside style={{ display: "grid", gap: 9, alignContent: "start" }}>
        <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}><h2 style={{ marginTop: 0 }}>Report concern</h2><div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}><label>Type<select style={field} value={draft.recordType} onChange={event => setDraft({ ...draft, recordType: event.target.value })}>{contracts?.recordTypes.map(value => <option key={value}>{value}</option>)}</select></label><label>Domain<select style={field} value={draft.domain} onChange={event => setDraft({ ...draft, domain: event.target.value })}>{contracts?.domains.map(value => <option key={value}>{value}</option>)}</select></label><label>Severity<select style={field} value={draft.severity} onChange={event => setDraft({ ...draft, severity: event.target.value })}>{contracts?.severities.map(value => <option key={value}>{value}</option>)}</select></label><label>Privacy<select style={field} value={draft.confidentiality} onChange={event => setDraft({ ...draft, confidentiality: event.target.value })}>{contracts?.confidentiality.map(value => <option key={value}>{value}</option>)}</select></label></div><label>Title<input style={field} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} /></label><label>What happened<textarea style={{ ...field, minHeight: 75 }} value={draft.summary} onChange={event => setDraft({ ...draft, summary: event.target.value })} /></label><label>Board-safe protection<textarea style={{ ...field, minHeight: 55 }} value={draft.protectiveSummary} onChange={event => setDraft({ ...draft, protectiveSummary: event.target.value })} /></label><div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}><label>Patient ref<input style={field} value={draft.patientRef} onChange={event => setDraft({ ...draft, patientRef: event.target.value })} /></label><label>Episode ref<input style={field} value={draft.episodeRef} onChange={event => setDraft({ ...draft, episodeRef: event.target.value })} /></label></div><label>Affected staff subject<input style={field} value={draft.affectedStaffSubject} onChange={event => setDraft({ ...draft, affectedStaffSubject: event.target.value })} /></label><label style={{ display: "flex", gap: 7, margin: "8px 0" }}><input type="checkbox" checked={draft.safetyHoldRequested} onChange={event => setDraft({ ...draft, safetyHoldRequested: event.target.checked })} />Request operational safety hold</label><button disabled={busy} onClick={report} style={{ ...press, width: "100%", background: "#0f766e", color: "white" }}>Create protected record</button></article>
        <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}><h2 style={{ marginTop: 0 }}>Open indicators</h2><div style={{ display: "grid", gap: 6 }}>{indicators.map(row => <button key={row.recordRef} onClick={() => setSelected(row.recordRef)} style={{ textAlign: "left", padding: 9, border: `1px solid ${edge(row.severity)}`, borderLeftWidth: 6, borderRadius: 9, background: selected === row.recordRef ? "#e0f2fe" : "#f8fafc", cursor: "pointer" }}><strong>{row.title}</strong><span style={{ display: "block", color: "#475569" }}>{row.summary}</span><small>{words(row.severity)} · {words(row.status)} · {row.ownerRole || "Unowned"}</small></button>)}</div></article>
      </aside>

      <section style={{ display: "grid", gap: 9, alignContent: "start" }}>{!bundle ? <article style={{ background: "white", borderRadius: 14, padding: 20 }}>Select a visible record.</article> : <><article style={{ background: "white", border: `1px solid ${edge(bundle.record.severity)}`, borderLeftWidth: 8, borderRadius: 14, padding: 14 }}><small style={{ fontWeight: 900 }}>{words(bundle.record.recordType)} · {words(bundle.record.domain)} · {words(bundle.record.confidentiality)}</small><h2 style={{ fontSize: 29, margin: "5px 0" }}>{bundle.record.title}</h2><p>{bundle.record.summary}</p><p style={{ background: "#f1f5f9", padding: 9, borderRadius: 8 }}><strong>Board-safe protection:</strong> {bundle.record.protectiveSummary || "Not separately recorded"}</p><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 6 }}><b>{words(bundle.record.status)}</b><b>{words(bundle.record.severity)}</b><b>Patient: {bundle.record.patientRef || "None"}</b><b>Episode: {bundle.record.episodeRef || "None"}</b><b>Hold: {bundle.record.safetyHoldRequested ? "Requested" : "No"}</b></div></article>

      <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}><h2 style={{ marginTop: 0 }}>Named actions</h2><div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 7 }}><label>Type<select style={field} value={action.actionType} onChange={event => setAction({ ...action, actionType: event.target.value })}>{["protective","clinical_review","operational","communication","investigation","corrective","monitoring","welfare_support"].map(value => <option key={value}>{value}</option>)}</select></label><label>Owner subject<input style={field} value={action.ownerSubject} onChange={event => setAction({ ...action, ownerSubject: event.target.value })} /></label><label>Owner role<select style={field} value={action.ownerRole} onChange={event => setAction({ ...action, ownerRole: event.target.value })}>{roles.map(value => <option key={value}>{value}</option>)}</select></label></div><label>Owner name<input style={field} value={action.ownerName} onChange={event => setAction({ ...action, ownerName: event.target.value })} /></label><label>Action title<input style={field} value={action.title} onChange={event => setAction({ ...action, title: event.target.value })} /></label><label>Description<textarea style={{ ...field, minHeight: 52 }} value={action.description} onChange={event => setAction({ ...action, description: event.target.value })} /></label><button onClick={addAction} style={{ ...press, background: "#1d4ed8", color: "white" }}>Assign action</button><div style={{ display: "grid", gap: 6, marginTop: 9 }}>{bundle.actions.map(row => <section key={row.actionRef} style={{ border: "1px solid #cbd5e1", borderRadius: 9, padding: 9 }}><strong>{row.title}</strong><span style={{ display: "block" }}>{words(row.actionType)} · {row.owner.name || row.owner.role} · {words(row.status)} · {words(row.verificationStatus)}</span><div style={{ display: "flex", gap: 6, marginTop: 6 }}>{row.status !== "completed" && <button onClick={() => complete(row)} style={{ ...press, background: "#0f766e", color: "white" }}>Complete</button>}{row.status === "completed" && row.verificationStatus === "pending" && <><button onClick={() => verify(row, "verified")} style={{ ...press, background: "#047857", color: "white" }}>Verify</button><button onClick={() => verify(row, "rejected")} style={{ ...press, background: "#b91c1c", color: "white" }}>Reject</button></>}</div></section>)}</div><label>Completion / verification evidence<textarea style={{ ...field, minHeight: 58 }} value={evidence} onChange={event => setEvidence(event.target.value)} /></label></article>

      <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}><h2 style={{ marginTop: 0 }}>Escalation and closure</h2><div style={{ background: bundle.closureGate.eligible ? "#ecfdf5" : "#fff7ed", padding: 9, borderRadius: 9 }}><strong>{bundle.closureGate.eligible ? "Closure gate clear" : "Closure blocked"}</strong>{bundle.closureGate.blockers.map(item => <div key={`${item.code}-${item.message}`}>{item.message}</div>)}</div><label>Reason<textarea style={{ ...field, minHeight: 52 }} value={reason} onChange={event => setReason(event.target.value)} /></label><label>Root cause<textarea style={{ ...field, minHeight: 52 }} value={rootCause} onChange={event => setRootCause(event.target.value)} /></label><label>Recurrence controls — one per line<textarea style={{ ...field, minHeight: 62 }} value={controls} onChange={event => setControls(event.target.value)} /></label><div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}><button onClick={escalate} style={{ ...press, background: "#b45309", color: "white" }}>Escalate</button><button onClick={reviewClosure} style={{ ...press, background: "#334155", color: "white" }}>Independent review</button><button onClick={closeRecord} style={{ ...press, background: "#047857", color: "white" }}>Close after gates</button></div></article></>}</section>
    </section>
    <details style={{ marginTop: 9, background: "white", border: "1px solid #cbd5e1", borderRadius: 12, padding: 11 }}><summary style={{ cursor: "pointer", fontWeight: 900 }}>Authority boundary</summary>{contracts?.principles.map(item => <p key={item}>{item}</p>)}</details>
  </main>;
}
