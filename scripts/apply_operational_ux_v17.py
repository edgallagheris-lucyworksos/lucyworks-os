#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one regex match, found {count}")
    return updated


# 1. Desktop board must use the browser's local operating date.
path = "apps/web/components/hospital-master-board-v11.tsx"
text = read(path)
text = replace_once(
    text,
    'function today() {\n  return new Date().toISOString().slice(0, 10);\n}',
    'function today() {\n  const value = new Date();\n  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);\n  return local.toISOString().slice(0, 10);\n}',
    "master board local date",
)
write(path, text)


# 2. Episode Command: retain patient context and replace browser prompts with governed fields.
path = "apps/web/components/hospital-command-workspace.tsx"
text = read(path)
text = replace_once(
    text,
    '  const [tab, setTab] = useState<Tab>("control");\n\n  const load = useCallback(async () => {',
    '  const [tab, setTab] = useState<Tab>("control");\n\n  useEffect(() => {\n    const initial = new URLSearchParams(window.location.search).get("episode");\n    if (initial) setEpisodeRef(initial);\n  }, []);\n\n  const load = useCallback(async () => {',
    "episode command URL context effect",
)
text = replace_once(
    text,
    '      setData(result);\n      setError("");',
    '      setData(result);\n      window.history.replaceState(null, "", `/episode-command?episode=${encodeURIComponent(result.episode.episode_ref)}`);\n      setError("");',
    "episode command URL persistence",
)
text = replace_once(
    text,
    '          <Link href="/system-control" style={{ color: "white" }}>← System control</Link>',
    '          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>\n            <Link href={episodeRef ? `/care?episode=${encodeURIComponent(episodeRef)}` : "/workspace"} style={{ color: "white" }}>← Care brief</Link>\n            <Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"} style={{ color: "white" }}>Patient record</Link>\n            <Link href={episodeRef ? `/clinical-execution?episode=${encodeURIComponent(episodeRef)}` : "/clinical-execution"} style={{ color: "white" }}>Patient work</Link>\n          </div>',
    "episode command context links",
)
control_head = '''function Control({ data, busy, act }: { data: CommandView; busy: boolean; act: Act }) {
  const [reason, setReason] = useState("");
  const [waiverHours, setWaiverHours] = useState("1");
  const [actionError, setActionError] = useState("");

  async function decide(status: string) {
    const value = reason.trim();
    if (!data.referral || !value) {
      setActionError("Record a reason before changing the referral decision.");
      return;
    }
    setActionError("");
    await act(`/api/v9/referrals/${data.referral.referral_ref}`, { expected_version: data.referral.version, status, reason: value }, `Referral ${status}.`, "PATCH");
    setReason("");
  }

  async function transition(target: string) {
    const value = reason.trim();
    if (!value) {
      setActionError("Record a reason before moving the episode.");
      return;
    }
    setActionError("");
    await act(
      `/api/v9/episodes/${data.episode.episode_ref}/transition`,
      {
        expected_version: data.episode.version,
        target_phase: target,
        idempotency_key: `ui:${data.episode.episode_ref}:${data.episode.version}:${target}:${Date.now()}`,
        reason: value,
      },
      `Episode transitioned to ${target}.`,
    );
    setReason("");
  }

  async function waive(code: string) {
    const value = reason.trim();
    const hours = Number(waiverHours);
    if (!value) {
      setActionError("Record the senior waiver reason.");
      return;
    }
    if (!Number.isFinite(hours) || hours <= 0 || hours > 24) {
      setActionError("Waiver duration must be greater than 0 and no more than 24 hours.");
      return;
    }
    setActionError("");
    await act(
      `/api/v9/episodes/${data.episode.episode_ref}/checkpoints`,
      {
        checkpoint_code: code,
        status: "waived",
        detail: { source: "episode-command-ui", durationHours: hours },
        reason: value,
        valid_until: new Date(Date.now() + hours * 60 * 60 * 1000).toISOString(),
      },
      `${code} recorded as a time-bounded senior waiver.`,
    );
    setReason("");
  }

  return (
    <div style={{ display: "grid", gap: 9 }}>
      <section style={{ ...panel, display: "grid", gap: 8, borderColor: actionError ? "#ef4444" : "#93c5fd" }}>
        <label style={{ fontWeight: 850 }}>Reason for the next decision or transition
          <textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="What changed, why this action is safe, and any relevant evidence" style={{ ...field, minHeight: 82 }} />
        </label>
        <label style={{ fontWeight: 850 }}>Senior waiver duration, hours
          <input type="number" min="0.25" max="24" step="0.25" value={waiverHours} onChange={event => setWaiverHours(event.target.value)} style={{ ...field, maxWidth: 220 }} />
        </label>
        {actionError && <strong role="alert" style={{ color: "#991b1b" }}>{actionError}</strong>}
      </section>'''
text = sub_once(
    text,
    r'function Control\(\{ data, busy, act \}: \{ data: CommandView; busy: boolean; act: Act \}\) \{.*?  return \(\n    <div style=\{\{ display: "grid", gap: 9 \}\}>',
    control_head,
    "episode command governed action form",
)
text = replace_once(
    text,
    '  const [form, setForm] = useState({ ownerRef: "", type: "admission", decisionMaker: "", channel: "telephone", maximumPounds: "", scope: "{}" });',
    '  const [form, setForm] = useState({ ownerRef: "", type: "admission", decisionMaker: "", channel: "telephone", maximumPounds: "", scopeSummary: "" });\n  const [withdrawReason, setWithdrawReason] = useState("");',
    "consent structured state",
)
text = replace_once(text, '        scope: JSON.parse(form.scope || "{}"),', '        scope: { summary: form.scopeSummary.trim() },', "consent scope object")
text = sub_once(
    text,
    r'  async function withdraw\(row: any\) \{.*?\n  \}',
    '  async function withdraw(row: any) {\n    const reason = withdrawReason.trim();\n    if (!reason) return;\n    await act(`/api/v9/consents/${row.consent_ref}/withdraw`, { expected_version: row.version, reason }, "Consent withdrawn.", "PATCH");\n    setWithdrawReason("");\n  }',
    "consent withdrawal form",
)
text = replace_once(
    text,
    '        <textarea aria-label="Consent scope JSON" style={{ ...field, minHeight: 95, fontFamily: "monospace" }} value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })} />',
    '        <textarea aria-label="Consent scope" placeholder="Agreed procedure, options discussed, material risks, limitations and owner questions" style={{ ...field, minHeight: 110 }} value={form.scopeSummary} onChange={e => setForm({ ...form, scopeSummary: e.target.value })} />',
    "consent scope UI",
)
text = replace_once(
    text,
    '        <h2 style={{ margin: 0 }}>Consent history</h2>',
    '        <h2 style={{ margin: 0 }}>Consent history</h2>\n        <textarea aria-label="Consent withdrawal reason" placeholder="Reason required before withdrawing an active consent" style={{ ...field, minHeight: 72 }} value={withdrawReason} onChange={event => setWithdrawReason(event.target.value)} />',
    "consent withdrawal reason field",
)
text = replace_once(
    text,
    '<button disabled={busy || row.status !== "active"} style={{ ...button, background: "#991b1b" }} onClick={() => void withdraw(row)}>Withdraw</button>',
    '<button disabled={busy || row.status !== "active" || !withdrawReason.trim()} style={{ ...button, background: "#991b1b" }} onClick={() => void withdraw(row)}>Withdraw with recorded reason</button>',
    "consent withdrawal button",
)
text = replace_once(
    text,
    '  const [form, setForm] = useState({ role: "nurse", subject: "", area: "", priority: "amber", situation: "", background: "", assessment: "", recommendation: "", risks: "[]", actions: "[]" });',
    '  const [form, setForm] = useState({ role: "nurse", subject: "", area: "", priority: "amber", situation: "", background: "", assessment: "", recommendation: "", risks: "", actions: "" });\n  const [acknowledgementNote, setAcknowledgementNote] = useState("");',
    "handover structured state",
)
text = replace_once(text, '        risks: JSON.parse(form.risks || "[]"),\n        pending_actions: JSON.parse(form.actions || "[]"),', '        risks: form.risks.split("\\n").map(value => value.trim()).filter(Boolean),\n        pending_actions: form.actions.split("\\n").map(value => value.trim()).filter(Boolean),', "handover list parsing")
text = sub_once(
    text,
    r'  async function acknowledge\(row: any\) \{.*?\n  \}',
    '  async function acknowledge(row: any) {\n    const reason = acknowledgementNote.trim();\n    if (!reason) return;\n    await act(`/api/v9/handovers/${row.handover_ref}/acknowledge`, { expected_version: row.version, reason }, "Handover acknowledged.", "PATCH");\n    setAcknowledgementNote("");\n  }',
    "handover acknowledgement form",
)
text = replace_once(text, '<textarea aria-label="Handover risks JSON" style={{ ...field, minHeight: 80, fontFamily: "monospace" }} value={form.risks} onChange={e => setForm({ ...form, risks: e.target.value })} />', '<textarea aria-label="Handover risks" placeholder="One risk per line" style={{ ...field, minHeight: 90 }} value={form.risks} onChange={e => setForm({ ...form, risks: e.target.value })} />', "handover risks UI")
text = replace_once(text, '<textarea aria-label="Pending actions JSON" style={{ ...field, minHeight: 80, fontFamily: "monospace" }} value={form.actions} onChange={e => setForm({ ...form, actions: e.target.value })} />', '<textarea aria-label="Pending actions" placeholder="One pending action per line" style={{ ...field, minHeight: 90 }} value={form.actions} onChange={e => setForm({ ...form, actions: e.target.value })} />', "handover actions UI")
text = replace_once(text, '        <h2 style={{ margin: 0 }}>Handover ledger</h2>', '        <h2 style={{ margin: 0 }}>Handover ledger</h2>\n        <textarea aria-label="Handover acknowledgement note" placeholder="What was received, checked and accepted" style={{ ...field, minHeight: 72 }} value={acknowledgementNote} onChange={event => setAcknowledgementNote(event.target.value)} />', "handover acknowledgement field")
text = replace_once(text, '<button disabled={busy || row.status !== "offered"} style={button} onClick={() => void acknowledge(row)}>Acknowledge</button>', '<button disabled={busy || row.status !== "offered" || !acknowledgementNote.trim()} style={button} onClick={() => void acknowledge(row)}>Acknowledge with note</button>', "handover acknowledgement button")
text = replace_once(text, '    retainedRisks: "[]",\n  });', '    retainedRisks: "",\n  });\n  const [approvalReason, setApprovalReason] = useState("");', "closure structured state")
text = replace_once(text, '        retained_risks: JSON.parse(form.retainedRisks || "[]"),', '        retained_risks: form.retainedRisks.split("\\n").map(value => value.trim()).filter(Boolean),', "closure retained risks parsing")
text = sub_once(
    text,
    r'  async function approve\(\) \{.*?\n  \}',
    '  async function approve() {\n    if (!data.closure) return;\n    const reason = approvalReason.trim();\n    if (!reason) return;\n    await act(`/api/v9/closures/${data.closure.closure_ref}/approve`, { expected_version: data.closure.version, reason }, "Closure approved.", "PATCH");\n    setApprovalReason("");\n  }',
    "closure approval form",
)
text = replace_once(text, '<textarea aria-label="Retained risks JSON" style={{ ...field, minHeight: 90, fontFamily: "monospace" }} value={form.retainedRisks} onChange={e => setForm({ ...form, retainedRisks: e.target.value })} />', '<textarea aria-label="Retained risks" placeholder="One retained risk per line" style={{ ...field, minHeight: 90 }} value={form.retainedRisks} onChange={e => setForm({ ...form, retainedRisks: e.target.value })} />', "closure retained risks UI")
text = replace_once(text, '          <p>{data.closure.outstanding_actions.length} outstanding actions · {data.closure.retained_risks.length} retained risks</p>\n          <button disabled={busy || data.closure.status !== "draft"} style={button} onClick={() => void approve()}>Senior approve</button>', '          <p>{data.closure.outstanding_actions.length} outstanding actions · {data.closure.retained_risks.length} retained risks</p>\n          <textarea aria-label="Senior closure approval reason" placeholder="Clinical and operational evidence reviewed" style={{ ...field, minHeight: 72 }} value={approvalReason} onChange={event => setApprovalReason(event.target.value)} />\n          <button disabled={busy || data.closure.status !== "draft" || !approvalReason.trim()} style={button} onClick={() => void approve()}>Senior approve with reason</button>', "closure approval UI")
write(path, text)


# 3. Patient Record: automatically open the episode and retain it across related pages.
path = "apps/web/components/detailed-patient-record-workspace.tsx"
text = read(path)
text = replace_once(text, 'import { useCallback, useMemo, useState } from "react";', 'import { useCallback, useEffect, useMemo, useState } from "react";', "patient record effect import")
text = replace_once(
    text,
    '  const [message, setMessage] = useState("");\n\n  const load = useCallback(async () => {',
    '  const [message, setMessage] = useState("");\n\n  useEffect(() => {\n    const initial = new URLSearchParams(window.location.search).get("episode");\n    if (initial) setEpisodeRef(initial);\n  }, []);\n\n  const load = useCallback(async () => {',
    "patient record URL context effect",
)
text = replace_once(
    text,
    '    try { setData(await apiGet<RecordData>(`/api/v8/episodes/${encodeURIComponent(episodeRef.trim())}/record`)); }',
    '    try {\n      const result = await apiGet<RecordData>(`/api/v8/episodes/${encodeURIComponent(episodeRef.trim())}/record`);\n      setData(result);\n      window.history.replaceState(null, "", `/patient-record?episode=${encodeURIComponent(result.episode?.episode_ref || episodeRef.trim())}`);\n    }',
    "patient record URL persistence",
)
text = replace_once(
    text,
    '        <Link href="/system-control" style={{ color: "white" }}>← System control</Link>',
    '        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}><Link href={episodeRef ? `/care?episode=${encodeURIComponent(episodeRef)}` : "/workspace"} style={{ color: "white" }}>← Care brief</Link><Link href={episodeRef ? `/episode-command?episode=${encodeURIComponent(episodeRef)}` : "/episode-command"} style={{ color: "white" }}>Episode decisions</Link><Link href={episodeRef ? `/clinical-execution?episode=${encodeURIComponent(episodeRef)}` : "/clinical-execution"} style={{ color: "white" }}>Patient work</Link></div>',
    "patient record context links",
)
text = replace_once(
    text,
    '    {message && <div aria-live="polite" style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 10 }}>{message}</div>}\n    {!data ?',
    '    {message && <div aria-live="polite" style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 10 }}>{message}</div>}\n    {data && <section style={{ ...panel, position: "sticky", top: 6, zIndex: 20, marginBottom: 10, borderLeft: "7px solid #0f766e", display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><div><strong style={{ fontSize: 22 }}>{data.patient?.display_name || data.episode?.patient_name}</strong><div>{data.patient?.species || "Species not recorded"} · {data.episode?.episode_ref}</div></div><div><strong>{data.episode?.current_area_ref || "Location not recorded"}</strong><div>{data.episode?.phase} · accountable {data.episode?.owner_role}</div></div></section>}\n    {!data ?',
    "patient record sticky identity",
)
write(path, text)


# 4. Clinical Execution: URL context, local dates and governed mobile-safe forms.
path = "apps/web/app/clinical-execution/page.tsx"
text = read(path)
text = replace_once(
    text,
    'const grid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,320px),1fr))", gap: 9 };',
    'const grid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,320px),1fr))", gap: 9 };\n\nfunction localDateTimeInput() {\n  const value = new Date();\n  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);\n  return local.toISOString().slice(0, 16);\n}',
    "clinical execution local datetime helper",
)
text = replace_once(
    text,
    '  const [message, setMessage] = useState("");\n\n  const load = useCallback(async () => {',
    '  const [message, setMessage] = useState("");\n\n  useEffect(() => {\n    const initial = new URLSearchParams(window.location.search).get("episode");\n    if (initial) setEpisodeRef(initial);\n  }, []);\n\n  const load = useCallback(async () => {',
    "clinical execution URL context effect",
)
text = replace_once(
    text,
    '      setData(await apiGet<Dashboard>(`/api/clinical-execution/governed/dashboard${query}`));\n      setError("");',
    '      setData(await apiGet<Dashboard>(`/api/clinical-execution/governed/dashboard${query}`));\n      if (episodeRef.trim()) window.history.replaceState(null, "", `/clinical-execution?episode=${encodeURIComponent(episodeRef.trim())}`);\n      setError("");',
    "clinical execution URL persistence",
)
text = replace_once(
    text,
    '<Link href="/patient-record" style={{ color: "white" }}>Patient record</Link><Link href="/patient-record/controlled-actions" style={{ color: "white" }}>Controlled actions</Link><Link href="/system-control" style={{ color: "white" }}>System control</Link>',
    '<Link href={episodeRef ? `/care?episode=${encodeURIComponent(episodeRef)}` : "/workspace"} style={{ color: "white" }}>Care brief</Link><Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"} style={{ color: "white" }}>Patient record</Link><Link href={episodeRef ? `/episode-command?episode=${encodeURIComponent(episodeRef)}` : "/episode-command"} style={{ color: "white" }}>Episode decisions</Link><Link href="/patient-record/controlled-actions" style={{ color: "white" }}>Controlled actions</Link>',
    "clinical execution context links",
)
medications = '''function Medications({ data, busy, act }: any) {
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
'''
text = sub_once(text, r'function Medications\(\{ data, busy, act \}: any\) \{.*?\n\}\n\nfunction Anaesthesia', medications + '\nfunction Anaesthesia', "clinical medication evidence form")
inpatient = '''function Inpatient({ data, episodeRef, busy, act }: any) {
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
'''
text = sub_once(text, r'function Inpatient\(\{ data, episodeRef, busy, act \}: any\) \{.*?\n\}\n\nfunction Diagnostics', inpatient + '\nfunction Diagnostics', "clinical inpatient forms")
diagnostics = '''function Diagnostics({ data, episodeRef, busy, act }: any) {
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
'''
text = sub_once(text, r'function Diagnostics\(\{ data, episodeRef, busy, act \}: any\) \{.*?\n\}\n\nfunction Pharmacy', diagnostics + '\nfunction Pharmacy', "clinical diagnostic report form")
pharmacy = '''function Pharmacy({ data, episodeRef, busy, act }: any) {
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
'''
text = sub_once(text, r'function Pharmacy\(\{ data, episodeRef, busy, act \}: any\) \{.*?\n\}\n\nfunction Discharge', pharmacy + '\nfunction Discharge', "clinical pharmacy discrepancy form")
discharge = '''function Discharge({ data, episodeRef, busy, act }: any) {
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
'''
text = sub_once(text, r'function Discharge\(\{ data, episodeRef, busy, act \}: any\) \{.*\Z', discharge, "clinical discharge evidence form")
write(path, text)

print("Operational UX v17 source transformations applied")
