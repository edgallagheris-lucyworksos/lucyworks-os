"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { apiGet, apiJson } from "@/lib/api-client";

type Dashboard = {
  summary: Record<string, number>;
  medicationOrders: any[];
  administrations: any[];
  anaesthesia: any[];
  observations: any[];
  tasks: any[];
  diagnostics: any[];
  dischargePlans: any[];
  inventory: any[];
  inventoryMovements: any[];
  controlledDrugEntries: any[];
};
type Tab = "control" | "medications" | "anaesthesia" | "inpatient" | "diagnostics" | "pharmacy" | "discharge";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 14, boxShadow: "0 5px 16px rgba(15,23,42,.05)", minWidth: 0 };
const field: React.CSSProperties = { width: "100%", minHeight: 46, border: "1px solid #94a3b8", borderRadius: 8, padding: "9px 10px", fontSize: 16, background: "white", color: "#0f172a", boxSizing: "border-box" };
const button: React.CSSProperties = { border: 0, borderRadius: 8, padding: "10px 12px", minHeight: 46, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };
const grid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,320px),1fr))", gap: 9 };

function localDateTimeInput() {
  const value = new Date();
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export default function ClinicalExecutionPage() {
  return <AuthGuard allowedRoles={["clinician", "clinical_director", "nurse", "senior_clinician", "supervisor"]}><Workspace /></AuthGuard>;
}

function Workspace() {
  const [episodeRef, setEpisodeRef] = useState("");
  const [data, setData] = useState<Dashboard | null>(null);
  const [tab, setTab] = useState<Tab>("control");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("episode");
    if (initial) setEpisodeRef(initial);
  }, []);

  const load = useCallback(async () => {
    try {
      const query = episodeRef.trim() ? `?episode_ref=${encodeURIComponent(episodeRef.trim())}` : "";
      setData(await apiGet<Dashboard>(`/api/clinical-execution/governed/dashboard${query}`));
      if (episodeRef.trim()) window.history.replaceState(null, "", `/clinical-execution?episode=${encodeURIComponent(episodeRef.trim())}`);
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load clinical execution"); }
  }, [episodeRef]);
  useEffect(() => { void load(); }, [load]);

  async function act(path: string, body: unknown, success: string, method = "POST") {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(path, { method, body: JSON.stringify(body) });
      setMessage(success);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Clinical action failed"); }
    finally { setBusy(false); }
  }

  const tabs: Array<[Tab, string]> = [["control", "Control"], ["medications", "Medications"], ["anaesthesia", "Anaesthesia"], ["inpatient", "Inpatient"], ["diagnostics", "Lab & imaging"], ["pharmacy", "Pharmacy"], ["discharge", "Discharge"]];
  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 17, padding: 17 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".12em" }}>GOVERNED CLINICAL EXECUTION</span><h1 style={{ margin: "5px 0", fontSize: "clamp(34px,7vw,66px)", lineHeight: .95 }}>Patient work</h1></div><div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}><Link href={episodeRef ? `/care?episode=${encodeURIComponent(episodeRef)}` : "/workspace"} style={{ color: "white" }}>Care brief</Link><Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"} style={{ color: "white" }}>Patient record</Link><Link href={episodeRef ? `/episode-command?episode=${encodeURIComponent(episodeRef)}` : "/episode-command"} style={{ color: "white" }}>Episode decisions</Link><Link href="/patient-record/controlled-actions" style={{ color: "white" }}>Controlled actions</Link></div></div>
      <p style={{ color: "#94a3b8", maxWidth: 900 }}>Clinical identity is derived from the secure session. Prescribing requires a recorded v8 medication-safety review. High-risk administrations require witnesses, escalations remain open until resolved, stock changes have a ledger and discharge communications require evidence references.</p>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><input aria-label="Episode reference" placeholder="Canonical episode reference" value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} style={{ ...field, maxWidth: 330 }} /><button style={button} onClick={() => void load()}>Load</button></div>
    </header>
    <nav aria-label="Clinical execution sections" style={{ display: "flex", gap: 7, overflowX: "auto", padding: "10px 0" }}>{tabs.map(([key, label]) => <button key={key} onClick={() => setTab(key)} style={{ ...button, flex: "0 0 auto", background: tab === key ? "#0f766e" : "#334155" }}>{label}</button>)}</nav>
    {error && <div aria-live="assertive" style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginBottom: 9 }}>{error}</div>}
    {message && <div aria-live="polite" style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 9 }}>{message}</div>}
    {!data ? <section style={panel}>Loading…</section> : <>
      {tab === "control" && <Control data={data} />}
      {tab === "medications" && <Medications data={data} busy={busy} act={act} />}
      {tab === "anaesthesia" && <Anaesthesia data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "inpatient" && <Inpatient data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "diagnostics" && <Diagnostics data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "pharmacy" && <Pharmacy data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "discharge" && <Discharge data={data} episodeRef={episodeRef} busy={busy} act={act} />}
    </>}
  </main>;
}

function Control({ data }: { data: Dashboard }) {
  return <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 8 }}>{Object.entries(data.summary).map(([label, value]) => <div key={label} style={{ ...panel, borderColor: value ? "#f59e0b" : "#86efac" }}><small style={{ color: "#64748b", textTransform: "uppercase", fontWeight: 800 }}>{label.replace(/([A-Z])/g, " $1")}</small><div style={{ fontSize: 32, fontWeight: 950 }}>{value}</div></div>)}</section>;
}

function Medications({ data, busy, act }: any) {
  const [entry, setEntry] = useState({ reason: "", dose: "", witness: "" });
  async function administration(row: any, status: string) {
    const reason = entry.reason.trim();
    if (!reason) return;
    if (status === "administered" && !entry.dose.trim()) return;
    await act(`/api/clinical-execution/administrations/${row.administrationRef}`, { expected_version: row.version, status, dose_given: status === "administered" ? entry.dose.trim() : null, witness_subject: status === "administered" ? entry.witness.trim() || null : null, omission_reason: status === "administered" ? null : reason, reason }, `Administration ${status}.`, "PATCH");
    setEntry({ reason: "", dose: "", witness: "" });
  }
  return <div style={{ display: "grid", gap: 9 }}>
    <section style={{ ...panel, borderColor: "#38bdf8", display: "grid", gap: 8 }}>
      <h2 style={{ margin: 0 }}>Prescribing moved to reviewed controls</h2>
      <p style={{ margin: 0, color: "#475569" }}>Direct medication ordering is retired. Record weight and allergies, complete the safety review, then issue a reviewed prescription through Controlled actions.</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Link href="/patient-record" style={{ ...button, textDecoration: "none", display: "inline-flex", alignItems: "center" }}>Run medication safety review</Link><Link href="/patient-record/controlled-actions" style={{ ...button, background: "#2563eb", textDecoration: "none", display: "inline-flex", alignItems: "center" }}>Issue reviewed prescription</Link></div>
    </section>
    <section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Administration evidence</h2><textarea placeholder="Reason, omission explanation or clinical note" value={entry.reason} onChange={event => setEntry({ ...entry, reason: event.target.value })} style={{ ...field, minHeight: 78 }} /><input placeholder="Dose actually given" value={entry.dose} onChange={event => setEntry({ ...entry, dose: event.target.value })} style={field} /><input placeholder="Witness identity or reference, where required" value={entry.witness} onChange={event => setEntry({ ...entry, witness: event.target.value })} style={field} /></section>
    <section style={{ display: "grid", gap: 8 }}><h2>Administrations</h2>{data.administrations.length ? data.administrations.map((row: any) => <article key={row.administrationRef} style={{ ...panel, borderColor: row.status === "due" && new Date(row.scheduledAt) < new Date() ? "#ef4444" : "#cbd5e1" }}><strong>{row.orderRef}</strong><p>{new Date(row.scheduledAt).toLocaleString()} · {row.status}</p><div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><button disabled={busy || row.status !== "due" || !entry.reason.trim() || !entry.dose.trim()} style={button} onClick={() => void administration(row, "administered")}>Administer</button><button disabled={busy || row.status !== "due" || !entry.reason.trim()} style={{ ...button, background: "#a16207" }} onClick={() => void administration(row, "omitted")}>Omit</button><button disabled={busy || row.status !== "due" || !entry.reason.trim()} style={{ ...button, background: "#475569" }} onClick={() => void administration(row, "withheld")}>Withhold</button></div></article>) : <article style={panel}>No scheduled administrations for the selected scope.</article>}</section>
  </div>;
}

function Anaesthesia({ data, episodeRef, busy, act }: any) {
  const [blockRef, setBlockRef] = useState("");
  async function create() { await act("/api/clinical-execution/governed/anaesthesia", { episode_ref: episodeRef, block_ref: blockRef || null, reason: "Anaesthesia plan created by verified clinician" }, "Governed anaesthesia record created."); }
  async function transition(row: any, status: string) { const checklist = status === "induced" ? { identity_checked: true, consent_checked: true, equipment_checked: true, airway_plan_confirmed: true } : row.checklist; await act(`/api/clinical-execution/anaesthesia/${row.recordRef}`, { expected_version: row.version, status, checklist, reason: `${status} recorded by verified operator` }, `Anaesthesia ${status}.`, "PATCH"); }
  return <div style={{ display: "grid", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Legacy execution record</h2><p style={{ margin: 0, color: "#475569" }}>Detailed physiological charting and governed stage transitions are available in the longitudinal patient record. This panel remains for existing anaesthesia execution records.</p><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Link href="/patient-record" style={{ ...button, textDecoration: "none", display: "inline-flex", alignItems: "center" }}>Open detailed anaesthesia chart</Link><Link href="/patient-record/controlled-actions" style={{ ...button, background: "#2563eb", textDecoration: "none", display: "inline-flex", alignItems: "center" }}>Apply detailed transition</Link></div><input placeholder="Operational block reference" style={field} value={blockRef} onChange={e => setBlockRef(e.target.value)} /><button disabled={busy || !episodeRef} style={button} onClick={() => void create()}>Create compatible execution record</button></section>{data.anaesthesia.map((row: any) => <article key={row.recordRef} style={panel}><strong>{row.recordRef}</strong><p>{row.status} · responsible clinician: {row.responsibleClinicianName}</p><div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><button disabled={busy || row.status !== "planned"} style={button} onClick={() => void transition(row, "induced")}>Complete checklist and induce</button><button disabled={busy || row.status !== "induced"} style={{ ...button, background: "#2563eb" }} onClick={() => void transition(row, "recovered")}>Record recovery</button></div></article>)}</div>;
}

function Inpatient({ data, episodeRef, busy, act }: any) {
  const [obs, setObs] = useState({ type: "ward_observation", concern: "green", temperature: "", heartRate: "", respiratoryRate: "", notes: "" });
  const [task, setTask] = useState({ title: "", instructions: "", due: localDateTimeInput(), role: "nurse" });
  const [escalationNote, setEscalationNote] = useState("");
  async function addObservation() {
    const values: Record<string, string | number> = {};
    if (obs.temperature) values.temperature = Number(obs.temperature);
    if (obs.heartRate) values.heart_rate = Number(obs.heartRate);
    if (obs.respiratoryRate) values.respiratory_rate = Number(obs.respiratoryRate);
    if (obs.notes.trim()) values.notes = obs.notes.trim();
    await act("/api/clinical-execution/observations", { episode_ref: episodeRef, observation_type: obs.type, values, concern_level: obs.concern }, "Observation recorded.");
    setObs({ type: "ward_observation", concern: "green", temperature: "", heartRate: "", respiratoryRate: "", notes: "" });
  }
  async function escalation(row: any, status: string) {
    const note = escalationNote.trim();
    if (!note) return;
    await act(`/api/clinical-execution/governed/observations/${row.observationRef}/escalation`, { expected_version: row.version, status, note, escalated_to_role: status === "escalated" ? "clinician" : null }, `Observation escalation ${status}.`, "PATCH");
    setEscalationNote("");
  }
  async function addTask() { await act("/api/clinical-execution/treatment-tasks", { episode_ref: episodeRef, task_type: "treatment", title: task.title, instructions: task.instructions, due_at: new Date(task.due).toISOString(), assigned_role: task.role, priority: "amber" }, "Treatment task created."); }
  async function complete(row: any) { await act(`/api/clinical-execution/treatment-tasks/${row.taskRef}/complete`, { expected_version: row.version, reason: "Treatment completed and checked" }, "Treatment task completed.", "PATCH"); }
  return <div style={grid}>
    <section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Observation</h2><input aria-label="Observation type" style={field} value={obs.type} onChange={event => setObs({ ...obs, type: event.target.value })} /><select aria-label="Concern level" style={field} value={obs.concern} onChange={event => setObs({ ...obs, concern: event.target.value })}><option>green</option><option>amber</option><option>red</option></select><input type="number" step="0.1" placeholder="Temperature °C" style={field} value={obs.temperature} onChange={event => setObs({ ...obs, temperature: event.target.value })} /><input type="number" placeholder="Heart rate per minute" style={field} value={obs.heartRate} onChange={event => setObs({ ...obs, heartRate: event.target.value })} /><input type="number" placeholder="Respiratory rate per minute" style={field} value={obs.respiratoryRate} onChange={event => setObs({ ...obs, respiratoryRate: event.target.value })} /><textarea placeholder="Clinical observation notes" style={{ ...field, minHeight: 88 }} value={obs.notes} onChange={event => setObs({ ...obs, notes: event.target.value })} /><button disabled={busy || !episodeRef} style={button} onClick={() => void addObservation()}>Record observation</button></section>
    <section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Treatment task</h2><input placeholder="Task" style={field} value={task.title} onChange={event => setTask({ ...task, title: event.target.value })} /><textarea placeholder="Instructions" style={{ ...field, minHeight: 75 }} value={task.instructions} onChange={event => setTask({ ...task, instructions: event.target.value })} /><input type="datetime-local" style={field} value={task.due} onChange={event => setTask({ ...task, due: event.target.value })} /><button disabled={busy || !episodeRef || !task.title} style={button} onClick={() => void addTask()}>Create task</button></section>
    <section style={{ gridColumn: "1 / -1", display: "grid", gap: 8 }}><h2>Open observations and tasks</h2><textarea placeholder="Acknowledgement, escalation or resolution note" style={{ ...field, minHeight: 72 }} value={escalationNote} onChange={event => setEscalationNote(event.target.value)} />{data.observations.map((row: any) => <article key={row.observationRef} style={{ ...panel, borderColor: row.concernLevel === "red" ? "#ef4444" : "#cbd5e1" }}><strong>{row.type} · {row.concernLevel}</strong><p>Escalation: {row.escalationStatus}</p><div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><button disabled={busy || row.escalationStatus === "resolved" || !escalationNote.trim()} style={button} onClick={() => void escalation(row, "acknowledged")}>Acknowledge</button><button disabled={busy || row.escalationStatus === "resolved" || !escalationNote.trim()} style={{ ...button, background: "#a16207" }} onClick={() => void escalation(row, "escalated")}>Escalate</button><button disabled={busy || row.escalationStatus === "resolved" || !escalationNote.trim()} style={{ ...button, background: "#2563eb" }} onClick={() => void escalation(row, "resolved")}>Resolve</button></div></article>)}{data.tasks.map((row: any) => <article key={row.taskRef} style={panel}><strong>{row.title}</strong><p>{row.status} · due {new Date(row.dueAt).toLocaleString()}</p><button disabled={busy || row.status === "completed"} style={button} onClick={() => void complete(row)}>Complete</button></article>)}</section>
  </div>;
}

function Diagnostics({ data, episodeRef, busy, act }: any) {
  const [form, setForm] = useState({ modality: "laboratory", test: "", specimen: "" });
  const [report, setReport] = useState({ summary: "", critical: false });
  async function create() { await act("/api/clinical-execution/diagnostics", { episode_ref: episodeRef, modality: form.modality, requested_test: form.test, urgency: "routine", specimen_ref: form.specimen || null }, "Diagnostic request created."); }
  async function recordReport(row: any) {
    const summary = report.summary.trim();
    if (!summary) return;
    await act(`/api/clinical-execution/diagnostics/${row.workRef}`, { expected_version: row.version, status: "reported", report_summary: summary, critical_result: report.critical, reason: "Diagnostic result reported" }, "Diagnostic result reported.", "PATCH");
    setReport({ summary: "", critical: false });
  }
  return <div style={{ display: "grid", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Request laboratory or imaging work</h2><select style={field} value={form.modality} onChange={event => setForm({ ...form, modality: event.target.value })}><option value="laboratory">Laboratory</option><option value="xray">X-ray</option><option value="ultrasound">Ultrasound</option><option value="ct">CT</option><option value="mri">MRI</option></select><input placeholder="Requested test" style={field} value={form.test} onChange={event => setForm({ ...form, test: event.target.value })} /><input placeholder="Specimen reference" style={field} value={form.specimen} onChange={event => setForm({ ...form, specimen: event.target.value })} /><button disabled={busy || !episodeRef || !form.test} style={button} onClick={() => void create()}>Create diagnostic request</button></section><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Report evidence</h2><textarea placeholder="Report summary" style={{ ...field, minHeight: 92 }} value={report.summary} onChange={event => setReport({ ...report, summary: event.target.value })} /><label style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 850 }}><input type="checkbox" checked={report.critical} onChange={event => setReport({ ...report, critical: event.target.checked })} />Critical result requiring acknowledgement</label></section>{data.diagnostics.map((row: any) => <article key={row.workRef} style={{ ...panel, borderColor: row.criticalResult ? "#ef4444" : "#cbd5e1" }}><strong>{row.modality}: {row.requestedTest}</strong><p>{row.status} · {row.urgency}</p><button disabled={busy || row.status === "reported" || !report.summary.trim()} style={button} onClick={() => void recordReport(row)}>Record report</button></article>)}</div>;
}

function Pharmacy({ data, episodeRef, busy, act }: any) {
  const [item, setItem] = useState({ ref: "", name: "", quantity: "0", unit: "units", reorder: "0" });
  const [move, setMove] = useState({ ref: "", amount: "-1", type: "issued", version: "1", reason: "" });
  const [discrepancy, setDiscrepancy] = useState({ resolution: "", witness: "" });
  async function createItem() { await act("/api/clinical-execution/inventory", { item_ref: item.ref, name: item.name, item_type: "medication", quantity_on_hand: Number(item.quantity), unit: item.unit, reorder_level: Number(item.reorder), reason: "Opening or verified stock count" }, "Inventory item created."); }
  async function movement() { await act("/api/clinical-execution/governed/inventory-movements", { item_ref: move.ref, movement_type: move.type, quantity_change: Number(move.amount), expected_item_version: Number(move.version), reason: move.reason, episode_ref: episodeRef || null }, "Stock movement recorded in the ledger."); }
  async function resolveDiscrepancy(row: any) {
    const resolution = discrepancy.resolution.trim();
    const witness = discrepancy.witness.trim();
    if (!resolution || !witness) return;
    await act(`/api/clinical-execution/governed/controlled-drugs/${row.entryRef}/discrepancy`, { expected_version: row.version, resolution, witness_subject: witness }, "Controlled-drug discrepancy resolved with evidence.", "PATCH");
    setDiscrepancy({ resolution: "", witness: "" });
  }
  return <div style={grid}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Create opening stock record</h2><input placeholder="Stable item reference" style={field} value={item.ref} onChange={event => setItem({ ...item, ref: event.target.value })} /><input placeholder="Item name" style={field} value={item.name} onChange={event => setItem({ ...item, name: event.target.value })} /><input type="number" step="any" placeholder="Quantity" style={field} value={item.quantity} onChange={event => setItem({ ...item, quantity: event.target.value })} /><input placeholder="Unit" style={field} value={item.unit} onChange={event => setItem({ ...item, unit: event.target.value })} /><input type="number" step="any" placeholder="Reorder level" style={field} value={item.reorder} onChange={event => setItem({ ...item, reorder: event.target.value })} /><button disabled={busy || !item.ref || !item.name} style={button} onClick={() => void createItem()}>Create item</button></section><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Record stock movement</h2><input placeholder="Item reference" style={field} value={move.ref} onChange={event => setMove({ ...move, ref: event.target.value })} /><input placeholder="Movement type" style={field} value={move.type} onChange={event => setMove({ ...move, type: event.target.value })} /><input type="number" step="any" placeholder="Quantity change, e.g. -1 or 10" style={field} value={move.amount} onChange={event => setMove({ ...move, amount: event.target.value })} /><input type="number" placeholder="Expected item version" style={field} value={move.version} onChange={event => setMove({ ...move, version: event.target.value })} /><textarea placeholder="Reason" style={{ ...field, minHeight: 70 }} value={move.reason} onChange={event => setMove({ ...move, reason: event.target.value })} /><button disabled={busy || !move.ref || !move.reason} style={button} onClick={() => void movement()}>Record movement</button></section><section style={{ ...panel, gridColumn: "1 / -1", display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Controlled-drug discrepancy evidence</h2><textarea placeholder="Resolution and reconciliation" style={{ ...field, minHeight: 76 }} value={discrepancy.resolution} onChange={event => setDiscrepancy({ ...discrepancy, resolution: event.target.value })} /><input placeholder="Witness identity or reference" style={field} value={discrepancy.witness} onChange={event => setDiscrepancy({ ...discrepancy, witness: event.target.value })} /></section><section style={{ gridColumn: "1 / -1", display: "grid", gap: 8 }}><h2>Inventory</h2>{data.inventory.map((row: any) => <article key={row.itemRef} style={{ ...panel, borderColor: row.lowStock ? "#ef4444" : "#86efac" }}><strong>{row.name}</strong><p>{row.quantityOnHand} {row.unit} · reorder {row.reorderLevel} · v{row.version}</p></article>)}<h2>Controlled-drug discrepancies</h2>{data.controlledDrugEntries.filter((row: any) => row.discrepancy).map((row: any) => <article key={row.entryRef} style={{ ...panel, borderColor: row.discrepancyStatus === "resolved" ? "#86efac" : "#ef4444" }}><strong>{row.medicationRef}</strong><p>{row.discrepancyStatus} · balance {row.runningBalance} {row.unit}</p><button disabled={busy || row.discrepancyStatus === "resolved" || !discrepancy.resolution.trim() || !discrepancy.witness.trim()} style={button} onClick={() => void resolveDiscrepancy(row)}>Resolve discrepancy with witness</button></article>)}</section></div>;
}

function Discharge({ data, episodeRef, busy, act }: any) {
  const [draft, setDraft] = useState({ care: "", warnings: "", followUp: "" });
  const [evidence, setEvidence] = useState({ owner: "", referrer: "" });
  async function create() { await act("/api/clinical-execution/discharge-plans", { episode_ref: episodeRef, care_instructions: draft.care, warning_signs: draft.warnings, follow_up: draft.followUp }, "Discharge plan created."); }
  async function approve(row: any) {
    if (!evidence.owner.trim() || !evidence.referrer.trim()) return;
    await act(`/api/clinical-execution/governed/discharge-plans/${row.planRef}`, { expected_version: row.version, status: "approved", owner_communication_status: "completed", owner_communication_evidence_ref: evidence.owner.trim(), referring_vet_report_status: "sent", referring_vet_report_evidence_ref: evidence.referrer.trim(), reason: "Discharge gates and evidence reviewed by verified clinician" }, "Discharge approved with communication evidence.", "PATCH");
    setEvidence({ owner: "", referrer: "" });
  }
  return <div style={{ display: "grid", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Create discharge plan</h2><p style={{ margin: 0, color: "#475569" }}>Generate and approve detailed owner/referring-vet documents in the patient record before completing this discharge gate.</p><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"} style={{ ...button, textDecoration: "none", display: "inline-flex", alignItems: "center" }}>Generate documents</Link><Link href="/patient-record/controlled-actions" style={{ ...button, background: "#2563eb", textDecoration: "none", display: "inline-flex", alignItems: "center" }}>Approve or send document</Link></div><textarea placeholder="Care instructions" style={{ ...field, minHeight: 85 }} value={draft.care} onChange={event => setDraft({ ...draft, care: event.target.value })} /><textarea placeholder="Warning signs" style={{ ...field, minHeight: 85 }} value={draft.warnings} onChange={event => setDraft({ ...draft, warnings: event.target.value })} /><textarea placeholder="Follow-up" style={{ ...field, minHeight: 75 }} value={draft.followUp} onChange={event => setDraft({ ...draft, followUp: event.target.value })} /><button disabled={busy || !episodeRef || !draft.care || !draft.warnings} style={button} onClick={() => void create()}>Create plan</button></section><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Approval evidence</h2><input placeholder="Owner communication evidence reference" style={field} value={evidence.owner} onChange={event => setEvidence({ ...evidence, owner: event.target.value })} /><input placeholder="Referring-vet report evidence reference" style={field} value={evidence.referrer} onChange={event => setEvidence({ ...evidence, referrer: event.target.value })} /></section>{data.dischargePlans.map((row: any) => <article key={row.planRef} style={{ ...panel, borderColor: row.status === "approved" ? "#86efac" : "#f59e0b" }}><strong>{row.planRef}</strong><p>{row.status} · owner communication {row.ownerCommunicationStatus} · ref-vet report {row.referringVetReportStatus}</p><button disabled={busy || row.status === "approved" || !evidence.owner.trim() || !evidence.referrer.trim()} style={button} onClick={() => void approve(row)}>Approve with recorded evidence</button></article>)}</div>;
}
