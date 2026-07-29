"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";

export const safetyControlRoles = [
  "admin",
  "clinician",
  "clinical_director",
  "governance_lead",
  "hospital_director",
  "nurse",
  "ops_manager",
  "senior_clinician",
  "supervisor",
];

type Owner = { subject?: string | null; name?: string | null; role?: string | null };
type SafetyRecord = {
  recordRef: string;
  recordType: string;
  domain: string;
  confidentiality: string;
  severity: string;
  status: string;
  title: string;
  summary: string;
  protectiveSummary?: string | null;
  patientRef?: string | null;
  episodeRef?: string | null;
  safetyHoldRequested: boolean;
  accountableOwner: Owner;
  clinicalOwner: Owner;
  independentOwner: Owner;
  rootCause?: string | null;
  recurrenceControls: string[];
  version: number;
};
type SafetyAction = {
  actionRef: string;
  actionType: string;
  title: string;
  description: string;
  owner: Owner;
  status: string;
  verificationStatus: string;
  version: number;
};
type Bundle = {
  record: SafetyRecord;
  actions: SafetyAction[];
  closureGate: { eligible: boolean; blockers: { code: string; message: string }[] };
};
type Indicator = {
  recordRef: string;
  title: string;
  summary: string;
  severity: string;
  status: string;
  confidentiality: string;
  safetyHoldRequested: boolean;
  ownerRole?: string | null;
};
type Contracts = {
  recordTypes: string[];
  domains: string[];
  confidentiality: string[];
  severities: string[];
  principles: string[];
};

type ReportDraft = {
  recordType: string;
  domain: string;
  confidentiality: string;
  severity: string;
  title: string;
  summary: string;
  protectiveSummary: string;
  patientRef: string;
  episodeRef: string;
  affectedStaffSubject: string;
  safetyHoldRequested: boolean;
};

type ActionDraft = {
  actionType: string;
  title: string;
  description: string;
  ownerSubject: string;
  ownerName: string;
  ownerRole: string;
};

const reportInitial: ReportDraft = {
  recordType: "patient_safety",
  domain: "patient",
  confidentiality: "standard",
  severity: "amber",
  title: "",
  summary: "",
  protectiveSummary: "",
  patientRef: "",
  episodeRef: "",
  affectedStaffSubject: "",
  safetyHoldRequested: false,
};

const actionInitial: ActionDraft = {
  actionType: "protective",
  title: "",
  description: "",
  ownerSubject: "",
  ownerName: "",
  ownerRole: "ops_manager",
};

const inputStyle = {
  width: "100%",
  padding: 10,
  border: "1px solid #cbd5e1",
  borderRadius: 9,
  background: "white",
  color: "#0f172a",
} as const;

const buttonStyle = {
  border: 0,
  borderRadius: 9,
  padding: "10px 13px",
  fontWeight: 850,
  cursor: "pointer",
} as const;

const ownerRoles = [
  "clinician",
  "clinical_director",
  "governance_lead",
  "hospital_director",
  "nurse",
  "ops_manager",
  "senior_clinician",
  "supervisor",
];

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function edge(value: string) {
  if (["red", "critical"].includes(value)) return "#b91c1c";
  if (value === "amber") return "#d97706";
  return "#047857";
}

function lines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

export function CrossSystemSafetyControlV25() {
  const [contracts, setContracts] = useState<Contracts | null>(null);
  const [records, setRecords] = useState<SafetyRecord[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [selectedRef, setSelectedRef] = useState("");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [reportDraft, setReportDraft] = useState<ReportDraft>(reportInitial);
  const [actionDraft, setActionDraft] = useState<ActionDraft>(actionInitial);
  const [completionEvidence, setCompletionEvidence] = useState("");
  const [managementReason, setManagementReason] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [recurrenceControls, setRecurrenceControls] = useState("");
  const [status, setStatus] = useState("Loading authenticated safety state");
  const [busy, setBusy] = useState(false);

  const refreshList = useCallback(async () => {
    const [contractData, recordData, indicatorData] = await Promise.all([
      apiGet<Contracts>("/api/v25/safety/contracts"),
      apiGet<{ records: SafetyRecord[] }>("/api/v25/safety/records"),
      apiGet<{ indicators: Indicator[] }>("/api/v25/safety/board-indicators"),
    ]);
    setContracts(contractData);
    setRecords(recordData.records);
    setIndicators(indicatorData.indicators);
    setSelectedRef((current) => current || recordData.records[0]?.recordRef || "");
  }, []);

  const refreshRecord = useCallback(async (recordRef: string) => {
    if (!recordRef) {
      setBundle(null);
      return;
    }
    const result = await apiGet<Bundle>(
      `/api/v25/safety/records/${encodeURIComponent(recordRef)}?reason=Safety%20command%20review`,
    );
    setBundle(result);
    setRootCause(result.record.rootCause || "");
    setRecurrenceControls((result.record.recurrenceControls || []).join("\n"));
  }, []);

  useEffect(() => {
    refreshList()
      .then(() => setStatus("Live safety state"))
      .catch((error) => setStatus(error instanceof Error ? error.message : "Safety control unavailable"));
  }, [refreshList]);

  useEffect(() => {
    void refreshRecord(selectedRef).catch((error) =>
      setStatus(error instanceof Error ? error.message : "Safety record unavailable"),
    );
  }, [refreshRecord, selectedRef]);

  const counts = useMemo(
    () => ({
      open: indicators.length,
      red: indicators.filter((item) => ["red", "critical"].includes(item.severity)).length,
      holds: indicators.filter((item) => item.safetyHoldRequested).length,
      restricted: indicators.filter((item) => item.confidentiality !== "standard").length,
    }),
    [indicators],
  );

  async function run(labelText: string, task: () => Promise<void>, recordRef = selectedRef) {
    try {
      setBusy(true);
      setStatus(`${labelText} in progress`);
      await task();
      await refreshList();
      if (recordRef) await refreshRecord(recordRef);
      setStatus(`${labelText} completed`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : `${labelText} failed`);
    } finally {
      setBusy(false);
    }
  }

  async function createRecord() {
    if (reportDraft.title.trim().length < 4 || reportDraft.summary.trim().length < 8) {
      setStatus("A clear title and summary are required");
      return;
    }
    let createdRef = "";
    await run("Safety report", async () => {
      const result = await apiPost<Bundle>("/api/v25/safety/records", {
        ...reportDraft,
        patientRef: reportDraft.patientRef || undefined,
        episodeRef: reportDraft.episodeRef || undefined,
        affectedStaffSubject: reportDraft.affectedStaffSubject || undefined,
        immediateRisk: ["red", "critical"].includes(reportDraft.severity),
      });
      createdRef = result.record.recordRef;
      setSelectedRef(createdRef);
      setBundle(result);
      setReportDraft(reportInitial);
    }, createdRef);
    if (createdRef) await refreshRecord(createdRef);
  }

  async function createAction() {
    if (!bundle || actionDraft.title.trim().length < 4 || !actionDraft.ownerSubject || !actionDraft.ownerName) {
      setStatus("Action title and a named owner are required");
      return;
    }
    await run("Safety action", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/actions`, {
        actionType: actionDraft.actionType,
        title: actionDraft.title,
        description: actionDraft.description,
        owner: {
          subject: actionDraft.ownerSubject,
          name: actionDraft.ownerName,
          role: actionDraft.ownerRole,
        },
      });
      setActionDraft(actionInitial);
    });
  }

  async function completeAction(action: SafetyAction) {
    if (completionEvidence.trim().length < 8) {
      setStatus("Completion evidence must explain what was done");
      return;
    }
    await run("Action completion", async () => {
      await apiJson(
        `/api/v25/safety/records/${encodeURIComponent(bundle!.record.recordRef)}/actions/${encodeURIComponent(action.actionRef)}/complete`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expectedVersion: action.version,
            completionEvidence,
          }),
        },
      );
      setCompletionEvidence("");
    });
  }

  async function verifyAction(action: SafetyAction, decision: "verified" | "rejected") {
    if (completionEvidence.trim().length < 8) {
      setStatus("Independent verification requires a clear note");
      return;
    }
    await run("Action verification", async () => {
      await apiJson(
        `/api/v25/safety/records/${encodeURIComponent(bundle!.record.recordRef)}/actions/${encodeURIComponent(action.actionRef)}/verify`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expectedVersion: action.version,
            decision,
            note: completionEvidence,
          }),
        },
      );
      setCompletionEvidence("");
    });
  }

  async function escalateRecord() {
    if (!bundle || managementReason.trim().length < 8) {
      setStatus("A clear escalation reason is required");
      return;
    }
    await run("Safety escalation", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/escalations`, {
        reason: managementReason,
        to: { role: "governance_lead" },
      });
    });
  }

  async function reviewClosure() {
    if (!bundle || managementReason.trim().length < 8) {
      setStatus("An independent review reason is required");
      return;
    }
    await run("Independent closure review", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/closure-review`, {
        decision: "approved",
        reason: managementReason,
        rootCause,
        recurrenceControls: lines(recurrenceControls),
      });
    });
  }

  async function closeRecord() {
    if (!bundle || managementReason.trim().length < 8) {
      setStatus("A closure reason is required");
      return;
    }
    await run("Safety record closure", async () => {
      await apiPost(`/api/v25/safety/records/${encodeURIComponent(bundle.record.recordRef)}/close`, {
        expectedVersion: bundle.record.version,
        rootCause,
        recurrenceControls: lines(recurrenceControls),
        reason: managementReason,
      });
    });
  }

  return (
    <main style={{ minHeight: "100vh", background: "#e8edf3", color: "#0f172a", padding: 10, fontFamily: "Inter,system-ui,sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
        <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>LUCYWORKS SAFETY CONTROL · V25</span>
        <h1 style={{ fontSize: "clamp(36px,8vw,70px)", lineHeight: 0.94, margin: "7px 0" }}>Protect first. Name the owner. Prove the fix.</h1>
        <p style={{ maxWidth: 950, color: "#b8c5d4" }}>One authenticated route for patient incidents, staff welfare, conduct, safeguarding, complaints and mixed operational events. General boards receive the protective consequence, not confidential HR detail.</p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link href="/workspace" style={{ color: "white" }}>Patient Command</Link>
          <Link href="/hospital-board" style={{ color: "white" }}>Hospital Today</Link>
          <Link href="/system-control" style={{ color: "white" }}>System Control</Link>
        </div>
      </header>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 8, marginTop: 8 }}>
        {Object.entries(counts).map(([name, value]) => (
          <article key={name} style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 12, padding: 11 }}>
            <small style={{ color: "#64748b", fontWeight: 850 }}>{label(name)}</small>
            <strong style={{ display: "block", fontSize: 28 }}>{value}</strong>
          </article>
        ))}
      </section>

      <p style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 10, padding: 10, fontWeight: 750 }}>{status}</p>

      <section style={{ display: "grid", gridTemplateColumns: "minmax(280px,.85fr) minmax(0,1.55fr)", gap: 9 }}>
        <aside style={{ display: "grid", gap: 9, alignContent: "start" }}>
          <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}>
            <h2 style={{ marginTop: 0 }}>Report concern</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
              <label>Type<select style={inputStyle} value={reportDraft.recordType} onChange={(event) => setReportDraft({ ...reportDraft, recordType: event.target.value })}>{contracts?.recordTypes.map((value) => <option key={value}>{value}</option>)}</select></label>
              <label>Domain<select style={inputStyle} value={reportDraft.domain} onChange={(event) => setReportDraft({ ...reportDraft, domain: event.target.value })}>{contracts?.domains.map((value) => <option key={value}>{value}</option>)}</select></label>
              <label>Severity<select style={inputStyle} value={reportDraft.severity} onChange={(event) => setReportDraft({ ...reportDraft, severity: event.target.value })}>{contracts?.severities.map((value) => <option key={value}>{value}</option>)}</select></label>
              <label>Privacy<select style={inputStyle} value={reportDraft.confidentiality} onChange={(event) => setReportDraft({ ...reportDraft, confidentiality: event.target.value })}>{contracts?.confidentiality.map((value) => <option key={value}>{value}</option>)}</select></label>
            </div>
            <label>Title<input style={inputStyle} value={reportDraft.title} onChange={(event) => setReportDraft({ ...reportDraft, title: event.target.value })} /></label>
            <label>What happened<textarea style={{ ...inputStyle, minHeight: 75 }} value={reportDraft.summary} onChange={(event) => setReportDraft({ ...reportDraft, summary: event.target.value })} /></label>
            <label>Board-safe protection<textarea style={{ ...inputStyle, minHeight: 55 }} value={reportDraft.protectiveSummary} onChange={(event) => setReportDraft({ ...reportDraft, protectiveSummary: event.target.value })} /></label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
              <label>Patient ref<input style={inputStyle} value={reportDraft.patientRef} onChange={(event) => setReportDraft({ ...reportDraft, patientRef: event.target.value })} /></label>
              <label>Episode ref<input style={inputStyle} value={reportDraft.episodeRef} onChange={(event) => setReportDraft({ ...reportDraft, episodeRef: event.target.value })} /></label>
            </div>
            <label>Affected staff subject<input style={inputStyle} value={reportDraft.affectedStaffSubject} onChange={(event) => setReportDraft({ ...reportDraft, affectedStaffSubject: event.target.value })} /></label>
            <label style={{ display: "flex", gap: 7, margin: "8px 0" }}><input type="checkbox" checked={reportDraft.safetyHoldRequested} onChange={(event) => setReportDraft({ ...reportDraft, safetyHoldRequested: event.target.checked })} />Request operational safety hold</label>
            <button disabled={busy} onClick={createRecord} style={{ ...buttonStyle, width: "100%", background: "#0f766e", color: "white" }}>Create protected record</button>
          </article>

          <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}>
            <h2 style={{ marginTop: 0 }}>Open indicators</h2>
            <div style={{ display: "grid", gap: 6 }}>
              {indicators.map((item) => (
                <button key={item.recordRef} onClick={() => setSelectedRef(item.recordRef)} style={{ textAlign: "left", padding: 9, border: `1px solid ${edge(item.severity)}`, borderLeftWidth: 6, borderRadius: 9, background: selectedRef === item.recordRef ? "#e0f2fe" : "#f8fafc", cursor: "pointer" }}>
                  <strong>{item.title}</strong>
                  <span style={{ display: "block", color: "#475569" }}>{item.summary}</span>
                  <small>{label(item.severity)} · {label(item.status)} · {item.ownerRole || "Unowned"}</small>
                </button>
              ))}
            </div>
          </article>
        </aside>

        <section style={{ display: "grid", gap: 9, alignContent: "start" }}>
          {!bundle ? (
            <article style={{ background: "white", borderRadius: 14, padding: 20 }}>Select a visible record.</article>
          ) : (
            <>
              <article style={{ background: "white", border: `1px solid ${edge(bundle.record.severity)}`, borderLeftWidth: 8, borderRadius: 14, padding: 14 }}>
                <small style={{ fontWeight: 900 }}>{label(bundle.record.recordType)} · {label(bundle.record.domain)} · {label(bundle.record.confidentiality)}</small>
                <h2 style={{ fontSize: 29, margin: "5px 0" }}>{bundle.record.title}</h2>
                <p>{bundle.record.summary}</p>
                <p style={{ background: "#f1f5f9", padding: 9, borderRadius: 8 }}><strong>Board-safe protection:</strong> {bundle.record.protectiveSummary || "Not separately recorded"}</p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 6 }}>
                  <b>{label(bundle.record.status)}</b>
                  <b>{label(bundle.record.severity)}</b>
                  <b>Patient: {bundle.record.patientRef || "None"}</b>
                  <b>Episode: {bundle.record.episodeRef || "None"}</b>
                  <b>Hold: {bundle.record.safetyHoldRequested ? "Requested" : "No"}</b>
                </div>
              </article>

              <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}>
                <h2 style={{ marginTop: 0 }}>Named actions</h2>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 7 }}>
                  <label>Type<select style={inputStyle} value={actionDraft.actionType} onChange={(event) => setActionDraft({ ...actionDraft, actionType: event.target.value })}>{["protective", "clinical_review", "operational", "communication", "investigation", "corrective", "monitoring", "welfare_support"].map((value) => <option key={value}>{value}</option>)}</select></label>
                  <label>Owner subject<input style={inputStyle} value={actionDraft.ownerSubject} onChange={(event) => setActionDraft({ ...actionDraft, ownerSubject: event.target.value })} /></label>
                  <label>Owner role<select style={inputStyle} value={actionDraft.ownerRole} onChange={(event) => setActionDraft({ ...actionDraft, ownerRole: event.target.value })}>{ownerRoles.map((value) => <option key={value}>{value}</option>)}</select></label>
                </div>
                <label>Owner name<input style={inputStyle} value={actionDraft.ownerName} onChange={(event) => setActionDraft({ ...actionDraft, ownerName: event.target.value })} /></label>
                <label>Action title<input style={inputStyle} value={actionDraft.title} onChange={(event) => setActionDraft({ ...actionDraft, title: event.target.value })} /></label>
                <label>Description<textarea style={{ ...inputStyle, minHeight: 52 }} value={actionDraft.description} onChange={(event) => setActionDraft({ ...actionDraft, description: event.target.value })} /></label>
                <button disabled={busy} onClick={createAction} style={{ ...buttonStyle, background: "#1d4ed8", color: "white" }}>Assign action</button>
                <div style={{ display: "grid", gap: 6, marginTop: 9 }}>
                  {bundle.actions.map((action) => (
                    <section key={action.actionRef} style={{ border: "1px solid #cbd5e1", borderRadius: 9, padding: 9 }}>
                      <strong>{action.title}</strong>
                      <span style={{ display: "block" }}>{label(action.actionType)} · {action.owner.name || action.owner.role} · {label(action.status)} · {label(action.verificationStatus)}</span>
                      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                        {action.status !== "completed" && <button onClick={() => completeAction(action)} style={{ ...buttonStyle, background: "#0f766e", color: "white" }}>Complete</button>}
                        {action.status === "completed" && action.verificationStatus === "pending" && (
                          <>
                            <button onClick={() => verifyAction(action, "verified")} style={{ ...buttonStyle, background: "#047857", color: "white" }}>Verify</button>
                            <button onClick={() => verifyAction(action, "rejected")} style={{ ...buttonStyle, background: "#b91c1c", color: "white" }}>Reject</button>
                          </>
                        )}
                      </div>
                    </section>
                  ))}
                </div>
                <label>Completion / verification evidence<textarea style={{ ...inputStyle, minHeight: 58 }} value={completionEvidence} onChange={(event) => setCompletionEvidence(event.target.value)} /></label>
              </article>

              <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 13 }}>
                <h2 style={{ marginTop: 0 }}>Investigation, escalation and closure</h2>
                <div style={{ background: bundle.closureGate.eligible ? "#ecfdf5" : "#fff7ed", padding: 9, borderRadius: 9 }}>
                  <strong>{bundle.closureGate.eligible ? "Closure gate clear" : "Closure blocked"}</strong>
                  {bundle.closureGate.blockers.map((item) => <div key={`${item.code}-${item.message}`}>{item.message}</div>)}
                </div>
                <label>Reason<textarea style={{ ...inputStyle, minHeight: 52 }} value={managementReason} onChange={(event) => setManagementReason(event.target.value)} /></label>
                <label>Root cause reviewed<textarea style={{ ...inputStyle, minHeight: 52 }} value={rootCause} onChange={(event) => setRootCause(event.target.value)} /></label>
                <label>Recurrence controls reviewed — one per line<textarea style={{ ...inputStyle, minHeight: 62 }} value={recurrenceControls} onChange={(event) => setRecurrenceControls(event.target.value)} /></label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  <button disabled={busy} onClick={escalateRecord} style={{ ...buttonStyle, background: "#b45309", color: "white" }}>Escalate</button>
                  <button disabled={busy} onClick={reviewClosure} style={{ ...buttonStyle, background: "#334155", color: "white" }}>Independent review of these findings</button>
                  <button disabled={busy} onClick={closeRecord} style={{ ...buttonStyle, background: "#047857", color: "white" }}>Close after gates</button>
                </div>
              </article>
            </>
          )}
        </section>
      </section>

      <details style={{ marginTop: 9, background: "white", border: "1px solid #cbd5e1", borderRadius: 12, padding: 11 }}>
        <summary style={{ cursor: "pointer", fontWeight: 900 }}>Authority boundary</summary>
        {contracts?.principles.map((item) => <p key={item}>{item}</p>)}
      </details>
    </main>
  );
}
