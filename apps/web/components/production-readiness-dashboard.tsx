"use client";

import { useEffect, useMemo, useState } from "react";
import { apiJson, apiPost } from "@/lib/api";

type Control = {
  controlRef: string;
  category: string;
  title: string;
  description: string;
  status: string;
  ownerRole: string;
  evidenceSummary?: string | null;
  verifiedAt?: string | null;
  expiresAt?: string | null;
  version: number;
};

type Pilot = {
  runRef: string;
  phase: string;
  serviceLine: string;
  status: string;
  accountableOwner: string;
  metrics: Record<string, unknown>;
  blockers: unknown[];
};

type Observation = {
  observationRef: string;
  runRef: string;
  severity: string;
  category: string;
  summary: string;
  status: string;
  resolution?: string | null;
};

type Dashboard = {
  gate: {
    shadowEligible: boolean;
    liveEligible: boolean;
    shadowMissing: string[];
    liveMissing: string[];
    openRedObservations: number;
    latestSecurity?: { runRef: string; status: string; score: number } | null;
    byCategory: Record<string, { total: number; passed: number; blocked: number }>;
  };
  controls: Control[];
  pilots: Pilot[];
  observations: Observation[];
  securityRuns: Array<{ runRef: string; status: string; score: number; failedCount: number; warningCount: number; checks: Array<{ title: string; passed: boolean; detail: string; severity: string }> }>;
};

const seniorRoles = ["admin", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "senior_clinician", "supervisor"];

function badge(status: string) {
  if (status === "passed" || status === "resolved") return "#047857";
  if (status === "failed" || status === "blocked" || status === "red") return "#b91c1c";
  if (status === "waived" || status === "amber" || status === "in_progress") return "#a16207";
  return "#475569";
}

export function ProductionReadinessDashboard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [phase, setPhase] = useState("synthetic");
  const [serviceLine, setServiceLine] = useState("neurology");

  async function refresh() {
    try {
      setError("");
      setData(await apiJson<Dashboard>("/api/production-readiness/dashboard", { cache: "no-store" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load production readiness");
    }
  }

  useEffect(() => { void refresh(); }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, Control[]>();
    for (const control of data?.controls || []) map.set(control.category, [...(map.get(control.category) || []), control]);
    return Array.from(map.entries());
  }, [data]);

  async function run(action: string, work: () => Promise<unknown>) {
    try {
      setBusy(action);
      setError("");
      await work();
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Action failed");
    } finally {
      setBusy("");
    }
  }

  async function setControl(control: Control, status: string) {
    const evidenceSummary = window.prompt(`Evidence or reason for ${status}:`, control.evidenceSummary || "") || undefined;
    const waiverReason = status === "waived" ? window.prompt("Named waiver reason:") || undefined : undefined;
    await run(`control-${control.controlRef}`, () => apiJson(`/api/production-readiness/controls/${control.controlRef}`, {
      method: "PATCH",
      body: JSON.stringify({ expectedVersion: control.version, status, evidenceSummary, waiverReason, reason: evidenceSummary }),
    }));
  }

  async function addEvidence(control: Control) {
    const summary = window.prompt("Evidence summary:");
    if (!summary) return;
    const sourceRef = window.prompt("Source/reference, ticket, report or URL label:") || undefined;
    await run(`evidence-${control.controlRef}`, () => apiPost(`/api/production-readiness/controls/${control.controlRef}/evidence`, { evidenceType: "reviewed_evidence", summary, sourceRef }));
  }

  async function createPilot() {
    const accountableOwner = window.prompt("Named accountable owner:");
    if (!accountableOwner) return;
    await run("pilot", () => apiPost("/api/production-readiness/pilots", {
      phase,
      serviceLine,
      accountableOwner,
      startNow: true,
      successCriteria: {
        unresolvedRedObservations: 0,
        lostUpdates: 0,
        criticalWorkflowAccuracyPercent: 100,
        staffAgreementPercent: 95,
      },
    }));
  }

  async function addObservation(pilot: Pilot) {
    const severity = window.prompt("Severity: green, amber or red", "amber") || "amber";
    const summary = window.prompt("What happened?");
    if (!summary) return;
    const expectedBehaviour = window.prompt("What should have happened?") || undefined;
    const actualBehaviour = window.prompt("What actually happened?") || undefined;
    await run(`observation-${pilot.runRef}`, () => apiPost(`/api/production-readiness/pilots/${pilot.runRef}/observations`, { severity, category: "workflow", summary, expectedBehaviour, actualBehaviour }));
  }

  async function resolveObservation(item: Observation) {
    const resolution = window.prompt("Resolution and verification:");
    if (!resolution) return;
    await run(`resolve-${item.observationRef}`, () => apiJson(`/api/production-readiness/observations/${item.observationRef}/resolve`, { method: "PATCH", body: JSON.stringify({ resolution }) }));
  }

  if (!data) return <main style={shell}><h1>Production readiness</h1><p>{error || "Loading…"}</p></main>;

  return <main style={shell}>
    <header style={hero}>
      <div>
        <span style={eyebrow}>LucyWorks OS · governed release</span>
        <h1 style={{ margin: "6px 0", fontSize: "clamp(36px,7vw,68px)", lineHeight: .95 }}>Production readiness</h1>
        <p style={{ color: "#a7b5c8", maxWidth: 850 }}>One evidence-backed gate for deployment, shadow mode and bounded hospital pilots. Code completion cannot override missing hospital controls.</p>
      </div>
      <button style={darkButton} disabled={Boolean(busy)} onClick={() => void refresh()}>Refresh</button>
    </header>

    {error && <p style={errorBox}>{error}</p>}

    <section style={gateGrid}>
      <article style={{ ...gateCard, borderColor: data.gate.shadowEligible ? "#10b981" : "#f59e0b" }}>
        <span style={eyebrow}>Shadow mode</span>
        <strong style={{ fontSize: 30 }}>{data.gate.shadowEligible ? "Eligible" : "Blocked"}</strong>
        <small>{data.gate.shadowMissing.length ? `${data.gate.shadowMissing.length} controls missing` : "Core operational controls passed"}</small>
      </article>
      <article style={{ ...gateCard, borderColor: data.gate.liveEligible ? "#10b981" : "#dc2626" }}>
        <span style={eyebrow}>Live patient care</span>
        <strong style={{ fontSize: 30 }}>{data.gate.liveEligible ? "Eligible" : "Not authorised"}</strong>
        <small>{data.gate.liveMissing.length} controls missing · {data.gate.openRedObservations} open red observations</small>
      </article>
      <article style={gateCard}>
        <span style={eyebrow}>Security assessment</span>
        <strong style={{ fontSize: 30 }}>{data.gate.latestSecurity?.score ?? "—"}</strong>
        <small>{data.gate.latestSecurity?.status || "Not run"}</small>
      </article>
    </section>

    <section style={actions}>
      <button style={button} disabled={Boolean(busy)} onClick={() => void run("bootstrap", () => apiPost("/api/production-readiness/bootstrap", {}))}>Seed controls</button>
      <button style={button} disabled={Boolean(busy)} onClick={() => void run("security", () => apiPost("/api/production-readiness/security/self-test", {}))}>Run security assessment</button>
      <button style={button} disabled={Boolean(busy)} onClick={() => void run("synthetic", () => apiPost("/api/production-readiness/synthetic-hospital/seed", { premisesRef: "synthetic-referral-hospital", confirmation: "CREATE SYNTHETIC DATA" }))}>Create synthetic hospital</button>
      <a style={linkButton} href="/system-control">System control</a>
    </section>

    <section style={section}>
      <h2>Readiness controls</h2>
      {grouped.map(([category, controls]) => <div key={category} style={{ marginTop: 18 }}>
        <h3 style={{ textTransform: "capitalize" }}>{category.replaceAll("_", " ")}</h3>
        <div style={cardGrid}>{controls.map((control) => <article key={control.controlRef} style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
            <b>{control.title}</b>
            <span style={{ ...statusBadge, background: badge(control.status) }}>{control.status.replaceAll("_", " ")}</span>
          </div>
          <p style={muted}>{control.description}</p>
          <small>{control.controlRef} · owner {control.ownerRole} · v{control.version}</small>
          {control.evidenceSummary && <p><b>Evidence:</b> {control.evidenceSummary}</p>}
          <div style={miniActions}>
            <button onClick={() => void setControl(control, "in_progress")}>In progress</button>
            <button onClick={() => void addEvidence(control)}>Add evidence</button>
            <button onClick={() => void setControl(control, "passed")}>Pass</button>
            <button onClick={() => void setControl(control, "blocked")}>Block</button>
          </div>
        </article>)}</div>
      </div>)}
    </section>

    <section style={section}>
      <h2>Start controlled validation</h2>
      <div style={pilotForm}>
        <label>Phase<select value={phase} onChange={(event) => setPhase(event.target.value)}><option value="synthetic">Synthetic</option><option value="historical_replay">Historical replay</option><option value="shadow">Shadow mode</option><option value="bounded_pilot">Bounded pilot</option><option value="scale_up">Scale-up</option></select></label>
        <label>Service line<input value={serviceLine} onChange={(event) => setServiceLine(event.target.value)} /></label>
        <button style={button} onClick={() => void createPilot()}>Create run</button>
      </div>
      <div style={cardGrid}>{data.pilots.map((pilot) => <article key={pilot.runRef} style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><b>{pilot.phase.replaceAll("_", " ")}</b><span style={{ ...statusBadge, background: badge(pilot.status) }}>{pilot.status}</span></div>
        <p>{pilot.serviceLine} · {pilot.accountableOwner}</p>
        <small>{pilot.runRef} · {pilot.blockers.length} blockers</small>
        <div style={miniActions}><button onClick={() => void addObservation(pilot)}>Record observation</button></div>
      </article>)}</div>
    </section>

    <section style={section}>
      <h2>Open observations</h2>
      <div style={cardGrid}>{data.observations.filter((item) => item.status !== "resolved").map((item) => <article key={item.observationRef} style={{ ...card, borderColor: badge(item.severity) }}>
        <span style={{ ...statusBadge, background: badge(item.severity) }}>{item.severity}</span>
        <b>{item.summary}</b>
        <small>{item.category} · {item.runRef}</small>
        <div style={miniActions}><button onClick={() => void resolveObservation(item)}>Resolve with evidence</button></div>
      </article>)}</div>
    </section>

    <section style={section}>
      <h2>Latest security checks</h2>
      {data.securityRuns.slice(0, 1).map((run) => <article key={run.runRef} style={card}>
        <h3>{run.status} · score {run.score}</h3>
        <p>{run.failedCount} failures · {run.warningCount} warnings</p>
        <div style={cardGrid}>{run.checks.map((check) => <div key={check.title} style={{ padding: 10, border: `1px solid ${check.passed ? "#86efac" : "#fca5a5"}`, borderRadius: 10 }}><b>{check.passed ? "PASS" : "FAIL"} · {check.title}</b><p style={muted}>{check.detail}</p></div>)}</div>
      </article>)}
    </section>
  </main>;
}

export { seniorRoles };

const shell: React.CSSProperties = { minHeight: "100vh", padding: 12, background: "#edf2f7", color: "#0f172a", fontFamily: "Inter, system-ui, sans-serif" };
const hero: React.CSSProperties = { display: "flex", justifyContent: "space-between", gap: 18, alignItems: "start", background: "#071019", color: "white", padding: 20, borderRadius: 20 };
const eyebrow: React.CSSProperties = { color: "#2dd4bf", textTransform: "uppercase", letterSpacing: ".12em", fontSize: 11, fontWeight: 900 };
const gateGrid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 10, marginTop: 10 };
const gateCard: React.CSSProperties = { display: "grid", gap: 6, padding: 16, background: "white", border: "2px solid #cbd5e1", borderRadius: 15 };
const section: React.CSSProperties = { marginTop: 12, padding: 16, background: "white", border: "1px solid #cbd5e1", borderRadius: 16 };
const cardGrid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(270px,1fr))", gap: 10 };
const card: React.CSSProperties = { display: "grid", alignContent: "start", gap: 8, padding: 13, border: "1px solid #cbd5e1", borderRadius: 13, background: "#fff" };
const muted: React.CSSProperties = { color: "#475569", margin: 0 };
const statusBadge: React.CSSProperties = { color: "white", borderRadius: 999, padding: "4px 8px", fontSize: 11, fontWeight: 900, alignSelf: "start" };
const actions: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 };
const button: React.CSSProperties = { border: 0, borderRadius: 10, background: "#0f766e", color: "white", padding: "10px 13px", fontWeight: 800, cursor: "pointer" };
const darkButton: React.CSSProperties = { ...button, background: "#1e293b" };
const linkButton: React.CSSProperties = { ...button, textDecoration: "none", background: "#2563eb" };
const miniActions: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 5 };
const pilotForm: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end", marginBottom: 12 };
const errorBox: React.CSSProperties = { padding: 10, background: "#fee2e2", color: "#991b1b", borderRadius: 10 };
