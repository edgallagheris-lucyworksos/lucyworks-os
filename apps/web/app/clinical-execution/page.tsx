"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
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
};

type Tab = "overview" | "medications" | "anaesthesia" | "inpatient" | "diagnostics" | "pharmacy" | "discharge";
const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 14, boxShadow: "0 5px 16px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", minHeight: 44, border: "1px solid #94a3b8", borderRadius: 8, padding: "9px 10px", fontSize: 16, background: "white", color: "#0f172a", boxSizing: "border-box" };
const button: React.CSSProperties = { border: 0, borderRadius: 8, padding: "10px 12px", minHeight: 44, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };

export default function ClinicalExecutionPage() {
  return <AuthGuard allowedRoles={["clinician", "clinical_director", "nurse", "senior_clinician", "supervisor"]}><ClinicalExecution /></AuthGuard>;
}

function ClinicalExecution() {
  const [episodeRef, setEpisodeRef] = useState("");
  const [data, setData] = useState<Dashboard | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const query = episodeRef.trim() ? `?episode_ref=${encodeURIComponent(episodeRef.trim())}` : "";
      setData(await apiGet<Dashboard>(`/api/clinical-execution/dashboard${query}`));
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load clinical execution"); }
  }, [episodeRef]);
  useEffect(() => { void load(); }, [load]);

  async function act(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await apiJson(path, init); setMessage(success); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Clinical action failed"); }
    finally { setBusy(false); }
  }

  const tabs: Array<[Tab, string]> = [["overview", "Control"], ["medications", "Medications"], ["anaesthesia", "Anaesthesia"], ["inpatient", "Inpatient"], ["diagnostics", "Lab & imaging"], ["pharmacy", "Pharmacy"], ["discharge", "Discharge"]];
  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 17, padding: 17 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".12em" }}>CLINICAL EXECUTION</span><h1 style={{ margin: "5px 0", fontSize: "clamp(34px,7vw,66px)", lineHeight: .95 }}>Patient work</h1></div><Link href="/system-control" style={{ color: "white" }}>← System control</Link></div>
      <p style={{ color: "#94a3b8", maxWidth: 900 }}>Medication administration, anaesthesia gates, observations, treatment tasks, diagnostics, pharmacy and discharge evidence linked to the canonical referral episode.</p>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><input aria-label="Episode reference filter" placeholder="Episode reference" value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} style={{ ...field, maxWidth: 300 }} /><button style={button} onClick={() => void load()}>Load episode</button></div>
    </header>
    <div style={{ display: "flex", gap: 7, overflowX: "auto", padding: "10px 0" }}>{tabs.map(([key, label]) => <button key={key} onClick={() => setTab(key)} style={{ ...button, flex: "0 0 auto", background: tab === key ? "#0f766e" : "#334155" }}>{label}</button>)}</div>
    {error && <div style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginBottom: 9 }}>{error}</div>}
    {message && <div style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 9 }}>{message}</div>}
    {!data ? <section style={panel}>Loading…</section> : <>
      {tab === "overview" && <Overview data={data} />}
      {tab === "medications" && <Medications data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "anaesthesia" && <Anaesthesia data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "inpatient" && <Inpatient data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "diagnostics" && <Diagnostics data={data} episodeRef={episodeRef} busy={busy} act={act} />}
      {tab === "pharmacy" && <Pharmacy data={data} busy={busy} act={act} />}
      {tab === "discharge" && <Discharge data={data} episodeRef={episodeRef} busy={busy} act={act} />}
    </>}
  </main>;
}

function Overview({ data }: { data: Dashboard }) {
  return <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 8 }}>{Object.entries(data.summary).map(([label, value]) => <div key={label} style={{ ...panel, borderColor: value ? "#f59e0b" : "#86efac" }}><small style={{ color: "#64748b", textTransform: "uppercase", fontWeight: 800 }}>{label.replaceAll(/([A-Z])/g, " $1")}</small><div style={{ fontSize: 32, fontWeight: 950 }}>{value}</div></div>)}</section>;
}

function Medications({ data, episodeRef, busy, act }: any) {
  const [form, setForm] = useState({ medication_name: "", dose: "", route: "oral", frequency: "once", indication: "", due: new Date().toISOString().slice(0, 16), high_risk: false, controlled_drug: false });
  async function submit(event: FormEvent) { event.preventDefault(); const due = new Date(form.due).toISOString(); await act("/api/clinical-execution/medication-orders", { method: "POST", body: JSON.stringify({ episode_ref: episodeRef, medication_ref: form.medication_name.toLowerCase().replaceAll(" ", "-"), medication_name: form.medication_name, dose: form.dose, route: form.route, frequency: form.frequency, indication: form.indication, starts_at: due, scheduled_times: [due], high_risk: form.high_risk, controlled_drug: form.controlled_drug }) }, "Medication order and due administration created."); }
  async function administer(row: any, status: string) { const witness = status === "administered" ? window.prompt("Witness subject/reference if required:") : null; const reason = window.prompt("Reason:") || "Recorded from clinical execution workspace"; await act(`/api/clinical-execution/administrations/${row.administrationRef}`, { method: "PATCH", body: JSON.stringify({ expected_version: row.version, status, dose_given: status === "administered" ? window.prompt("Dose given:") : null, witness_subject: witness || null, omission_reason: status === "administered" ? null : reason, reason }) }, `Administration ${status}.`); }
  return <div style={{ display: "grid", gap: 9 }}><form onSubmit={submit} style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Prescribe and schedule</h2><input required placeholder="Medication" style={field} value={form.medication_name} onChange={e => setForm({ ...form, medication_name: e.target.value })} /><input required placeholder="Dose" style={field} value={form.dose} onChange={e => setForm({ ...form, dose: e.target.value })} /><input required placeholder="Route" style={field} value={form.route} onChange={e => setForm({ ...form, route: e.target.value })} /><input required placeholder="Frequency" style={field} value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })} /><textarea required placeholder="Indication" style={{ ...field, minHeight: 70 }} value={form.indication} onChange={e => setForm({ ...form, indication: e.target.value })} /><input type="datetime-local" style={field} value={form.due} onChange={e => setForm({ ...form, due: e.target.value })} /><label><input type="checkbox" checked={form.high_risk} onChange={e => setForm({ ...form, high_risk: e.target.checked })} /> High risk</label><label><input type="checkbox" checked={form.controlled_drug} onChange={e => setForm({ ...form, controlled_drug: e.target.checked })} /> Controlled drug</label><button disabled={busy || !episodeRef} style={button}>Create order</button></form>
    <section style={{ display: "grid", gap: 8 }}><h2>Due administrations</h2>{data.administrations.map((row: any) => <article key={row.administrationRef} style={{ ...panel, borderColor: row.status === "due" && new Date(row.scheduledAt) < new Date() ? "#ef4444" : "#cbd5e1" }}><strong>{row.orderRef}</strong><p>{new Date(row.scheduledAt).toLocaleString()} · {row.status}</p><div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><button disabled={busy || row.status !== "due"} style={button} onClick={() => void administer(row, "administered")}>Administer</button><button disabled={busy || row.status !== "due"} style={{ ...button, background: "#a16207" }} onClick={() => void administer(row, "omitted")}>Omit</button><button disabled={busy || row.status !== "due"} style={{ ...button, background: "#475569" }} onClick={() => void administer(row, "withheld")}>Withhold</button></div></article>)}</section></div>;
}

function Anaesthesia({ data, episodeRef, busy, act }: any) {
  const [blockRef, setBlockRef] = useState("");
  async function create() { await act("/api/clinical-execution/anaesthesia", { method: "POST", body: JSON.stringify({ episode_ref: episodeRef, block_ref: blockRef || null, responsible_clinician_subject: "current-clinician", responsible_clinician_name: "Verified current clinician", checklist: {} }) }, "Anaesthesia record created."); }
  async function transition(row: any, status: string) { const checklist = status === "induced" ? { identity_checked: true, consent_checked: true, equipment_checked: true, airway_plan_confirmed: true } : row.checklist; await act(`/api/clinical-execution/anaesthesia/${row.recordRef}`, { method: "PATCH", body: JSON.stringify({ expected_version: row.version, status, checklist, reason: `${status} recorded by verified operator` }) }, `Anaesthesia ${status}.`); }
  return <div style={{ display: "grid", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Create anaesthesia record</h2><input placeholder="Operational block reference" style={field} value={blockRef} onChange={e => setBlockRef(e.target.value)} /><button disabled={busy || !episodeRef} style={button} onClick={() => void create()}>Create record</button></section>{data.anaesthesia.map((row: any) => <article key={row.recordRef} style={panel}><strong>{row.recordRef}</strong><p>{row.status} · ASA {row.asaStatus || "not recorded"}</p><div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><button disabled={busy} style={button} onClick={() => void transition(row, "induced")}>Complete checklist & induce</button><button disabled={busy} style={{ ...button, background: "#2563eb" }} onClick={() => void transition(row, "recovered")}>Record recovery</button></div></article>)}</div>;
}

function Inpatient({ data, episodeRef, busy, act }: any) {
  const [obs, setObs] = useState({ type: "ward_observation", concern: "green", values: "{\"temperature\":38.0}" });
  const [task, setTask] = useState({ title: "", instructions: "", due: new Date().toISOString().slice(0, 16), role: "nurse", priority: "amber" });
  async function addObservation() { await act("/api/clinical-execution/observations", { method: "POST", body: JSON.stringify({ episode_ref: episodeRef, observation_type: obs.type, values: JSON.parse(obs.values), concern_level: obs.concern }) }, "Observation recorded and escalation created where required."); }
  async function addTask() { await act("/api/clinical-execution/treatment-tasks", { method: "POST", body: JSON.stringify({ episode_ref: episodeRef, task_type: "treatment", title: task.title, instructions: task.instructions, due_at: new Date(task.due).toISOString(), assigned_role: task.role, priority: task.priority }) }, "Treatment task created."); }
  async function complete(row: any) { await act(`/api/clinical-execution/treatment-tasks/${row.taskRef}/complete`, { method: "PATCH", body: JSON.stringify({ expected_version: row.version, reason: "Treatment completed and checked" }) }, "Treatment task completed."); }
  return <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Observation</h2><input style={field} value={obs.type} onChange={e => setObs({ ...obs, type: e.target.value })} /><select style={field} value={obs.concern} onChange={e => setObs({ ...obs, concern: e.target.value })}><option>green</option><option>amber</option><option>red</option></select><textarea style={{ ...field, minHeight: 100, fontFamily: "monospace" }} value={obs.values} onChange={e => setObs({ ...obs, values: e.target.value })} /><button disabled={busy || !episodeRef} style={button} onClick={() => void addObservation()}>Record observation</button></section><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Treatment task</h2><input required placeholder="Task" style={field} value={task.title} onChange={e => setTask({ ...task, title: e.target.value })} /><textarea placeholder="Instructions" style={{ ...field, minHeight: 70 }} value={task.instructions} onChange={e => setTask({ ...task, instructions: e.target.value })} /><input type="datetime-local" style={field} value={task.due} onChange={e => setTask({ ...task, due: e.target.value })} /><input style={field} value={task.role} onChange={e => setTask({ ...task, role: e.target.value })} /><button disabled={busy || !episodeRef} style={button} onClick={() => void addTask()}>Create task</button></section><section style={{ gridColumn: "1 / -1", display: "grid", gap: 8 }}>{data.tasks.map((row: any) => <article key={row.taskRef} style={{ ...panel, borderColor: row.status !== "completed" && new Date(row.dueAt) < new Date() ? "#ef4444" : "#cbd5e1" }}><strong>{row.title}</strong><p>{row.status} · due {new Date(row.dueAt).toLocaleString()}</p><button disabled={busy || row.status === "completed"} style={button} onClick={() => void complete(row)}>Complete</button></article>)}</section></div>;
}

function Diagnostics({ data, episodeRef, busy, act }: any) {
  const [form, setForm] = useState({ modality: "laboratory", test: "", urgency: "routine", specimen: "" });
  async function create() { await act("/api/clinical-execution/diagnostics", { method: "POST", body: JSON.stringify({ episode_ref: episodeRef, modality: form.modality, requested_test: form.test, urgency: form.urgency, specimen_ref: form.specimen || null }) }, "Diagnostic work item created."); }
  async function report(row: any) { const summary = window.prompt("Report summary:") || "Report entered"; const critical = window.confirm("Is this a critical result requiring acknowledgement?"); await act(`/api/clinical-execution/diagnostics/${row.workRef}`, { method: "PATCH", body: JSON.stringify({ expected_version: row.version, status: "reported", report_summary: summary, critical_result: critical, reason: "Diagnostic result reported" }) }, "Diagnostic result reported."); }
  return <div style={{ display: "grid", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Request laboratory or imaging work</h2><select style={field} value={form.modality} onChange={e => setForm({ ...form, modality: e.target.value })}><option value="laboratory">Laboratory</option><option value="xray">X-ray</option><option value="ultrasound">Ultrasound</option><option value="ct">CT</option><option value="mri">MRI</option></select><input placeholder="Requested test" style={field} value={form.test} onChange={e => setForm({ ...form, test: e.target.value })} /><input placeholder="Specimen reference" style={field} value={form.specimen} onChange={e => setForm({ ...form, specimen: e.target.value })} /><button disabled={busy || !episodeRef} style={button} onClick={() => void create()}>Create diagnostic request</button></section>{data.diagnostics.map((row: any) => <article key={row.workRef} style={{ ...panel, borderColor: row.criticalResult ? "#ef4444" : "#cbd5e1" }}><strong>{row.modality}: {row.requestedTest}</strong><p>{row.status} · {row.urgency}</p><button disabled={busy || row.status === "reported"} style={button} onClick={() => void report(row)}>Record report</button></article>)}</div>;
}

function Pharmacy({ data, busy, act }: any) {
  const [form, setForm] = useState({ ref: "", name: "", quantity: "0", unit: "units", reorder: "0", version: "" });
  async function save() { await act("/api/clinical-execution/inventory", { method: "POST", body: JSON.stringify({ item_ref: form.ref, name: form.name, item_type: "medication", quantity_on_hand: Number(form.quantity), unit: form.unit, reorder_level: Number(form.reorder), expected_version: form.version ? Number(form.version) : null, reason: "Stock count recorded" }) }, "Inventory item saved."); }
  return <div style={{ display: "grid", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Inventory count</h2><input placeholder="Stable item reference" style={field} value={form.ref} onChange={e => setForm({ ...form, ref: e.target.value })} /><input placeholder="Item name" style={field} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /><input type="number" step="any" placeholder="Quantity" style={field} value={form.quantity} onChange={e => setForm({ ...form, quantity: e.target.value })} /><input placeholder="Unit" style={field} value={form.unit} onChange={e => setForm({ ...form, unit: e.target.value })} /><input type="number" step="any" placeholder="Reorder level" style={field} value={form.reorder} onChange={e => setForm({ ...form, reorder: e.target.value })} /><input type="number" placeholder="Expected version when updating" style={field} value={form.version} onChange={e => setForm({ ...form, version: e.target.value })} /><button disabled={busy} style={button} onClick={() => void save()}>Save stock count</button></section>{data.inventory.map((row: any) => <article key={row.itemRef} style={{ ...panel, borderColor: row.lowStock ? "#ef4444" : "#86efac" }}><strong>{row.name}</strong><p>{row.quantityOnHand} {row.unit} · reorder at {row.reorderLevel} · v{row.version}</p></article>)}</div>;
}

function Discharge({ data, episodeRef, busy, act }: any) {
  const [care, setCare] = useState(""); const [warnings, setWarnings] = useState(""); const [followUp, setFollowUp] = useState("");
  async function create() { await act("/api/clinical-execution/discharge-plans", { method: "POST", body: JSON.stringify({ episode_ref: episodeRef, care_instructions: care, warning_signs: warnings, follow_up: followUp }) }, "Discharge plan created."); }
  async function approve(row: any) { await act(`/api/clinical-execution/discharge-plans/${row.planRef}`, { method: "PATCH", body: JSON.stringify({ expected_version: row.version, status: "approved", care_instructions: row.careInstructions || care, warning_signs: row.warningSigns || warnings, follow_up: row.followUp || followUp, owner_communication_status: "completed", referring_vet_report_status: "sent", reason: "Discharge gates completed and clinician approved" }) }, "Discharge approved."); }
  return <div style={{ display: "grid", gap: 9 }}><section style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Create discharge plan</h2><textarea placeholder="Care instructions" style={{ ...field, minHeight: 80 }} value={care} onChange={e => setCare(e.target.value)} /><textarea placeholder="Warning signs" style={{ ...field, minHeight: 80 }} value={warnings} onChange={e => setWarnings(e.target.value)} /><textarea placeholder="Follow-up" style={{ ...field, minHeight: 70 }} value={followUp} onChange={e => setFollowUp(e.target.value)} /><button disabled={busy || !episodeRef} style={button} onClick={() => void create()}>Create plan</button></section>{data.dischargePlans.map((row: any) => <article key={row.planRef} style={panel}><strong>{row.planRef}</strong><p>{row.status} · owner communication {row.ownerCommunicationStatus} · referring-vet report {row.referringVetReportStatus}</p><button disabled={busy || row.status === "approved"} style={button} onClick={() => void approve(row)}>Complete gates and approve</button></article>)}</div>;
}
