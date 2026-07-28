"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";

export const safetyControlRoles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];

type Owner = { subject?: string | null; name?: string | null; role?: string | null };
type SafetyRecord = {
  recordRef: string; recordType: string; domain: string; confidentiality: string; severity: string; status: string;
  title: string; summary: string; description?: string; premisesRef: string; patientRef?: string | null; episodeRef?: string | null;
  affectedStaffSubject?: string | null; affectedStaffName?: string | null; immediateRisk: boolean; safetyHoldRequested: boolean;
  operationalImpact: Record<string, unknown>; protectiveSummary?: string | null; accountableOwner: Owner; clinicalOwner: Owner;
  independentOwner: Owner; conflictSubjects: string[]; rootCause?: string | null; recurrenceControls: string[];
  dueAt?: string | null; version: number; updatedAt: string;
};
type SafetyAction = {
  actionRef: string; actionType: string; title: string; description: string; owner: Required<Owner>; status: string;
  dueAt?: string | null; completionEvidence?: string | null; requiresIndependentVerification: boolean;
  verificationStatus: string; verificationNote?: string | null; version: number;
};
type Blocker = { code: string; message: string };
type Bundle = { record: SafetyRecord; actions: SafetyAction[]; decisions: unknown[]; escalations: unknown[]; links: unknown[]; closureGate: { eligible: boolean; blockers: Blocker[]; actionCount: number } };
type Indicator = {
  recordRef: string; recordType: string; domain: string; confidentiality: string; severity: string; status: string;
  title: string; summary: string; patientRef?: string | null; episodeRef?: string | null; immediateRisk: boolean;
  safetyHoldRequested: boolean; ownerRole?: string | null; dueAt?: string | null; updatedAt: string;
};
type Contracts = { recordTypes: string[]; domains: string[]; confidentiality: string[]; severities: string[]; principles: string[] };

type Draft = {
  recordType: string; domain: string; confidentiality: string; severity: string; title: string; summary: string; description: string;
  premisesRef: string; patientRef: string; episodeRef: string; affectedStaffSubject: string; affectedStaffName: string;
  protectiveSummary: string; safetyHoldRequested: boolean; ownerSubject: string; ownerName: string; ownerRole: string;
};

const blankDraft: Draft = {
  recordType: "patient_safety", domain: "patient", confidentiality: "standard", severity: "amber", title: "", summary: "", description: "",
  premisesRef: "default-premises", patientRef: "", episodeRef: "", affectedStaffSubject: "", affectedStaffName: "",
  protectiveSummary: "", safetyHoldRequested: false, ownerSubject: "", ownerName: "", ownerRole: "clinical_director",
};

function words(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()); }
function dateTime(value?: string | null) { return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "Not set"; }
function border(severity: string) { return severity === "critical" || severity === "red" ? "#b91c1c" : severity === "amber" ? "#d97706" : "#047857"; }
const input = { width: "100%", padding: "10px 11px", border: "1px solid #cbd5e1", borderRadius: 9, background: "white", color: "#0f172a" } as const;
const button = { border: 0, borderRadius: 9, padding: "10px 13px", fontWeight: 850, cursor: "pointer" } as const;

export function CrossSystemSafetyControlV25() {
  const [contracts, setContracts] = useState<Contracts | null>(null);
  const [records, setRecords] = useState<SafetyRecord[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [selectedRef, setSelectedRef] = useState("");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [draft, setDraft] = useState<Draft>(blankDraft);
  const [actionType, setActionType] = useState("protective");
  const [actionTitle, setActionTitle] = useState("");
  const [actionDescription, setActionDescription] = useState("");
  const [actionOwnerSubject, setActionOwnerSubject] = useState("");
  const [actionOwnerName, setActionOwnerName] = useState("");
  const [actionOwnerRole, setActionOwnerRole] = useState("ops_manager");
  const [completionEvidence, setCompletionEvidence] = useState("");
  const [verificationNote, setVerificationNote] = useState("");
  const [managementReason, setManagementReason] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [recurrenceControls, setRecurrenceControls] = useState("");
  const [status, setStatus] = useState("Loading safety control");
  const [busy, setBusy] = useState("");

  const refreshList = useCallback(async () => {
    const [contractData, recordData, indicatorData] = await Promise.all([
      apiGet<Contracts>("/api/v25/safety/contracts"),
      apiGet<{ records: SafetyRecord[] }>("/api/v25/safety/records"),
      apiGet<{ indicators: Indicator[] }>("/api/v25/safety/board-indicators"),
    ]);
    setContracts(contractData);
    setRecords(recordData.records);
    setIndicators(indicatorData.indicators);
    setSelectedRef(current => current || recordData.records[0]?.recordRef || "");
  }, []);

  const refreshBundle = useCallback(async (ref: string) => {
    if (!ref) { setBundle(null); return; }
    setBundle(await apiGet<Bundle>(`/api/v25/safety/records/${encodeURIComponent(ref)}?reason=Safety%20control%20review`));
  }, []);

  useEffect(() => {
    refreshList().then(() => setStatus("Live authenticated safety state")).catch(error => setStatus(error instanceof Error ? error.message : "Safety control unavailable"));
  }, [refreshList]);
  useEffect(() => { void refreshBundle(selectedRef).catch(error => setStatus(error instanceof Error ? error.message : "Record unavailable")); }, [selectedRef, refreshBundle]);

  const counts = useMemo(() => ({
    open: indicators.length,
    red: indicators.filter(item => ["red", "critical"].includes(item.severity)).length,
    holds: indicators.filter(item => item.safetyHoldRequested).length,
    restricted: indicators.filter(item => item.confidentiality !== "standard").length,
  }), [indicators]);

  async function run(label: string, work: () => Promise<void>, ref = selectedRef) {
    try {
      setBusy(label); setStatus(`${words(label)} in progress`);
      await work(); await refreshList(); if (ref) await refreshBundle(ref);
      setStatus(`${words(label)} completed`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : `${words(label)} failed`);
    } finally { setBusy(""); }
  }

  async function createRecord() {
    if (draft.title.trim().length < 4 || draft.summary.trim().length < 8) { setStatus("Record a clear title and summary"); return; }
    let createdRef = "";
    await run("create safety record", async () => {
      const owners = draft.ownerSubject ? { accountable: { subject: draft.ownerSubject, name: draft.ownerName || draft.ownerSubject, role: draft.ownerRole } } : {};
      const response = await apiPost<Bundle & { created: boolean }>("/api/v25/safety/records", {
        recordType: draft.recordType, domain: draft.domain, confidentiality: draft.confidentiality, severity: draft.severity,
        title: draft.title, summary: draft.summary, description: draft.description, premisesRef: draft.premisesRef,
        patientRef: draft.patientRef || undefined, episodeRef: draft.episodeRef || undefined,
        affectedStaffSubject: draft.affectedStaffSubject || undefined, affectedStaffName: draft.affectedStaffName || undefined,
        protectiveSummary: draft.protectiveSummary || undefined, safetyHoldRequested: draft.safetyHoldRequested,
        immediateRisk: ["red", "critical"].includes(draft.severity), owners,
      });
      createdRef = response.record.recordRef; setSelectedRef(createdRef); setBundle(response); setDraft(blankDraft);
    }, createdRef);
    if (createdRef) await refreshBundle(createdRef);
  }

  async function createAction() {
    if (!bundle || actionTitle.trim().length < 4 || !actionOwnerSubject || !actionOwnerName) { setStatus("Action requires a title and named owner"); return; }
    await run("create safety action", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/actions`, {
        actionType, title: actionTitle, description: actionDescription,
        owner: { subject: actionOwnerSubject, name: actionOwnerName, role: actionOwnerRole },
      });
      setActionTitle(""); setActionDescription("");
    });
  }

  async function completeAction(action: SafetyAction) {
    if (completionEvidence.trim().length < 8) { setStatus("Completion evidence must explain what was done"); return; }
    await run("complete safety action", async () => {
      await apiJson(`/api/v25/safety/records/${encodeURIComponent(action.recordRef || bundle!.record.recordRef)}/actions/${encodeURIComponent(action.actionRef)}/complete`, {
        method: "PATCH", body: JSON.stringify({ expectedVersion: action.version, completionEvidence }),
      });
      setCompletionEvidence("");
    });
  }

  async function verifyAction(action: SafetyAction, decision: "verified" | "rejected") {
    if (verificationNote.trim().length < 8) { setStatus("Verification requires a clear note"); return; }
    await run(`${decision} safety action`, async () => {
      await apiJson(`/api/v25/safety/records/${encodeURIComponent(bundle!.record.recordRef)}/actions/${encodeURIComponent(action.actionRef)}/verify`, {
        method: "PATCH", body: JSON.stringify({ expectedVersion: action.version, decision, note: verificationNote }),
      });
      setVerificationNote("");
    });
  }

  async function escalate() {
    if (!bundle || managementReason.trim().length < 8) { setStatus("Record a clear escalation reason"); return; }
    await run("escalate safety record", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/escalations`, { reason: managementReason, to: { role: "governance_lead" } });
    });
  }

  async function reviewClosure() {
    if (!bundle || managementReason.trim().length < 8) { setStatus("Record an independent review reason"); return; }
    await run("approve closure review", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/closure-review`, { decision: "approved", reason: managementReason });
    });
  }

  async function closeRecord() {
    if (!bundle || managementReason.trim().length < 8) { setStatus("Record a closure reason"); return; }
    await run("close safety record", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/close`, {
        expectedVersion: bundle.record.version, rootCause,
        recurrenceControls: recurrenceControls.split("\n").map(value => value.trim()).filter(Boolean), reason: managementReason,
      });
    });
  }

  return <main style={{ minHeight: "100vh", background: "#e8edf3", color: "#0f172a", padding: 10, fontFamily: "Inter,system-ui,sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>LUCYWORKS SAFETY CONTROL · V25</span>
      <h1 style={{ margin: "7px 0", fontSize: "clamp(36px,8vw,72px)", lineHeight: .94 }}>Protect first. Name the owner. Prove the fix.</h1>
      <p style={{ color: "#b8c5d4", maxWidth: 950 }}>One route for patient incidents, staff welfare, conduct, complaints, safeguarding, operational failures and mixed events. Restricted staff detail remains restricted; the hospital board receives only the protective consequence.</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
        <Link href="/workspace" style={{ color: "white" }}>Patient Command</Link><Link href="/hospital-board" style={{ color: "white" }}>Hospital Today</Link><Link href="/system-control" style={{ color: "white" }}>System Control</Link>
      </div>
    </header>

    <section style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 8, marginTop: 8 }}>
      {[["Open", counts.open], ["Red / critical", counts.red], ["Safety holds", counts.holds], ["Restricted", counts.restricted]].map(([label, value]) => <article key={String(label)} style={{ background: "white", borderRadius: 13, padding: 12, border: "1px solid #cbd5e1" }}><small style={{ color: "#64748b", fontWeight: 850 }}>{label}</small><strong style={{ display: "block", fontSize: 28 }}>{value}</strong></article>)}
    </section>
    <p style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 10, padding: 10, fontWeight: 750 }}>{status}{busy ? ` · ${words(busy)}` : ""}</p>

    <section style={{ display: "grid", gridTemplateColumns: "minmax(280px,.85fr) minmax(0,1.6fr)", gap: 9 }}>
      <aside style={{ display: "grid", gap: 9, alignContent: "start" }}>
        <section style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 13 }}>
          <h2 style={{ marginTop: 0 }}>Report a concern</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
            <label>Type<select style={input} value={draft.recordType} onChange={event => setDraft({ ...draft, recordType: event.target.value })}>{(contracts?.recordTypes || []).map(value => <option key={value}>{value}</option>)}</select></label>
            <label>Domain<select style={input} value={draft.domain} onChange={event => setDraft({ ...draft, domain: event.target.value })}>{(contracts?.domains || []).map(value => <option key={value}>{value}</option>)}</select></label>
            <label>Severity<select style={input} value={draft.severity} onChange={event => setDraft({ ...draft, severity: event.target.value })}>{(contracts?.severities || []).map(value => <option key={value}>{value}</option>)}</select></label>
            <label>Privacy<select style={input} value={draft.confidentiality} onChange={event => setDraft({ ...draft, confidentiality: event.target.value })}>{(contracts?.confidentiality || []).map(value => <option key={value}>{value}</option>)}</select></label>
          </div>
          <label>Title<input style={input} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} /></label>
          <label>What happened<textarea style={{ ...input, minHeight: 78 }} value={draft.summary} onChange={event => setDraft({ ...draft, summary: event.target.value })} /></label>
          <label>Protective message for general boards<textarea style={{ ...input, minHeight: 58 }} value={draft.protectiveSummary} onChange={event => setDraft({ ...draft, protectiveSummary: event.target.value })} placeholder="Describe the operational protection without confidential HR detail" /></label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}><label>Patient ref<input style={input} value={draft.patientRef} onChange={event => setDraft({ ...draft, patientRef: event.target.value })} /></label><label>Episode ref<input style={input} value={draft.episodeRef} onChange={event => setDraft({ ...draft, episodeRef: event.target.value })} /></label></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}><label>Affected staff subject<input style={input} value={draft.affectedStaffSubject} onChange={event => setDraft({ ...draft, affectedStaffSubject: event.target.value })} /></label><label>Affected staff name<input style={input} value={draft.affectedStaffName} onChange={event => setDraft({ ...draft, affectedStaffName: event.target.value })} /></label></div>
          <label style={{ display: "flex", gap: 8, alignItems: "center", margin: "9px 0" }}><input type="checkbox" checked={draft.safetyHoldRequested} onChange={event => setDraft({ ...draft, safetyHoldRequested: event.target.checked })} /> Request immediate operational safety hold</label>
          <button disabled={!!busy} onClick={createRecord} style={{ ...button, width: "100%", background: "#0f766e", color: "white" }}>Create protected safety record</button>
        </section>

        <section style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 13 }}>
          <h2 style={{ marginTop: 0 }}>Open protective indicators</h2>
          <div style={{ display: "grid", gap: 6 }}>{indicators.map(item => <button key={item.recordRef} onClick={() => setSelectedRef(item.recordRef)} style={{ textAlign: "left", padding: 10, background: selectedRef === item.recordRef ? "#e0f2fe" : "#f8fafc", border: `1px solid ${border(item.severity)}`, borderLeftWidth: 6, borderRadius: 10, cursor: "pointer" }}><strong>{item.title}</strong><span style={{ display: "block", color: "#475569", marginTop: 3 }}>{item.summary}</span><small>{words(item.severity)} · {words(item.status)} · {item.ownerRole || "Unowned"}</small></button>)}</div>
        </section>
      </aside>

      <section style={{ display: "grid", gap: 9, alignContent: "start" }}>
        {!bundle ? <article style={{ background: "white", borderRadius: 15, padding: 20 }}>Select a visible record. Restricted matters are only returned to authorised parties.</article> : <>
          <article style={{ background: "white", border: `1px solid ${border(bundle.record.severity)}`, borderLeftWidth: 8, borderRadius: 15, padding: 15 }}>
            <small style={{ fontWeight: 900 }}>{words(bundle.record.recordType)} · {words(bundle.record.domain)} · {words(bundle.record.confidentiality)}</small>
            <h2 style={{ fontSize: 30, margin: "5px 0" }}>{bundle.record.title}</h2><p>{bundle.record.summary}</p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 7 }}>
              <b>State: {words(bundle.record.status)}</b><b>Severity: {words(bundle.record.severity)}</b><b>Patient: {bundle.record.patientRef || "Not linked"}</b><b>Episode: {bundle.record.episodeRef || "Not linked"}</b><b>Due: {dateTime(bundle.record.dueAt)}</b><b>Hold: {bundle.record.safetyHoldRequested ? "Requested" : "No"}</b>
            </div>
            <p style={{ background: "#f1f5f9", padding: 10, borderRadius: 9 }}><strong>Board-safe protection:</strong> {bundle.record.protectiveSummary || "No separate protective summary recorded"}</p>
            <p><strong>Owners:</strong> accountable {bundle.record.accountableOwner.name || "unassigned"}; clinical {bundle.record.clinicalOwner.name || "unassigned"}; independent {bundle.record.independentOwner.name || "unassigned"}.</p>
          </article>

          <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 13 }}>
            <h2 style={{ marginTop: 0 }}>Actions and verification</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 7 }}><label>Action type<select style={input} value={actionType} onChange={event => setActionType(event.target.value)}>{["protective","clinical_review","operational","communication","investigation","corrective","monitoring","welfare_support"].map(value => <option key={value}>{value}</option>)}</select></label><label>Owner subject<input style={input} value={actionOwnerSubject} onChange={event => setActionOwnerSubject(event.target.value)} /></label><label>Owner role<input style={input} value={actionOwnerRole} onChange={event => setActionOwnerRole(event.target.value)} /></label></div>
            <label>Owner name<input style={input} value={actionOwnerName} onChange={event => setActionOwnerName(event.target.value)} /></label><label>Action title<input style={input} value={actionTitle} onChange={event => setActionTitle(event.target.value)} /></label><label>Description<textarea style={{ ...input, minHeight: 56 }} value={actionDescription} onChange={event => setActionDescription(event.target.value)} /></label><button disabled={!!busy} onClick={createAction} style={{ ...button, background: "#1d4ed8", color: "white" }}>Assign action</button>
            <div style={{ display: "grid", gap: 7, marginTop: 10 }}>{bundle.actions.map(action => <section key={action.actionRef} style={{ padding: 10, border: "1px solid #cbd5e1", borderRadius: 10 }}><strong>{action.title}</strong><span style={{ display: "block" }}>{words(action.actionType)} · {action.owner.name} · {words(action.status)} · verification {words(action.verificationStatus)}</span>{action.status !== "completed" && <button onClick={() => completeAction(action)} style={{ ...button, marginTop: 6, background: "#0f766e", color: "white" }}>Complete with evidence below</button>}{action.status === "completed" && action.verificationStatus === "pending" && <span style={{ display: "flex", gap: 6, marginTop: 6 }}><button onClick={() => verifyAction(action, "verified")} style={{ ...button, background: "#047857", color: "white" }}>Verify</button><button onClick={() => verifyAction(action, "rejected")} style={{ ...button, background: "#b91c1c", color: "white" }}>Reject</button></span>}</section>)}</div>
            <label>Completion evidence<textarea style={{ ...input, minHeight: 56 }} value={completionEvidence} onChange={event => setCompletionEvidence(event.target.value)} /></label><label>Independent verification note<textarea style={{ ...input, minHeight: 56 }} value={verificationNote} onChange={event => setVerificationNote(event.target.value)} /></label>
          </article>

          <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 13 }}>
            <h2 style={{ marginTop: 0 }}>Escalation and closure</h2>
            <div style={{ background: bundle.closureGate.eligible ? "#ecfdf5" : "#fff7ed", padding: 10, borderRadius: 10 }}><strong>{bundle.closureGate.eligible ? "Closure gate clear" : "Closure blocked"}</strong>{bundle.closureGate.blockers.map(item => <div key={`${item.code}-${item.message}`}>{item.message}</div>)}</div>
            <label>Management / review reason<textarea style={{ ...input, minHeight: 60 }} value={managementReason} onChange={event => setManagementReason(event.target.value)} /></label><label>Root cause<textarea style={{ ...input, minHeight: 60 }} value={rootCause} onChange={event => setRootCause(event.target.value)} /></label><label>Recurrence controls — one per line<textarea style={{ ...input, minHeight: 72 }} value={recurrenceControls} onChange={event => setRecurrenceControls(event.target.value)} /></label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}><button onClick={escalate} style={{ ...button, background: "#b45309", color: "white" }}>Escalate</button><button onClick={reviewClosure} style={{ ...button, background: "#334155", color: "white" }}>Independent closure review</button><button onClick={closeRecord} style={{ ...button, background: "#047857", color: "white" }}>Close after all gates</button></div>
          </article>
        </>}
      </section>
    </section>

    <details style={{ marginTop: 10, background: "white", border: "1px solid #cbd5e1", borderRadius: 13, padding: 12 }}><summary style={{ fontWeight: 900, cursor: "pointer" }}>Safety boundaries</summary>{contracts?.principles.map(item => <p key={item}>{item}</p>)}</details>
  </main>;
}
