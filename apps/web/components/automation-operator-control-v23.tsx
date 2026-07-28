"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson, apiPost } from "@/lib/api";
import { localOperationalDate } from "@/lib/operational-date";

const PREMISES = "default-premises";
const SOURCE_TYPES = ["observation", "critical_result", "evidence_gap", "operational_delay"] as const;

type Mode = "disabled" | "preview_only" | "governed_commit";
type Configuration = {
  configRef?: string | null;
  premisesRef: string;
  mode: Mode;
  enabledTriggerTypes: string[];
  serviceSubject: string;
  serviceName: string;
  serviceRole: string;
  backgroundScanEnabled: boolean;
  scanIntervalSeconds: number;
  version: number;
  persisted: boolean;
};
type Validation = {
  valid: boolean;
  checks: Array<{ code: string; passed: boolean; detail: string }>;
  authorityBoundary: string;
  forbiddenEffects: string[];
};
type WorkItem = { id: number; title: string; description: string; ownerRole: string; urgency: string; status: string; dueAt?: string | null };
type Trigger = {
  triggerRef: string;
  episodeRef?: string | null;
  sourceType: string;
  sourceRef: string;
  sourceVersion?: number | null;
  sourceStateHash: string;
  mode: Mode;
  status: string;
  attempts: number;
  decisionOutcome?: string | null;
  workItems: WorkItem[];
  errorCode?: string | null;
  errorDetail?: string | null;
  createdAt?: string | null;
  processedAt?: string | null;
  initiatedBy: { name: string; role: string };
  sourceSnapshot: Record<string, unknown>;
};
type OperatorAction = { actionRef: string; actionType: string; reason: string; targetRef: string; createdAt?: string | null; actor: { name: string; role: string }; resultState: Record<string, unknown> };
type Control = {
  configuration: Configuration;
  serviceValidation: Validation;
  summary: { triggers: number; failed: number; queued: number; completed: number; previewed: number; skipped: number; workItems: number };
  recentActions: OperatorAction[];
  governedAcknowledgement: string;
};
type Overview = { summary: { count: number; failed: number; active: number; workItems: number }; triggers: Trigger[] };
type FormState = Omit<Configuration, "configRef" | "premisesRef" | "persisted" | "version">;

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function when(value?: string | null) {
  return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "Not recorded";
}

function tone(value: string) {
  const normal = value.toLowerCase();
  if (["failed", "red", "governed_commit"].includes(normal)) return "red";
  if (["previewed", "preview_only", "queued", "processing", "amber"].includes(normal)) return "amber";
  return "green";
}

export function AutomationOperatorControlV23() {
  const [control, setControl] = useState<Control | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [reason, setReason] = useState("");
  const [acknowledgement, setAcknowledgement] = useState("");
  const [episodeRef, setEpisodeRef] = useState("");
  const [operationalDate, setOperationalDate] = useState(() => localOperationalDate());
  const [status, setStatus] = useState("Loading automation authority");
  const [busy, setBusy] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState<Record<string, unknown> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [controlData, overviewData] = await Promise.all([
        apiGet<Control>(`/api/v23/automation/control/${PREMISES}`),
        apiGet<Overview>(`/api/v23/automation/overview?premises_ref=${PREMISES}&limit=500`),
      ]);
      setControl(controlData);
      setOverview(overviewData);
      setValidation(controlData.serviceValidation);
      setForm(current => current || {
        mode: controlData.configuration.mode,
        enabledTriggerTypes: controlData.configuration.enabledTriggerTypes,
        serviceSubject: controlData.configuration.serviceSubject,
        serviceName: controlData.configuration.serviceName,
        serviceRole: controlData.configuration.serviceRole,
        backgroundScanEnabled: controlData.configuration.backgroundScanEnabled,
        scanIntervalSeconds: controlData.configuration.scanIntervalSeconds,
      });
      setStatus(`Live · ${new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Automation control unavailable");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const failures = useMemo(() => (overview?.triggers || []).filter(item => item.status === "failed"), [overview]);
  const recent = overview?.triggers || [];

  function updateForm<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(current => current ? { ...current, [key]: value } : current);
  }

  function toggleSource(source: string) {
    if (!form) return;
    const next = form.enabledTriggerTypes.includes(source)
      ? form.enabledTriggerTypes.filter(value => value !== source)
      : [...form.enabledTriggerTypes, source];
    updateForm("enabledTriggerTypes", next);
  }

  async function validateService() {
    if (!form) return;
    setBusy("validate");
    try {
      const result = await apiPost<Validation>("/api/v23/automation/validate-service", {
        mode: form.mode,
        enabledTriggerTypes: form.enabledTriggerTypes,
        serviceSubject: form.serviceSubject,
        serviceName: form.serviceName,
        serviceRole: form.serviceRole,
      });
      setValidation(result);
      setStatus(result.valid ? "Service configuration passes LucyWorks authority checks" : "Service configuration has blocking checks");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Validation failed");
    } finally { setBusy(null); }
  }

  async function saveControl() {
    if (!form || !control) return;
    if (reason.trim().length < 8) { setStatus("Record a clear reason of at least eight characters"); return; }
    setBusy("save");
    try {
      const result = await apiJson<Control>(`/api/v23/automation/control/${PREMISES}`, {
        method: "PUT",
        body: JSON.stringify({
          ...form,
          expectedVersion: control.configuration.version,
          reason,
          acknowledgement: form.mode === "governed_commit" ? acknowledgement : undefined,
        }),
      });
      setControl(result);
      setValidation(result.serviceValidation);
      setForm({
        mode: result.configuration.mode,
        enabledTriggerTypes: result.configuration.enabledTriggerTypes,
        serviceSubject: result.configuration.serviceSubject,
        serviceName: result.configuration.serviceName,
        serviceRole: result.configuration.serviceRole,
        backgroundScanEnabled: result.configuration.backgroundScanEnabled,
        scanIntervalSeconds: result.configuration.scanIntervalSeconds,
      });
      setReason("");
      setAcknowledgement("");
      setStatus(`Saved ${label(result.configuration.mode)} mode with audited authority`);
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Configuration update failed");
    } finally { setBusy(null); }
  }

  async function reconcile() {
    if (reason.trim().length < 8) { setStatus("Record why this reconciliation scan is required"); return; }
    setBusy("reconcile");
    try {
      const result = await apiPost<{ count: number; failedCount: number; workItemCount: number }>("/api/v23/automation/reconcile", {
        premisesRef: PREMISES,
        operationalDate,
        episodeRef: episodeRef.trim() || undefined,
        sourceTypes: form?.enabledTriggerTypes || [...SOURCE_TYPES],
        reason,
      });
      setStatus(`Reconciled ${result.count} recorded sources · ${result.workItemCount} linked work items · ${result.failedCount} failed`);
      setReason("");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Reconciliation failed");
    } finally { setBusy(null); }
  }

  async function runDryRun() {
    if (!episodeRef.trim()) { setStatus("Enter a canonical episode reference for dry run"); return; }
    if (reason.trim().length < 8) { setStatus("Record why this dry run is required"); return; }
    setBusy("dry-run");
    try {
      const result = await apiPost<Record<string, unknown>>(`/api/v23/automation/episodes/${encodeURIComponent(episodeRef.trim())}/dry-run`, { reason });
      setDryRun(result);
      setStatus("Dry run completed without creating work");
      setReason("");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Dry run failed");
    } finally { setBusy(null); }
  }

  async function retry(trigger: Trigger) {
    if (reason.trim().length < 8) { setStatus("Record why this failed trigger is being retried"); return; }
    setBusy(trigger.triggerRef);
    try {
      const result = await apiPost<{ trigger: Trigger }>(`/api/v23/automation/triggers/${trigger.triggerRef}/retry`, { reason });
      setStatus(`Retry finished with ${label(result.trigger.status)} status`);
      setReason("");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Retry failed");
    } finally { setBusy(null); }
  }

  if (!control || !form || !overview) return <main className="ac loading"><style>{css}</style>{status}</main>;

  return <main className="ac"><style>{css}</style>
    <header className="hero"><div><span>LUCYWORKS OS · AUTOMATION CONTROL V23</span><h1>Automation authority</h1><p>Control what recorded hospital changes may propose, what may create owned work, and who remains responsible.</p></div><nav><Link href="/workspace">Patient command</Link><Link href="/hospital-board">Hospital today</Link><Link href="/system-control">All tools</Link></nav></header>
    <section className="statusbar"><strong aria-live="polite">{status}</strong><button onClick={() => void refresh()}>Refresh</button></section>
    <section className="kpis"><article className={tone(form.mode)}><b>{label(form.mode)}</b><small>current operating mode</small></article><article className={control.summary.failed ? "red" : "green"}><b>{control.summary.failed}</b><small>failed triggers</small></article><article className={control.summary.queued ? "amber" : "green"}><b>{control.summary.queued}</b><small>queued or processing</small></article><article><b>{control.summary.workItems}</b><small>accountable work items</small></article><article><b>v{control.configuration.version}</b><small>configuration version</small></article></section>
    <section className="boundary"><b>Authority boundary</b><span>LucyWorks may create review and coordination work. It does not diagnose, prescribe, administer, acknowledge results, complete evidence, reschedule care, admit, discharge or change a clinical phase.</span></section>
    <section className="panel modes"><div className="head"><div><span>1 · OPERATING MODE</span><h2>Choose the permitted effect</h2></div><small>Default remains disabled</small></div><div className="modegrid"><label className={form.mode === "disabled" ? "selected" : ""}><input type="radio" name="mode" checked={form.mode === "disabled"} onChange={() => updateForm("mode", "disabled")} /><b>Disabled</b><span>Record triggers as skipped. No decision and no work.</span></label><label className={form.mode === "preview_only" ? "selected" : ""}><input type="radio" name="mode" checked={form.mode === "preview_only"} onChange={() => updateForm("mode", "preview_only")} /><b>Preview only</b><span>Evaluate recorded facts and show proposals. Create no work.</span></label><label className={form.mode === "governed_commit" ? "selected danger" : "danger"}><input type="radio" name="mode" checked={form.mode === "governed_commit"} onChange={() => updateForm("mode", "governed_commit")} /><b>Governed commit</b><span>Create accountable human-owned review or coordination work only.</span></label></div></section>
    <section className="panel config"><div className="head"><div><span>2 · RECORDED SOURCES AND SERVICE IDENTITY</span><h2>Who may request evaluation</h2></div><button disabled={busy === "validate"} onClick={() => void validateService()}>Validate configuration</button></div><fieldset><legend>Recorded trigger types</legend><div className="checks">{SOURCE_TYPES.map(source => <label key={source}><input type="checkbox" checked={form.enabledTriggerTypes.includes(source)} onChange={() => toggleSource(source)} />{label(source)}</label>)}</div></fieldset><div className="fields"><label>Service subject<input value={form.serviceSubject} onChange={event => updateForm("serviceSubject", event.target.value)} /></label><label>Visible service name<input value={form.serviceName} onChange={event => updateForm("serviceName", event.target.value)} /></label><label>Mapped service role<select value={form.serviceRole} onChange={event => updateForm("serviceRole", event.target.value)}><option value="senior_clinician">Senior clinician</option><option value="clinical_director">Clinical director</option><option value="supervisor">Supervisor</option><option value="ops_manager">Operations manager</option><option value="governance_lead">Governance lead</option><option value="hospital_director">Hospital director</option><option value="admin">Administrator</option></select></label><label>Scan interval seconds<input type="number" min={30} max={3600} value={form.scanIntervalSeconds} onChange={event => updateForm("scanIntervalSeconds", Number(event.target.value))} /></label></div><label className="toggle"><input type="checkbox" checked={form.backgroundScanEnabled} onChange={event => updateForm("backgroundScanEnabled", event.target.checked)} />Enable scheduled reconciliation scan</label><div className={`validation ${validation?.valid ? "valid" : "invalid"}`}><header><b>{validation?.valid ? "Configuration checks pass" : "Configuration blocked"}</b><span>{validation?.authorityBoundary}</span></header>{validation?.checks.map(check => <div key={check.code}><strong>{check.passed ? "PASS" : "BLOCK"}</strong><span>{check.detail}</span></div>)}</div></section>
    <section className="panel authorise"><div className="head"><div><span>3 · AUTHORISE CHANGE</span><h2>Record why this control is changing</h2></div><small>Optimistic version {control.configuration.version}</small></div><label>Reason<textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Explain the operational or governance reason. This becomes immutable evidence." /></label>{form.mode === "governed_commit" ? <label className="ack">Typed acknowledgement<input value={acknowledgement} onChange={event => setAcknowledgement(event.target.value)} placeholder={control.governedAcknowledgement} /><small>Type exactly: {control.governedAcknowledgement}</small></label> : null}<button className="primary" disabled={busy === "save" || !validation?.valid} onClick={() => void saveControl()}>Save audited control</button></section>
    <section className="panel operations"><div className="head"><div><span>4 · DRY RUN AND RECONCILIATION</span><h2>Test or recover recorded state</h2></div><small>No browser-supplied clinical facts</small></div><div className="fields"><label>Operating date<input type="date" value={operationalDate} onChange={event => setOperationalDate(event.target.value)} /></label><label>Episode reference<input value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} placeholder="EP-..." /></label></div><div className="buttons"><button disabled={busy === "dry-run"} onClick={() => void runDryRun()}>Run episode dry run</button><button disabled={busy === "reconcile"} onClick={() => void reconcile()}>Reconcile recorded sources</button></div>{dryRun ? <pre>{JSON.stringify(dryRun, null, 2)}</pre> : null}</section>
    {failures.length ? <section className="panel failures"><div className="head"><div><span>FAILED TRIGGERS</span><h2>Visible recovery queue</h2></div><small>{failures.length}</small></div>{failures.map(trigger => <article key={trigger.triggerRef}><div><b>{label(trigger.sourceType)} · {trigger.sourceRef}</b><span>{trigger.errorCode || "Unknown failure"}</span><small>{trigger.errorDetail || "No failure detail recorded"}</small></div><button disabled={busy === trigger.triggerRef} onClick={() => void retry(trigger)}>Retry with reason</button></article>)}</section> : null}
    <section className="panel history"><div className="head"><div><span>RECORDED AUTOMATION HISTORY</span><h2>Source → decision → accountable work</h2></div><small>{recent.length} shown</small></div>{recent.length ? recent.map(trigger => <details key={trigger.triggerRef} className={tone(trigger.status)}><summary><span><b>{label(trigger.sourceType)}</b><small>{trigger.episodeRef || "No episode"} · {when(trigger.createdAt)}</small></span><strong>{label(trigger.status)}</strong></summary><div className="triggergrid"><div><dt>Source</dt><dd>{trigger.sourceRef}</dd></div><div><dt>Version / hash</dt><dd>{trigger.sourceVersion ?? "n/a"} · {trigger.sourceStateHash.slice(0, 12)}…</dd></div><div><dt>Mode</dt><dd>{label(trigger.mode)}</dd></div><div><dt>Initiated by</dt><dd>{trigger.initiatedBy.name} · {label(trigger.initiatedBy.role)}</dd></div><div><dt>Decision</dt><dd>{label(trigger.decisionOutcome || "none")}</dd></div><div><dt>Attempts</dt><dd>{trigger.attempts}</dd></div></div>{trigger.workItems.length ? <div className="work"><b>Generated accountable work</b>{trigger.workItems.map(item => <article key={item.id}><span>{item.title}</span><small>{label(item.ownerRole)} · {item.urgency.toUpperCase()} · {label(item.status)} · due {when(item.dueAt)}</small></article>)}</div> : <p>No work item was created from this recorded state.</p>}</details>) : <div className="empty">No automation triggers recorded for this premises.</div>}</section>
    <section className="panel actions"><div className="head"><div><span>OPERATOR EVIDENCE</span><h2>Recent control actions</h2></div><small>{control.recentActions.length}</small></div>{control.recentActions.map(action => <article key={action.actionRef}><b>{label(action.actionType)}</b><span>{action.reason}</span><small>{action.actor.name} · {label(action.actor.role)} · {when(action.createdAt)}</small></article>)}</section>
  </main>;
}

const css = `
.ac{min-height:100vh;background:#e9eef5;color:#0f172a;padding:8px;font-family:Inter,system-ui,sans-serif}.ac *{box-sizing:border-box}.loading{display:grid;place-items:center;background:#071019;color:white;font-weight:900}.hero{display:flex;justify-content:space-between;gap:16px;background:#071019;color:white;border-radius:18px;padding:18px}.hero span,.head>div>span{color:#2dd4bf;font-size:11px;font-weight:950;letter-spacing:.13em}.hero h1{font-size:clamp(38px,7vw,70px);line-height:.92;margin:6px 0}.hero p{margin:0;color:#b6c2d1;max-width:800px}.hero nav{display:flex;gap:7px;flex-wrap:wrap;align-content:flex-start}.hero a,.statusbar button,.panel button{border:1px solid #334155;border-radius:999px;background:#0f172a;color:white;padding:10px 13px;text-decoration:none;font-weight:900}.statusbar{display:flex;justify-content:space-between;align-items:center;gap:10px;background:white;border:1px solid #cbd5e1;border-radius:12px;padding:9px;margin:9px 0}.statusbar strong{color:#475569}.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.kpis article{background:white;border:1px solid #cbd5e1;border-top:5px solid #64748b;border-radius:11px;padding:10px}.kpis article.red{border-top-color:#dc2626}.kpis article.amber{border-top-color:#f59e0b}.kpis article.green{border-top-color:#16a34a}.kpis b{display:block;font-size:24px}.kpis small{color:#64748b}.boundary{display:flex;gap:10px;align-items:center;background:#fff7ed;border:1px solid #fb923c;border-radius:12px;padding:11px;margin-top:8px}.boundary b{white-space:nowrap}.boundary span{color:#7c2d12}.panel{background:white;border:1px solid #cbd5e1;border-radius:15px;padding:13px;margin-top:9px}.head{display:flex;justify-content:space-between;align-items:end;gap:10px}.head h2{font-size:30px;line-height:1;margin:4px 0}.head>small{color:#64748b;font-weight:850}.modegrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.modegrid label{display:grid;grid-template-columns:auto 1fr;gap:6px 9px;border:2px solid #cbd5e1;border-radius:12px;padding:12px;cursor:pointer}.modegrid label.selected{border-color:#0f766e;background:#f0fdfa}.modegrid label.danger.selected{border-color:#dc2626;background:#fff1f2}.modegrid label b{font-size:20px}.modegrid label span{grid-column:2;color:#475569}.fields{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}.panel label{display:grid;gap:4px;font-size:12px;font-weight:900;color:#475569}.panel input,.panel select,.panel textarea{min-height:44px;border:1px solid #94a3b8;border-radius:8px;padding:8px;font:inherit;background:white;color:#0f172a}.panel textarea{min-height:92px;resize:vertical}.panel fieldset{border:1px solid #cbd5e1;border-radius:10px;margin-top:10px}.checks{display:flex;gap:12px;flex-wrap:wrap}.checks label,.toggle{display:flex!important;align-items:center;gap:6px}.checks input,.toggle input,.modegrid input{min-height:auto}.toggle{margin-top:10px}.validation{display:grid;gap:5px;margin-top:10px;border:1px solid #fecaca;background:#fff1f2;border-radius:10px;padding:9px}.validation.valid{border-color:#86efac;background:#f0fdf4}.validation header{display:flex;justify-content:space-between;gap:8px}.validation header span{color:#475569}.validation>div{display:grid;grid-template-columns:58px 1fr;gap:8px}.validation>div strong{font-size:11px}.ack{margin-top:8px}.ack small{color:#991b1b}.primary{margin-top:9px;background:#0f766e!important;border-color:#0f766e!important}.buttons{display:flex;gap:8px;margin-top:10px}.operations pre{max-height:360px;overflow:auto;background:#071019;color:#dbeafe;border-radius:10px;padding:10px;font-size:11px}.failures article,.actions article{display:flex;justify-content:space-between;gap:10px;align-items:center;border:1px solid #fecaca;background:#fff1f2;border-radius:10px;padding:10px;margin-top:7px}.failures article div,.actions article{display:grid}.failures span,.failures small,.actions span,.actions small{color:#475569}.history details{border:1px solid #cbd5e1;border-left:6px solid #16a34a;border-radius:10px;padding:9px;margin-top:7px}.history details.red{border-left-color:#dc2626}.history details.amber{border-left-color:#f59e0b}.history summary{display:flex;justify-content:space-between;gap:10px;cursor:pointer}.history summary span{display:grid}.history summary small{color:#64748b}.triggergrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:9px}.triggergrid>div{background:#f8fafc;border-radius:7px;padding:7px}.triggergrid dt{font-size:10px;font-weight:950;color:#64748b;text-transform:uppercase}.triggergrid dd{margin:3px 0 0;font-weight:800;overflow-wrap:anywhere}.work{display:grid;gap:5px;margin-top:8px}.work article{display:grid;background:#eff6ff;border:1px solid #bfdbfe;border-radius:7px;padding:7px}.work small{color:#475569}.empty{padding:12px;color:#64748b}@media(max-width:900px){.hero{display:grid}.kpis{grid-template-columns:repeat(2,1fr)}.modegrid{grid-template-columns:1fr}.fields,.triggergrid{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.ac{padding:5px}.hero nav a{flex:1;text-align:center}.statusbar,.boundary,.head,.validation header,.failures article{display:grid}.fields,.triggergrid{grid-template-columns:1fr}.buttons{display:grid}.kpis{grid-template-columns:1fr 1fr}.history summary{align-items:start}}
`;
