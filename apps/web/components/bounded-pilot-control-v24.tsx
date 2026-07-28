"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";

export const pilotControlRoles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];

type Mode = "synthetic" | "shadow" | "bounded_live";
type Owner = { subject: string; name: string; role: string };
type Authority = {
  authorityRef: string; runRef: string; premisesRef: string; serviceLine: string; requestedMode: Mode; status: string;
  scope: Record<string, unknown>; successCriteria: Record<string, unknown>; stopCriteria: Record<string, unknown>;
  rollbackPlan: Record<string, unknown>; integrationScope: string[]; automationMode: string;
  accountableOwner: Owner; clinicalOwner?: Owner | null; planVersion: number; version: number;
  activatedAt?: string | null; stoppedAt?: string | null; rollbackAt?: string | null; completedAt?: string | null;
};
type Blocker = { code: string; detail: string; ownerRole: string; severity: string };
type Gate = {
  eligible: boolean; blockers: Blocker[]; warnings: Blocker[];
  automation: { mode: string; serviceName?: string; serviceRole?: string };
  authorisationAcknowledgement: string; approvalAcknowledgement: string; rollbackAcknowledgement: string;
  approvals: Record<string, Approval>; summary: { openObservations: number; openRedObservations: number; shadowComparisons: number; unresolvedRedComparisons: number; uatTotal: number; uatPassed: number; criticalUatRemaining: number };
};
type Approval = { approvalRef: string; approvalType: string; decision: string; reason: string; planVersion: number; actor: { name: string; role: string }; createdAt: string };
type UAT = { scenarioRef: string; scenarioCode: string; title: string; actorRole: string; workflow: string; expectedOutcome: string; critical: boolean; status: string; evidenceSummary?: string | null; version: number };
type Comparison = { comparisonRef: string; externalRef: string; canonicalEpisodeRef: string; sourceSystem: string; mismatchCodes: string[]; severity: string; status: string; reviewNote?: string | null; version: number };
type Observation = { observationRef: string; severity: string; category: string; summary: string; ownerRole: string; status: string; resolution?: string | null };
type Action = { actionRef: string; actionType: string; reason: string; previousStatus?: string | null; resultStatus?: string | null; actor: { name: string; role: string }; createdAt: string };
type Command = { authority: Authority; gate: Gate; approvals: Approval[]; uatScenarios: UAT[]; shadowComparisons: Comparison[]; observations: Observation[]; actions: Action[]; authorityBoundary: { permitted: string[]; forbidden: string[] } };
type Contracts = { supportedModes: Mode[]; approvalAcknowledgement: string; authorisationAcknowledgements: Record<Mode, string>; rollbackAcknowledgement: string; defaultPlan: { scope: Record<string, unknown>; successCriteria: Record<string, unknown>; stopCriteria: Record<string, unknown>; rollbackPlan: Record<string, unknown> } };
type PilotSummary = { authority: Authority; gate: Gate };

type Draft = {
  mode: Mode; premisesRef: string; serviceLine: string; workflows: string; maxPatients: number;
  accountableSubject: string; accountableName: string; accountableRole: string;
  clinicalSubject: string; clinicalName: string; clinicalRole: string;
  automationMode: string; integrations: string; rollbackOwner: string; recoveryPoint: string; rollbackSteps: string; communications: string;
};

const defaultDraft: Draft = {
  mode: "synthetic", premisesRef: "default-premises", serviceLine: "referral", workflows: "referral_intake, patient_command, hospital_today, care_brief", maxPatients: 5,
  accountableSubject: "", accountableName: "", accountableRole: "ops_manager", clinicalSubject: "", clinicalName: "", clinicalRole: "clinical_director",
  automationMode: "disabled", integrations: "", rollbackOwner: "", recoveryPoint: "Last verified existing-system state", rollbackSteps: "Stop LucyWorks pilot writes\nReturn to existing workflow\nReconcile patient, task and evidence state", communications: "Notify clinical lead, operations, governance and affected staff",
};

function words(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()); }
function dateTime(value?: string | null) { return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "Not recorded"; }
function tone(value: string) { const normal = value.toLowerCase(); if (["red", "failed", "blocked", "rollback", "stopped", "rejected"].includes(normal)) return "red"; if (["amber", "draft", "authorised", "shadow", "warning", "not_run"].includes(normal)) return "amber"; return "green"; }

export function BoundedPilotControlV24() {
  const [contracts, setContracts] = useState<Contracts | null>(null);
  const [pilots, setPilots] = useState<PilotSummary[]>([]);
  const [selectedRef, setSelectedRef] = useState("");
  const [command, setCommand] = useState<Command | null>(null);
  const [draft, setDraft] = useState<Draft>(defaultDraft);
  const [reason, setReason] = useState("");
  const [acknowledgement, setAcknowledgement] = useState("");
  const [approvalType, setApprovalType] = useState("operational");
  const [observationSeverity, setObservationSeverity] = useState("amber");
  const [observationSummary, setObservationSummary] = useState("");
  const [shadowJson, setShadowJson] = useState('[{"externalRef":"EXT-1","canonicalEpisodeRef":"EP-1","sourceSystem":"pims-shadow","externalSnapshot":{"patientRef":"PAT-1","phase":"referral_received","status":"active","ownerRole":"reception"}}]');
  const [status, setStatus] = useState("Loading pilot control");
  const [busy, setBusy] = useState("");

  const refreshList = useCallback(async () => {
    const [contractData, pilotData] = await Promise.all([
      apiGet<Contracts>("/api/v24/pilots/contracts"),
      apiGet<{ pilots: PilotSummary[] }>("/api/v24/pilots"),
    ]);
    setContracts(contractData);
    setPilots(pilotData.pilots);
    setSelectedRef(current => current || pilotData.pilots[0]?.authority.authorityRef || "");
  }, []);

  const refreshCommand = useCallback(async (ref: string) => {
    if (!ref) { setCommand(null); return; }
    setCommand(await apiGet<Command>(`/api/v24/pilots/${encodeURIComponent(ref)}`));
  }, []);

  useEffect(() => {
    refreshList().then(() => setStatus("Live pilot authority state")).catch(error => setStatus(error instanceof Error ? error.message : "Pilot control unavailable"));
  }, [refreshList]);
  useEffect(() => { void refreshCommand(selectedRef).catch(error => setStatus(error instanceof Error ? error.message : "Pilot unavailable")); }, [selectedRef, refreshCommand]);

  const approvalByType = useMemo(() => command?.gate.approvals || {}, [command]);

  async function run(label: string, work: () => Promise<unknown>, ref = selectedRef) {
    try {
      setBusy(label); setStatus(`${words(label)} in progress`);
      await work();
      await refreshList();
      if (ref) await refreshCommand(ref);
      setStatus(`${words(label)} completed`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : `${words(label)} failed`);
    } finally { setBusy(""); }
  }

  function planPayload() {
    return {
      requestedMode: draft.mode,
      premisesRef: draft.premisesRef,
      serviceLine: draft.serviceLine,
      scope: { includedWorkflows: draft.workflows.split(",").map(value => value.trim()).filter(Boolean), maxConcurrentPatients: draft.maxPatients, operatingWindow: "08:00-18:00" },
      successCriteria: { measures: { unresolvedRedObservations: 0, lostUpdates: 0, criticalWorkflowAccuracyPercent: 100, staffAgreementPercent: 95 } },
      stopCriteria: { decisionOwner: "Named pilot owner or any authorised safety lead", triggers: ["patient identity mismatch", "unresolved red safety observation", "data integrity failure", "critical integration outage", "named clinical owner requests stop"] },
      rollbackPlan: { owner: draft.rollbackOwner, steps: draft.rollbackSteps.split("\n").map(value => value.trim()).filter(Boolean), recoveryPoint: draft.recoveryPoint, communications: draft.communications },
      integrationScope: draft.integrations.split(",").map(value => value.trim()).filter(Boolean),
      automationMode: draft.automationMode,
      accountableOwner: { subject: draft.accountableSubject, name: draft.accountableName, role: draft.accountableRole },
      clinicalOwner: draft.clinicalSubject ? { subject: draft.clinicalSubject, name: draft.clinicalName, role: draft.clinicalRole } : undefined,
      reason,
    };
  }

  async function createPilot() {
    if (reason.trim().length < 8) { setStatus("Record a clear reason of at least eight characters"); return; }
    let newRef = "";
    await run("create pilot plan", async () => {
      const result = await apiPost<Command>("/api/v24/pilots", planPayload());
      newRef = result.authority.authorityRef;
      setSelectedRef(newRef); setCommand(result); setReason("");
    }, newRef);
  }

  async function updatePlan() {
    if (!command || reason.trim().length < 8) { setStatus("Select a pilot and record a reason"); return; }
    await run("update pilot plan", async () => {
      await apiJson(`/api/v24/pilots/${command.authority.authorityRef}`, { method: "PUT", body: JSON.stringify({ ...planPayload(), expectedVersion: command.authority.version }) });
      setReason("");
    });
  }

  async function approve() {
    if (!command || reason.trim().length < 8 || !contracts) { setStatus("Record the approval reason"); return; }
    await run(`${approvalType} approval`, () => apiPost(`/api/v24/pilots/${command.authority.authorityRef}/approvals`, { approvalType, decision: "approved", reason, acknowledgement: contracts.approvalAcknowledgement }));
    setReason("");
  }

  async function authorise() {
    if (!command || reason.trim().length < 8) { setStatus("Record the authorisation reason"); return; }
    await run("authorise pilot", () => apiPost(`/api/v24/pilots/${command.authority.authorityRef}/authorise`, { expectedVersion: command.authority.version, mode: command.authority.requestedMode, reason, acknowledgement }));
    setReason(""); setAcknowledgement("");
  }

  async function stateAction(action: "start" | "stop" | "complete" | "rollback") {
    if (!command || reason.trim().length < 8) { setStatus("Record why this action is required"); return; }
    const body: Record<string, unknown> = { reason };
    if (action !== "stop") body.expectedVersion = command.authority.version;
    if (action === "rollback") body.acknowledgement = acknowledgement;
    await run(action, () => apiPost(`/api/v24/pilots/${command.authority.authorityRef}/${action}`, body));
    setReason(""); setAcknowledgement("");
  }

  async function setUat(item: UAT, next: "passed" | "failed") {
    const evidenceSummary = window.prompt(`${next === "passed" ? "Evidence that this passed" : "Failure detail"}:`);
    if (!evidenceSummary || evidenceSummary.trim().length < 8) return;
    await run(`uat ${next}`, () => apiJson(`/api/v24/pilots/${selectedRef}/uat/${item.scenarioRef}`, { method: "PUT", body: JSON.stringify({ expectedVersion: item.version, status: next, evidenceSummary, reason: evidenceSummary }) }));
  }

  async function importShadow() {
    if (!command || reason.trim().length < 8) { setStatus("Record why this comparison import is required"); return; }
    let rows: unknown;
    try { rows = JSON.parse(shadowJson); } catch { setStatus("Shadow comparison JSON is invalid"); return; }
    if (!Array.isArray(rows)) { setStatus("Shadow comparison JSON must be an array"); return; }
    await run("import shadow comparisons", () => apiPost(`/api/v24/pilots/${command.authority.authorityRef}/shadow-comparisons`, { rows, reason }));
    setReason("");
  }

  async function reviewComparison(item: Comparison, decision: "approved" | "rejected") {
    const note = window.prompt(`${words(decision)} mismatch review note:`);
    if (!note || note.trim().length < 8) return;
    await run(`comparison ${decision}`, () => apiPost(`/api/v24/pilots/${selectedRef}/shadow-comparisons/${item.comparisonRef}/review`, { expectedVersion: item.version, decision, note }));
  }

  async function addObservation() {
    if (!command || observationSummary.trim().length < 8) { setStatus("Describe the pilot observation"); return; }
    await run("record observation", () => apiPost(`/api/v24/pilots/${command.authority.authorityRef}/observations`, { severity: observationSeverity, category: "workflow", summary: observationSummary, ownerRole: "ops_manager" }));
    setObservationSummary("");
  }

  async function resolveObservation(item: Observation) {
    const resolution = window.prompt("Resolution and verification:");
    if (!resolution || resolution.trim().length < 8) return;
    await run("resolve observation", () => apiJson(`/api/v24/pilots/${selectedRef}/observations/${item.observationRef}/resolve`, { method: "PATCH", body: JSON.stringify({ resolution }) }));
  }

  return <main className="pc"><style>{css}</style>
    <header className="hero"><div><span>LUCYWORKS OS · PILOT CONTROL V24</span><h1>Hospital pilot authority</h1><p>One governed route from synthetic proof to shadow comparison and a bounded live pilot, with named ownership, exact scope, visible blockers and immediate stop.</p></div><nav><Link href="/production-readiness">Readiness evidence</Link><Link href="/automation-control">Automation authority</Link><Link href="/system-control">All tools</Link></nav></header>
    <section className="status"><strong aria-live="polite">{status}</strong><button onClick={() => void refreshList().then(() => refreshCommand(selectedRef))}>Refresh</button></section>
    <section className="boundary"><b>Clinical boundary</b><span>LucyWorks may coordinate and evidence a bounded validation run. Named veterinary professionals retain diagnosis, treatment, prescribing, consent, acknowledgement, admission and discharge decisions.</span></section>

    <section className="layout">
      <aside className="panel list"><div className="head"><div><span>PILOT RUNS</span><h2>Choose authority</h2></div><b>{pilots.length}</b></div>{pilots.length ? pilots.map(item => <button key={item.authority.authorityRef} className={selectedRef === item.authority.authorityRef ? "selected" : ""} onClick={() => setSelectedRef(item.authority.authorityRef)}><span><b>{words(item.authority.requestedMode)}</b><small>{item.authority.serviceLine} · plan v{item.authority.planVersion}</small></span><strong className={tone(item.authority.status)}>{words(item.authority.status)}</strong></button>) : <p>No pilot authority exists.</p>}</aside>

      <section className="panel create"><div className="head"><div><span>PLAN</span><h2>Create or revise scope</h2></div><small>Changes invalidate earlier approvals</small></div>
        <div className="fields"><label>Mode<select value={draft.mode} onChange={event => setDraft({ ...draft, mode: event.target.value as Mode })}><option value="synthetic">Synthetic</option><option value="shadow">Shadow</option><option value="bounded_live">Bounded live</option></select></label><label>Premises reference<input value={draft.premisesRef} onChange={event => setDraft({ ...draft, premisesRef: event.target.value })} /></label><label>Service line<input value={draft.serviceLine} onChange={event => setDraft({ ...draft, serviceLine: event.target.value })} /></label><label>Maximum concurrent patients<input type="number" min={1} value={draft.maxPatients} onChange={event => setDraft({ ...draft, maxPatients: Number(event.target.value) })} /></label></div>
        <label>Included workflows<input value={draft.workflows} onChange={event => setDraft({ ...draft, workflows: event.target.value })} /></label>
        <div className="fields"><label>Accountable owner subject<input value={draft.accountableSubject} onChange={event => setDraft({ ...draft, accountableSubject: event.target.value })} /></label><label>Accountable owner name<input value={draft.accountableName} onChange={event => setDraft({ ...draft, accountableName: event.target.value })} /></label><label>Accountable owner role<input value={draft.accountableRole} onChange={event => setDraft({ ...draft, accountableRole: event.target.value })} /></label><label>Automation mode<select value={draft.automationMode} onChange={event => setDraft({ ...draft, automationMode: event.target.value })}><option value="disabled">Disabled</option><option value="preview_only">Preview only</option><option value="governed_commit">Governed commit</option></select></label></div>
        <div className="fields"><label>Clinical owner subject<input value={draft.clinicalSubject} onChange={event => setDraft({ ...draft, clinicalSubject: event.target.value })} /></label><label>Clinical owner name<input value={draft.clinicalName} onChange={event => setDraft({ ...draft, clinicalName: event.target.value })} /></label><label>Clinical owner role<input value={draft.clinicalRole} onChange={event => setDraft({ ...draft, clinicalRole: event.target.value })} /></label><label>Integration scope<input value={draft.integrations} onChange={event => setDraft({ ...draft, integrations: event.target.value })} /></label></div>
        <div className="fields"><label>Rollback owner<input value={draft.rollbackOwner} onChange={event => setDraft({ ...draft, rollbackOwner: event.target.value })} /></label><label>Recovery point<input value={draft.recoveryPoint} onChange={event => setDraft({ ...draft, recoveryPoint: event.target.value })} /></label><label>Rollback communications<input value={draft.communications} onChange={event => setDraft({ ...draft, communications: event.target.value })} /></label></div><label>Rollback steps<textarea value={draft.rollbackSteps} onChange={event => setDraft({ ...draft, rollbackSteps: event.target.value })} /></label>
        <label>Reason<textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Required for plan, approval, authorisation and recovery actions." /></label><div className="buttons"><button className="primary" disabled={Boolean(busy)} onClick={() => void createPilot()}>Create plan</button><button disabled={!command || Boolean(busy)} onClick={() => void updatePlan()}>Update selected plan</button></div>
      </section>
    </section>

    {command ? <>
      <section className="kpis"><article className={tone(command.authority.status)}><b>{words(command.authority.status)}</b><small>{words(command.authority.requestedMode)} · state v{command.authority.version}</small></article><article className={command.gate.eligible ? "green" : "red"}><b>{command.gate.eligible ? "Eligible" : "Blocked"}</b><small>{command.gate.blockers.length} blockers · {command.gate.warnings.length} warnings</small></article><article className={command.gate.summary.openRedObservations ? "red" : "green"}><b>{command.gate.summary.openRedObservations}</b><small>open red observations</small></article><article className={command.gate.summary.criticalUatRemaining ? "amber" : "green"}><b>{command.gate.summary.uatPassed}/{command.gate.summary.uatTotal}</b><small>UAT passed</small></article><article><b>{words(command.gate.automation.mode)}</b><small>site automation · plan {words(command.authority.automationMode)}</small></article></section>

      <section className="panel"><div className="head"><div><span>GO / NO-GO</span><h2>Current blockers</h2></div><small>Plan v{command.authority.planVersion}</small></div>{command.gate.blockers.length ? <div className="blockers">{command.gate.blockers.map(item => <article key={item.code} className={tone(item.severity)}><b>{words(item.code)}</b><span>{item.detail}</span><small>Owner: {words(item.ownerRole)}</small></article>)}</div> : <p className="clear">All current controls pass for this mode.</p>}{command.gate.warnings.map(item => <p key={item.code} className="warning"><b>{words(item.code)}:</b> {item.detail}</p>)}</section>

      <section className="panel approvals"><div className="head"><div><span>APPROVAL AND ACTIVATION</span><h2>Named authority</h2></div><small>Exact plan version only</small></div><div className="approvalgrid">{["clinical", "operational", "governance"].map(type => <article key={type} className={approvalByType[type]?.decision === "approved" ? "approved" : "missing"}><b>{words(type)}</b><span>{approvalByType[type] ? `${approvalByType[type].actor.name} · ${words(approvalByType[type].actor.role)}` : "Not approved for this plan"}</span></article>)}</div><div className="fields"><label>Approval type<select value={approvalType} onChange={event => setApprovalType(event.target.value)}><option value="clinical">Clinical</option><option value="operational">Operational</option><option value="governance">Governance</option></select></label><label>Typed acknowledgement<input value={acknowledgement} onChange={event => setAcknowledgement(event.target.value)} placeholder={command.gate.authorisationAcknowledgement} /></label></div><small>Approval phrase: {command.gate.approvalAcknowledgement}<br />Authorisation phrase: {command.gate.authorisationAcknowledgement}<br />Rollback phrase: {command.gate.rollbackAcknowledgement}</small><div className="buttons"><button onClick={() => void approve()}>Record approval</button><button className="primary" disabled={!command.gate.eligible} onClick={() => void authorise()}>Authorise mode</button><button onClick={() => void stateAction("start")}>Start</button><button className="danger" onClick={() => void stateAction("stop")}>STOP PILOT</button><button className="danger" onClick={() => void stateAction("rollback")}>Rollback</button><button onClick={() => void stateAction("complete")}>Complete</button></div></section>

      <section className="panel"><div className="head"><div><span>USER ACCEPTANCE</span><h2>Critical hospital journeys</h2></div><small>{command.gate.summary.criticalUatRemaining} critical remaining</small></div><div className="uat">{command.uatScenarios.map(item => <article key={item.scenarioRef} className={tone(item.status)}><header><b>{item.title}</b><strong>{words(item.status)}</strong></header><p>{item.workflow}</p><small>{words(item.actorRole)} · {item.expectedOutcome}</small><div className="buttons"><button onClick={() => void setUat(item, "passed")}>Pass with evidence</button><button className="danger" onClick={() => void setUat(item, "failed")}>Fail</button></div>{item.evidenceSummary ? <em>{item.evidenceSummary}</em> : null}</article>)}</div></section>

      <section className="panel"><div className="head"><div><span>SHADOW COMPARISON</span><h2>External state against canonical LucyWorks state</h2></div><small>{command.shadowComparisons.length}</small></div><label>Comparison JSON<textarea className="json" value={shadowJson} onChange={event => setShadowJson(event.target.value)} /></label><button onClick={() => void importShadow()}>Import and compare</button><div className="comparisons">{command.shadowComparisons.map(item => <article key={item.comparisonRef} className={tone(item.severity)}><header><b>{item.externalRef}</b><strong>{words(item.status)} · {item.severity.toUpperCase()}</strong></header><span>{item.canonicalEpisodeRef} · {item.sourceSystem}</span><p>{item.mismatchCodes.length ? item.mismatchCodes.map(words).join(" · ") : "Canonical match"}</p>{item.status === "mismatch" ? <div className="buttons"><button onClick={() => void reviewComparison(item, "approved")}>Accept explained difference</button><button className="danger" onClick={() => void reviewComparison(item, "rejected")}>Reject source state</button></div> : null}</article>)}</div></section>

      <section className="panel"><div className="head"><div><span>OBSERVATIONS AND SAFETY STOP</span><h2>Record what happened</h2></div><small>Red automatically stops</small></div><div className="fields"><label>Severity<select value={observationSeverity} onChange={event => setObservationSeverity(event.target.value)}><option value="green">Green</option><option value="amber">Amber</option><option value="red">Red</option></select></label><label>Observation<input value={observationSummary} onChange={event => setObservationSummary(event.target.value)} /></label></div><button onClick={() => void addObservation()}>Record observation</button><div className="observations">{command.observations.map(item => <article key={item.observationRef} className={tone(item.severity)}><b>{item.summary}</b><span>{item.severity.toUpperCase()} · {words(item.status)} · owner {words(item.ownerRole)}</span>{item.status !== "resolved" ? <button onClick={() => void resolveObservation(item)}>Resolve with evidence</button> : <small>{item.resolution}</small>}</article>)}</div></section>

      <section className="panel"><div className="head"><div><span>IMMUTABLE CONTROL HISTORY</span><h2>Plan, approval, stop and recovery evidence</h2></div><small>{command.actions.length}</small></div><div className="actions">{command.actions.map(item => <article key={item.actionRef}><b>{words(item.actionType)}</b><span>{item.reason}</span><small>{item.actor.name} · {words(item.actor.role)} · {dateTime(item.createdAt)} · {words(item.previousStatus || "none")} → {words(item.resultStatus || "none")}</small></article>)}</div></section>
    </> : <section className="panel empty">Create or select a pilot authority to open the command view.</section>}
  </main>;
}

const css = `
.pc{min-height:100vh;background:#e9eef5;color:#0f172a;padding:8px;font-family:Inter,system-ui,sans-serif}.pc *{box-sizing:border-box}.hero{display:flex;justify-content:space-between;gap:16px;background:#071019;color:white;border-radius:18px;padding:18px}.hero span,.head>div>span{color:#2dd4bf;font-size:11px;font-weight:950;letter-spacing:.13em}.hero h1{font-size:clamp(38px,7vw,72px);line-height:.92;margin:6px 0}.hero p{max-width:850px;color:#b6c2d1;margin:0}.hero nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.hero a,.status button,.panel button{background:#0f172a;color:white;border:1px solid #334155;border-radius:999px;padding:10px 13px;text-decoration:none;font-weight:900}.status{display:flex;justify-content:space-between;align-items:center;background:white;border:1px solid #cbd5e1;border-radius:11px;padding:9px;margin:8px 0}.boundary{display:flex;gap:10px;background:#fff7ed;border:1px solid #fb923c;border-radius:12px;padding:10px;color:#7c2d12}.boundary b{white-space:nowrap}.layout{display:grid;grid-template-columns:320px 1fr;gap:8px}.panel{background:white;border:1px solid #cbd5e1;border-radius:14px;padding:12px;margin-top:8px}.head{display:flex;justify-content:space-between;align-items:end;gap:9px}.head h2{font-size:28px;line-height:1;margin:4px 0}.head small{color:#64748b}.list button{width:100%;display:flex;justify-content:space-between;align-items:center;text-align:left;background:#f8fafc;color:#0f172a;border:1px solid #cbd5e1;border-radius:9px;margin-top:6px}.list button.selected{border:2px solid #0f766e;background:#f0fdfa}.list button span{display:grid}.list small{color:#64748b}.list strong,.approvals strong{padding:4px 7px;border-radius:999px;font-size:11px}.red{border-color:#dc2626!important}.amber{border-color:#f59e0b!important}.green{border-color:#16a34a!important}.list strong.red,.uat strong.red{background:#fee2e2;color:#991b1b}.list strong.amber,.uat strong.amber{background:#fef3c7;color:#92400e}.list strong.green,.uat strong.green{background:#dcfce7;color:#166534}.fields{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:8px}.panel label{display:grid;gap:4px;font-size:12px;font-weight:900;color:#475569;margin-top:8px}.panel input,.panel select,.panel textarea{min-height:43px;border:1px solid #94a3b8;border-radius:8px;padding:8px;font:inherit;background:white;color:#0f172a}.panel textarea{min-height:80px;resize:vertical}.panel textarea.json{min-height:150px;font-family:ui-monospace,monospace;font-size:12px}.buttons{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.panel button.primary{background:#0f766e;border-color:#0f766e}.panel button.danger{background:#b91c1c;border-color:#b91c1c}.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-top:8px}.kpis article{background:white;border:1px solid #cbd5e1;border-top:5px solid #64748b;border-radius:11px;padding:10px}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{display:block;font-size:22px}.kpis small{color:#64748b}.blockers,.uat,.comparisons,.observations,.actions{display:grid;gap:7px;margin-top:9px}.blockers{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}.blockers article,.uat article,.comparisons article,.observations article{border:1px solid #cbd5e1;border-left:6px solid #64748b;border-radius:9px;padding:9px;display:grid;gap:5px}.blockers article.red,.uat article.red,.comparisons article.red,.observations article.red{border-left-color:#dc2626!important}.blockers article.amber,.uat article.amber,.comparisons article.amber,.observations article.amber{border-left-color:#f59e0b!important}.blockers article.green,.uat article.green,.comparisons article.green,.observations article.green{border-left-color:#16a34a!important}.blockers span,.blockers small,.uat small,.comparisons span,.observations span,.actions small{color:#64748b}.clear{background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:10px;color:#166534}.warning{background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:8px}.approvalgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:9px}.approvalgrid article{display:grid;gap:5px;border:1px solid #cbd5e1;border-radius:9px;padding:9px}.approvalgrid .approved{border-color:#16a34a;background:#f0fdf4}.approvalgrid .missing{border-color:#f59e0b;background:#fffbeb}.uat{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}.uat header,.comparisons header{display:flex;justify-content:space-between;gap:8px}.uat em{font-size:12px;color:#166534}.observations article{grid-template-columns:1fr auto;align-items:center}.observations article span,.observations article small{grid-column:1}.actions article{display:grid;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px}.empty{text-align:center;color:#64748b;padding:30px}@media(max-width:980px){.layout{grid-template-columns:1fr}.fields{grid-template-columns:repeat(2,1fr)}.kpis{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.pc{padding:5px}.hero,.status,.boundary,.head{display:grid}.hero nav a{flex:1;text-align:center}.fields,.approvalgrid,.kpis{grid-template-columns:1fr}.buttons{display:grid}.buttons button{width:100%}.uat{grid-template-columns:1fr}.observations article{grid-template-columns:1fr}.observations article button{grid-column:1}.boundary b{white-space:normal}}
`;
