"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, apiJson } from "@/lib/api-client";

type Dashboard = {
  premisesRef: string;
  configuration: Array<Record<string, any>>;
  claims: Array<Record<string, any>>;
  verificationTasks: Array<Record<string, any>>;
  workforce: Array<Record<string, any>>;
  competencies: Array<Record<string, any>>;
  coverageRequirements: Array<Record<string, any>>;
  referrals: Array<Record<string, any>>;
  replayRuns: Array<Record<string, any>>;
  summary: Record<string, any>;
};

type Tab = "overview" | "configuration" | "workforce" | "referrals" | "replay";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 16, padding: 16, boxShadow: "0 6px 18px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", background: "white", color: "#0f172a" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "9px 12px", background: "#0f766e", color: "white", fontWeight: 800, cursor: "pointer" };

function statusColour(value: string): string {
  if (["verified", "passed", "accepted", "ready_for_clinical_review", "met"].includes(value)) return "#047857";
  if (["disputed", "failed", "declined", "gap"].includes(value)) return "#b91c1c";
  return "#a16207";
}

function Status({ value }: { value: string }) {
  return <span style={{ display: "inline-block", padding: "3px 7px", borderRadius: 999, background: `${statusColour(value)}18`, color: statusColour(value), fontSize: 11, fontWeight: 900, textTransform: "uppercase" }}>{value.replaceAll("_", " ")}</span>;
}

function Metric({ label, value, warning }: { label: string; value: string | number; warning?: boolean }) {
  return <div style={{ ...panel, padding: 13, borderColor: warning ? "#fca5a5" : "#cbd5e1" }}><div style={{ color: "#64748b", fontSize: 11, fontWeight: 900, textTransform: "uppercase", letterSpacing: ".08em" }}>{label}</div><div style={{ fontSize: 29, fontWeight: 950, marginTop: 5, color: warning ? "#b91c1c" : "#0f172a" }}>{value}</div></div>;
}

export function BvsConfigurationWorkspace() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [coverage, setCoverage] = useState<Record<string, any> | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await apiGet<Dashboard>("/api/bvs-v6/dashboard");
      setData(result);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load BVS workspace");
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
      setError(err instanceof Error ? err.message : "Action failed");
    } finally { setBusy(false); }
  }

  async function bootstrap() {
    await act("/api/bvs-v6/bootstrap", { method: "POST" }, "Draft BVS configuration and verification queue created.");
  }

  async function runCoverage() {
    setBusy(true);
    try { setCoverage(await apiGet("/api/bvs-v6/coverage-assessment")); setMessage("Coverage capability assessment updated."); }
    catch (err) { setError(err instanceof Error ? err.message : "Coverage assessment failed"); }
    finally { setBusy(false); }
  }

  const theatreClaims = useMemo(() => data?.claims.filter(item => item.fieldName === "operatingTheatreCount") || [], [data]);
  const openRed = data?.verificationTasks.filter(item => item.priority === "red" && item.status !== "verified") || [];

  if (!data) return <main style={{ minHeight: "100vh", padding: 20, background: "#e9eef5", color: "#0f172a" }}><h1>BVS configuration</h1><p>{error || "Loading…"}</p><button style={button} onClick={bootstrap}>Create draft configuration</button></main>;

  const tabs: Array<[Tab, string]> = [["overview", "Control summary"], ["configuration", "Configuration & verification"], ["workforce", "Workforce & competencies"], ["referrals", "Referral intake"], ["replay", "Historical replay"]];

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
        <div><span style={{ color: "#2dd4bf", fontWeight: 900, fontSize: 11, letterSpacing: ".12em", textTransform: "uppercase" }}>LucyWorks OS · v6</span><h1 style={{ margin: "5px 0", fontSize: "clamp(34px,7vw,66px)", lineHeight: .95 }}>BVS hospital configuration</h1></div>
        <Link href="/system-control" style={{ color: "white", textDecoration: "none", border: "1px solid #334155", borderRadius: 9, padding: "8px 11px" }}>← System control</Link>
      </div>
      <p style={{ color: "#94a3b8", maxWidth: 920 }}>Public evidence, internal claims and hospital-approved facts remain separate. Nothing becomes operational truth until an authorised person verifies it with evidence.</p>
    </header>

    <div style={{ display: "flex", gap: 7, overflowX: "auto", padding: "10px 0" }}>{tabs.map(([key, label]) => <button key={key} onClick={() => setTab(key)} style={{ ...button, flex: "0 0 auto", background: tab === key ? "#0f766e" : "#334155" }}>{label}</button>)}</div>
    {error && <div style={{ ...panel, borderColor: "#fca5a5", color: "#991b1b", marginBottom: 10 }}>{error}</div>}
    {message && <div style={{ ...panel, borderColor: "#86efac", color: "#166534", marginBottom: 10 }}>{message}</div>}

    {tab === "overview" && <Overview data={data} theatreClaims={theatreClaims} openRed={openRed} busy={busy} bootstrap={bootstrap} runCoverage={runCoverage} coverage={coverage} />}
    {tab === "configuration" && <Configuration data={data} busy={busy} act={act} />}
    {tab === "workforce" && <Workforce data={data} busy={busy} act={act} coverage={coverage} runCoverage={runCoverage} />}
    {tab === "referrals" && <Referrals data={data} busy={busy} act={act} />}
    {tab === "replay" && <Replay data={data} busy={busy} act={act} />}
  </main>;
}

function Overview({ data, theatreClaims, openRed, busy, bootstrap, runCoverage, coverage }: any) {
  const s = data.summary;
  return <div style={{ display: "grid", gap: 10 }}>
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 9 }}>
      <Metric label="Configuration" value={`${s.verifiedConfiguration}/${s.configurationRecords}`} warning={!s.verifiedConfiguration} />
      <Metric label="Disputed claims" value={s.disputedClaims} warning={s.disputedClaims > 0} />
      <Metric label="Red verification tasks" value={s.openRedTasks} warning={s.openRedTasks > 0} />
      <Metric label="Workforce profiles" value={s.workforceProfiles} warning={s.workforceProfiles === 0} />
      <Metric label="Incomplete referrals" value={s.referralsMissingInformation} warning={s.referralsMissingInformation > 0} />
      <Metric label="Passed replays" value={s.passedReplays} warning={s.passedReplays === 0} />
    </section>
    <section style={{ ...panel, borderColor: s.shadowEligible ? "#86efac" : "#fca5a5" }}><h2 style={{ marginTop: 0 }}>Shadow readiness: <span style={{ color: s.shadowEligible ? "#047857" : "#b91c1c" }}>{s.shadowEligible ? "ELIGIBLE" : "BLOCKED"}</span></h2><p>Blocked until disputed configuration is resolved, red verification tasks are evidenced, at least one hospital record is verified and an anonymised historical replay passes.</p><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button disabled={busy} style={button} onClick={bootstrap}>Seed or refresh draft</button><button disabled={busy} style={{ ...button, background: "#2563eb" }} onClick={runCoverage}>Assess coverage pool</button></div></section>
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(310px,1fr))", gap: 10 }}>
      <div style={panel}><h2 style={{ marginTop: 0 }}>Theatre-count conflict</h2>{theatreClaims.length ? theatreClaims.map((item: any) => <div key={item.claimRef} style={{ borderTop: "1px solid #e2e8f0", padding: "10px 0" }}><strong>{String(item.claimedValue)} theatres</strong> <Status value={item.status} /><div style={{ color: "#475569", marginTop: 4 }}>{item.sourceType}: {item.notes}</div></div>) : <p>Seed the BVS draft to create the conflicting claims.</p>}</div>
      <div style={panel}><h2 style={{ marginTop: 0 }}>Highest-priority unknowns</h2>{openRed.slice(0, 6).map((item: any) => <div key={item.taskRef} style={{ borderTop: "1px solid #e2e8f0", padding: "9px 0" }}><strong>{item.question}</strong><div style={{ color: "#64748b", fontSize: 13 }}>{item.accountableRole.replaceAll("_", " ")}</div></div>)}</div>
    </section>
    {coverage && <section style={panel}><h2 style={{ marginTop: 0 }}>Coverage capability pool</h2><p>This checks verified role/competency eligibility, not whether people are actually rostered on a shift.</p>{coverage.results?.map((item: any) => <div key={item.requirement.requirementRef} style={{ display: "flex", justifyContent: "space-between", gap: 10, borderTop: "1px solid #e2e8f0", padding: "8px 0" }}><span>{item.requirement.serviceRef} · {item.requirement.roleRef}</span><Status value={item.status} /></div>)}</section>}
  </div>;
}

function Configuration({ data, busy, act }: any) {
  const [answers, setAnswers] = useState<Record<string, { answer: string; evidence: string }>>({});
  async function submitTask(item: any) {
    const entry = answers[item.taskRef] || { answer: "", evidence: "" };
    await act(`/api/bvs-v6/verification-tasks/${item.taskRef}`, { method: "PATCH", body: JSON.stringify({ expectedVersion: item.version, answer: entry.answer, evidenceRefs: entry.evidence ? [entry.evidence] : [], status: entry.evidence ? "verified" : "answered", reason: entry.answer }) }, "Verification response recorded.");
  }
  return <div style={{ display: "grid", gap: 10 }}>
    <section style={panel}><h2 style={{ marginTop: 0 }}>Configuration records</h2><div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><th align="left">Type</th><th align="left">Name</th><th align="left">Status</th><th align="left">Evidence source</th></tr></thead><tbody>{data.configuration.map((item: any) => <tr key={`${item.entityType}:${item.entityRef}`} style={{ borderTop: "1px solid #e2e8f0" }}><td style={{ padding: 8 }}>{item.entityType}</td><td>{item.name}</td><td><Status value={item.verificationStatus} /></td><td>{item.authoritativeSourceRef || "Not verified"}</td></tr>)}</tbody></table></div></section>
    <section style={panel}><h2 style={{ marginTop: 0 }}>Claims requiring judgement</h2>{data.claims.map((item: any) => <div key={item.claimRef} style={{ borderTop: "1px solid #e2e8f0", padding: "10px 0", display: "grid", gap: 5 }}><div><strong>{item.entityRef}.{item.fieldName}: {JSON.stringify(item.claimedValue)}</strong> <Status value={item.status} /></div><div style={{ color: "#475569" }}>{item.notes}</div><div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}><button disabled={busy} style={{ ...button, background: "#b91c1c" }} onClick={() => act(`/api/bvs-v6/claims/${item.claimRef}`, { method: "PATCH", body: JSON.stringify({ expectedVersion: item.version, status: "disputed", notes: "Conflicting evidence remains unresolved", reason: "Retain as disputed pending hospital evidence" }) }, "Claim retained as disputed.")}>Mark disputed</button><button disabled={busy} style={{ ...button, background: "#475569" }} onClick={() => act(`/api/bvs-v6/claims/${item.claimRef}`, { method: "PATCH", body: JSON.stringify({ expectedVersion: item.version, status: "rejected", notes: "Rejected by authorised reviewer", reason: "Hospital review rejected this claim" }) }, "Claim rejected.")}>Reject</button></div></div>)}</section>
    <section style={panel}><h2 style={{ marginTop: 0 }}>Structured BVS verification queue</h2>{data.verificationTasks.map((item: any) => { const value = answers[item.taskRef] || { answer: "", evidence: "" }; return <div key={item.taskRef} style={{ borderTop: "1px solid #e2e8f0", padding: "12px 0", display: "grid", gap: 7 }}><div><strong>{item.question}</strong> <Status value={item.status} /></div><div style={{ color: "#475569" }}>{item.whyItMatters}</div><small>Accountable: {item.accountableRole.replaceAll("_", " ")} · Evidence requested: {item.requestedEvidence}</small><textarea style={{ ...field, minHeight: 65 }} placeholder="Hospital answer" value={value.answer} onChange={event => setAnswers({ ...answers, [item.taskRef]: { ...value, answer: event.target.value } })} /><input style={field} placeholder="Evidence reference, document ID or approved URL" value={value.evidence} onChange={event => setAnswers({ ...answers, [item.taskRef]: { ...value, evidence: event.target.value } })} /><button disabled={busy || !value.answer} style={{ ...button, justifySelf: "start" }} onClick={() => submitTask(item)}>{value.evidence ? "Verify with evidence" : "Record provisional answer"}</button></div>; })}</section>
  </div>;
}

function Workforce({ data, busy, act, coverage, runCoverage }: any) {
  const [form, setForm] = useState({ staffRef: "", displayName: "", primaryRoleRef: "", departmentRef: "", gradeOrTrainingLevel: "", contractedHoursWeekly: "" });
  async function submit(event: FormEvent) { event.preventDefault(); await act(`/api/bvs-v6/workforce/${encodeURIComponent(form.staffRef)}`, { method: "PUT", body: JSON.stringify({ displayName: form.displayName, primaryRoleRef: form.primaryRoleRef, departmentRef: form.departmentRef, gradeOrTrainingLevel: form.gradeOrTrainingLevel || undefined, contractedHoursWeekly: form.contractedHoursWeekly ? Number(form.contractedHoursWeekly) : undefined, sourceStatus: "draft", reason: "Draft workforce profile created for verification" }) }, "Workforce profile created."); setForm({ staffRef: "", displayName: "", primaryRoleRef: "", departmentRef: "", gradeOrTrainingLevel: "", contractedHoursWeekly: "" }); }
  return <div style={{ display: "grid", gap: 10 }}>
    <form onSubmit={submit} style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>Add draft workforce profile</h2><p style={{ margin: 0, color: "#475569" }}>Use an internal stable identifier. A title does not grant privileges; competencies are verified separately.</p><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 8 }}><input required style={field} placeholder="Staff reference" value={form.staffRef} onChange={e => setForm({ ...form, staffRef: e.target.value })} /><input required style={field} placeholder="Display name" value={form.displayName} onChange={e => setForm({ ...form, displayName: e.target.value })} /><input required style={field} placeholder="Primary role reference" value={form.primaryRoleRef} onChange={e => setForm({ ...form, primaryRoleRef: e.target.value })} /><input required style={field} placeholder="Department reference" value={form.departmentRef} onChange={e => setForm({ ...form, departmentRef: e.target.value })} /><input style={field} placeholder="Grade / training level" value={form.gradeOrTrainingLevel} onChange={e => setForm({ ...form, gradeOrTrainingLevel: e.target.value })} /><input style={field} type="number" placeholder="Contracted weekly hours" value={form.contractedHoursWeekly} onChange={e => setForm({ ...form, contractedHoursWeekly: e.target.value })} /></div><button disabled={busy} style={{ ...button, justifySelf: "start" }}>Create profile</button></form>
    <section style={panel}><div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}><h2 style={{ margin: 0 }}>Workforce registry</h2><button style={button} onClick={runCoverage}>Assess eligibility pool</button></div>{data.workforce.length ? data.workforce.map((item: any) => <div key={item.staffRef} style={{ borderTop: "1px solid #e2e8f0", padding: "10px 0" }}><strong>{item.displayName}</strong> · {item.primaryRoleRef} · {item.departmentRef} <Status value={item.sourceStatus} /><div style={{ color: "#64748b" }}>{item.gradeOrTrainingLevel || "Grade unverified"} · {item.contractedHoursWeekly ?? "?"} contracted hours</div></div>) : <p>No local workforce profiles yet.</p>}</section>
    <section style={panel}><h2 style={{ marginTop: 0 }}>Verified competencies</h2>{data.competencies.length ? data.competencies.map((item: any) => <div key={`${item.staffRef}:${item.competencyRef}:${item.scopeRef}`} style={{ borderTop: "1px solid #e2e8f0", padding: 8 }}><strong>{item.staffRef}</strong> · {item.competencyRef} · {item.scopeRef} <Status value={item.status} /></div>) : <p>No competencies verified. Coverage will remain blocked or provisional.</p>}</section>
    {coverage && <section style={panel}><h2 style={{ marginTop: 0 }}>Coverage results</h2>{coverage.results.map((item: any) => <div key={item.requirement.requirementRef} style={{ borderTop: "1px solid #e2e8f0", padding: 8 }}><strong>{item.requirement.serviceRef}: {item.requirement.roleRef}</strong> <Status value={item.status} /><div>{item.candidateCount} eligible profiles; minimum {item.requirement.minimumCount}</div><small>{item.note}</small></div>)}</section>}
  </div>;
}

function Referrals({ data, busy, act }: any) {
  const [form, setForm] = useState({ urgency: "routine", referringPractice: "", patientName: "", species: "Dog", ownerName: "", requestedServiceRef: "", presentingProblem: "", historySummary: "" });
  async function submit(event: FormEvent) { event.preventDefault(); await act("/api/bvs-v6/referrals", { method: "POST", body: JSON.stringify(form) }, "Referral intake created and completeness checked."); setForm({ urgency: "routine", referringPractice: "", patientName: "", species: "Dog", ownerName: "", requestedServiceRef: "", presentingProblem: "", historySummary: "" }); }
  return <div style={{ display: "grid", gap: 10 }}>
    <form onSubmit={submit} style={{ ...panel, display: "grid", gap: 8 }}><h2 style={{ margin: 0 }}>New referral intake</h2><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 8 }}><select style={field} value={form.urgency} onChange={e => setForm({ ...form, urgency: e.target.value })}><option>routine</option><option>urgent</option><option>emergency</option><option>critical</option></select><input required style={field} placeholder="Referring practice" value={form.referringPractice} onChange={e => setForm({ ...form, referringPractice: e.target.value })} /><input required style={field} placeholder="Patient name" value={form.patientName} onChange={e => setForm({ ...form, patientName: e.target.value })} /><input required style={field} placeholder="Species" value={form.species} onChange={e => setForm({ ...form, species: e.target.value })} /><input required style={field} placeholder="Owner name" value={form.ownerName} onChange={e => setForm({ ...form, ownerName: e.target.value })} /><input style={field} placeholder="Requested service" value={form.requestedServiceRef} onChange={e => setForm({ ...form, requestedServiceRef: e.target.value })} /></div><textarea required style={{ ...field, minHeight: 65 }} placeholder="Presenting problem" value={form.presentingProblem} onChange={e => setForm({ ...form, presentingProblem: e.target.value })} /><textarea style={{ ...field, minHeight: 65 }} placeholder="Clinical history summary" value={form.historySummary} onChange={e => setForm({ ...form, historySummary: e.target.value })} /><button disabled={busy} style={{ ...button, justifySelf: "start" }}>Create intake</button></form>
    <section style={panel}><h2 style={{ marginTop: 0 }}>Referral queue</h2>{data.referrals.length ? data.referrals.map((item: any) => <div key={item.referralRef} style={{ borderTop: "1px solid #e2e8f0", padding: "11px 0", display: "grid", gap: 5 }}><div><strong>{item.patientName}</strong> · {item.species} · {item.referringPractice} <Status value={item.status} /></div><div>{item.urgency.toUpperCase()} · {item.requestedServiceRef || "Service not assigned"} · due {item.responseDueAt ? new Date(item.responseDueAt).toLocaleString() : "not set"}</div>{item.missingInformation.length > 0 && <div style={{ color: "#b91c1c" }}>Missing: {item.missingInformation.join(", ")}</div>}<div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>{item.status === "ready_for_clinical_review" && <><button disabled={busy} style={button} onClick={() => act(`/api/bvs-v6/referrals/${item.referralRef}/transition`, { method: "PATCH", body: JSON.stringify({ expectedVersion: item.version, status: "accepted", decision: "accept", decisionReason: "Accepted by authorised clinical reviewer" }) }, "Referral accepted.")}>Accept</button><button disabled={busy} style={{ ...button, background: "#b91c1c" }} onClick={() => act(`/api/bvs-v6/referrals/${item.referralRef}/transition`, { method: "PATCH", body: JSON.stringify({ expectedVersion: item.version, status: "declined", decision: "decline", decisionReason: "Declined by authorised clinical reviewer" }) }, "Referral declined.")}>Decline</button></>}</div></div>) : <p>No referrals created.</p>}</section>
  </div>;
}

function Replay({ data, busy, act }: any) {
  async function sample() {
    const now = new Date(); const iso = (minutes: number) => new Date(now.getTime() + minutes * 60000).toISOString();
    const events = [
      { eventRef: "admission-1", occurredAt: iso(0), eventType: "admission", episodeRef: "anon-001", areaRef: "icu", payload: {} },
      { eventRef: "capacity-1", occurredAt: iso(15), eventType: "capacity", areaRef: "icu", payload: { occupied: 5, safeCapacity: 4, expectedAlert: true, lucyworksDetected: true } },
      { eventRef: "delay-1", occurredAt: iso(30), eventType: "delay", episodeRef: "anon-002", areaRef: "mri", payload: { minutes: 25, expectedAlert: true, lucyworksDetected: true, decisionLatencyMinutes: 7 } },
      { eventRef: "handover-1", occurredAt: iso(60), eventType: "handover", episodeRef: "anon-001", payload: { acknowledged: true } },
    ];
    await act("/api/bvs-v6/historical-replays", { method: "POST", body: JSON.stringify({ sourceDate: now.toISOString().slice(0, 10), dataClassification: "anonymised", events }) }, "Anonymised historical replay analysed.");
  }
  return <div style={{ display: "grid", gap: 10 }}><section style={panel}><h2 style={{ marginTop: 0 }}>Historical-day validation</h2><p>Import anonymised event sequences, compare expected alerts with LucyWorks detection and block shadow mode when red findings remain.</p><button disabled={busy} style={button} onClick={sample}>Run representative replay</button></section><section style={panel}><h2 style={{ marginTop: 0 }}>Replay results</h2>{data.replayRuns.length ? data.replayRuns.map((item: any) => <div key={item.runRef} style={{ borderTop: "1px solid #e2e8f0", padding: "11px 0" }}><div><strong>{item.runRef}</strong> · {item.sourceDate} <Status value={item.status} /></div><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 5, marginTop: 6 }}>{Object.entries(item.metrics || {}).map(([key, value]) => <small key={key}><b>{key.replaceAll(/([A-Z])/g, " $1")}</b>: {String(value)}</small>)}</div>{item.findings?.map((finding: any) => <div key={finding.eventRef} style={{ color: finding.severity === "red" ? "#b91c1c" : "#a16207", marginTop: 5 }}>{finding.severity.toUpperCase()}: {finding.finding}</div>)}</div>) : <p>No historical replays yet.</p>}</section></div>;
}
