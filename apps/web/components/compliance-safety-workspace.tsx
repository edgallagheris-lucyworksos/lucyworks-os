"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

export const complianceSafetyRoles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 16, padding: 15, boxShadow: "0 5px 18px rgba(15,23,42,.05)", minWidth: 0 };
const button: React.CSSProperties = { border: 0, borderRadius: 10, padding: "10px 14px", minHeight: 44, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };
const grid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,300px),1fr))", gap: 10 };
const muted: React.CSSProperties = { color: "#64748b" };

type Summary = {
  baselineId: string;
  asOfDate: string;
  sources: number;
  obligations: number;
  identityGroups: number;
  vendorContracts: number;
  syntheticPacks: number;
  safetyCase: any | null;
  deploymentProfile: any | null;
  hazards: { total: number; open: number; highResidual: number };
  gates: Record<string, any>;
};

type Baseline = {
  sourceStatuses: Array<{ code: string; meaning: string }>;
  sources: any[];
  obligations: any[];
  identityGroups: any[];
  vendorContracts: any[];
  syntheticDataPacks: any[];
  dpia: any;
  safetyMethodology: any;
};

type SafetyView = { safetyCase: any; hazards: any[]; reviews: any[] };

type Tab = "overview" | "law" | "hazards" | "identity" | "vendors" | "privacy" | "release";

const statusLabel: Record<string, string> = {
  law_in_force: "Law / current regulator guidance",
  binding_professional_duty: "Current professional duty",
  draft_future_requirement: "Draft / future CMA requirement",
  government_policy_proposal: "Government proposal",
  voluntary_standard: "Voluntary standard",
  best_practice_adaptation: "Adapted best practice",
};

function tone(status: string): string {
  if (["law_in_force", "binding_professional_duty", "ready", "synthetic_ready", "approved_for_target"].includes(status)) return "#166534";
  if (["draft_future_requirement", "government_policy_proposal", "blocked", "open"].includes(status)) return "#92400e";
  return "#334155";
}

export function ComplianceSafetyWorkspace() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [safety, setSafety] = useState<SafetyView | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [nextSummary, nextBaseline] = await Promise.all([
        apiGet<Summary>("/api/v10/compliance-safety/summary"),
        apiGet<Baseline>("/api/v10/compliance-safety/baseline"),
      ]);
      setSummary(nextSummary);
      setBaseline(nextBaseline);
      if (nextSummary.safetyCase) setSafety(await apiGet<SafetyView>("/api/v10/compliance-safety/safety-case"));
      else setSafety(null);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load compliance and safety baseline");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function bootstrap() {
    setBusy(true); setMessage(""); setError("");
    try {
      await apiJson("/api/v10/compliance-safety/bootstrap", { method: "POST" });
      setMessage("UK veterinary baseline, reference deployment and hazard log created.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Bootstrap failed");
    } finally { setBusy(false); }
  }

  async function verifyHazard(row: any) {
    const evidence = window.prompt("Evidence references, comma separated:", (row.evidenceRefs || []).join(","));
    if (evidence === null) return;
    const reason = window.prompt("Verification reason:", "Design control and synthetic negative tests reviewed");
    if (!reason) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/v10/compliance-safety/hazards/${row.hazardRef}`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: row.version,
          status: "verified",
          residualSeverity: row.residualSeverity,
          residualLikelihood: row.residualLikelihood,
          controls: row.controls,
          verification: row.verification,
          evidenceRefs: evidence.split(",").map(item => item.trim()).filter(Boolean),
          reason,
        }),
      });
      setMessage(`${row.code} verified against recorded evidence.`);
      await load();
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Hazard verification failed");
    } finally { setBusy(false); }
  }

  const obligationByStatus = useMemo(() => {
    const result: Record<string, any[]> = {};
    for (const row of baseline?.obligations || []) (result[row.status] ||= []).push(row);
    return result;
  }, [baseline]);

  const tabs: Array<[Tab, string]> = [["overview", "Overview"], ["law", "Law & guidance"], ["hazards", "Hazard log"], ["identity", "Identity"], ["vendors", "Vendor contracts"], ["privacy", "DPIA"], ["release", "Release gates"]];

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div><span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>UK VETERINARY ASSURANCE V10</span><h1 style={{ fontSize: "clamp(38px,8vw,72px)", lineHeight: .93, margin: "7px 0" }}>Compliance & safety</h1></div>
        <Link href="/system-control" style={{ color: "white" }}>← System control</Link>
      </div>
      <p style={{ color: "#94a3b8", maxWidth: 980 }}>A machine-readable legal baseline, reference identity model, vendor contracts, DPIA, clinical and operational hazard log, safety case and target-specific release decision. Synthetic validation does not pretend to be hospital approval.</p>
      <button disabled={busy} style={button} onClick={() => void bootstrap()}>{summary?.safetyCase ? "Reconcile baseline" : "Create assurance baseline"}</button>
    </header>

    <nav aria-label="Compliance and safety sections" style={{ display: "flex", gap: 7, overflowX: "auto", padding: "10px 0" }}>{tabs.map(([key, label]) => <button key={key} onClick={() => setTab(key)} style={{ ...button, flex: "0 0 auto", background: tab === key ? "#0f766e" : "#334155" }}>{label}</button>)}</nav>
    {error && <div aria-live="assertive" style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginBottom: 9 }}>{error}</div>}
    {message && <div aria-live="polite" style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 9 }}>{message}</div>}

    {!summary || !baseline ? <section style={panel}>Loading assurance data…</section> : <>
      {tab === "overview" && <div style={{ display: "grid", gap: 10 }}>
        <section style={grid}>
          <Metric title="Current obligations" value={summary.obligations} detail={`Baseline dated ${summary.asOfDate}`} />
          <Metric title="Safety hazards" value={summary.hazards.total} detail={`${summary.hazards.open} open · ${summary.hazards.highResidual} release-blocking`} />
          <Metric title="Reference identity groups" value={summary.identityGroups} detail="Mapped to controlled platform roles" />
          <Metric title="Vendor contracts" value={summary.vendorContracts} detail="PIMS, PACS, LIS, HR, insurance and payments" />
        </section>
        <section style={{ ...panel, borderColor: summary.gates.synthetic?.canRelease ? "#86efac" : "#ef4444" }}>
          <small style={{ ...muted, fontWeight: 850 }}>CURRENT ENGINEERING DECISION</small>
          <h2 style={{ margin: "5px 0" }}>{summary.gates.synthetic?.canRelease ? "Synthetic and historical validation may proceed" : "Synthetic validation is blocked"}</h2>
          <p>{summary.gates.synthetic?.boundary}</p>
          {!summary.safetyCase && <p><strong>The policy catalogue exists, but the persisted safety case has not yet been bootstrapped.</strong></p>}
        </section>
        <section style={grid}>
          {Object.entries(statusLabel).map(([status, label]) => <article key={status} style={panel}><strong style={{ color: tone(status) }}>{label}</strong><div style={{ fontSize: 34, fontWeight: 950 }}>{(obligationByStatus[status] || []).length}</div><p style={muted}>{baseline.sourceStatuses.find(row => row.code === status)?.meaning}</p></article>)}
        </section>
        {summary.safetyCase && <section style={panel}><small style={{ ...muted, fontWeight: 850 }}>SAFETY CASE</small><h2>{summary.safetyCase.title}</h2><p>{summary.safetyCase.safetyStatement}</p><p><strong>Status:</strong> {summary.safetyCase.status} · release {summary.safetyCase.releaseVersion} · version {summary.safetyCase.version}</p></section>}
      </div>}

      {tab === "law" && <section style={{ display: "grid", gap: 10 }}>{Object.entries(obligationByStatus).map(([status, rows]) => <div key={status} style={{ display: "grid", gap: 8 }}><h2 style={{ color: tone(status), marginBottom: 0 }}>{statusLabel[status] || status}</h2>{rows.map(row => <article key={row.code} style={panel}><div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong>{row.code} · {row.domain}</strong><span style={{ color: tone(row.status), fontWeight: 850 }}>{statusLabel[row.status]}</span></div><p>{row.requirement}</p><small style={muted}>Controls: {row.controls.join(" · ")} · Sources: {row.sourceIds.join(", ")}</small></article>)}</div>)}</section>}

      {tab === "hazards" && <section style={{ display: "grid", gap: 8 }}>{!safety ? <article style={panel}>Create the assurance baseline to generate the hazard log.</article> : safety.hazards.map(row => <article key={row.hazardRef} style={{ ...panel, borderColor: row.residualRisk >= 16 ? "#ef4444" : row.residualRisk >= 10 ? "#f59e0b" : "#86efac" }}><div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><div><strong style={{ fontSize: 20 }}>{row.code} · {row.title}</strong><p style={{ margin: "5px 0" }}>{row.hazardousSituation}</p></div><div style={{ textAlign: "right" }}><strong>Initial {row.initialRisk}</strong><br/><strong>Residual {row.residualRisk}</strong></div></div><p><strong>Potential harm:</strong> {row.potentialHarm}</p><p><strong>Controls:</strong> {row.controls.join(" · ")}</p><p><strong>Verification:</strong> {row.verification.join(" · ")}</p><small style={muted}>Owner {row.ownerRole} · {row.status} · version {row.version}</small><div style={{ marginTop: 8 }}><button disabled={busy || row.status === "verified"} style={{ ...button, background: row.status === "verified" ? "#64748b" : "#0f766e" }} onClick={() => void verifyHazard(row)}>Record verification</button></div></article>)}</section>}

      {tab === "identity" && <section style={grid}>{baseline.identityGroups.map(row => <article key={row.group} style={panel}><strong style={{ fontSize: 19 }}>{row.group}</strong><p>{row.purpose}</p><p><strong>Platform role:</strong> {row.platformRole}</p><small style={muted}>Capabilities: {row.capabilities.join(" · ")}{row.constraints?.length ? ` · Constraints: ${row.constraints.join(" · ")}` : ""}</small></article>)}</section>}

      {tab === "vendors" && <section style={{ display: "grid", gap: 9 }}>{baseline.vendorContracts.map(row => <article key={row.systemType} style={panel}><h2 style={{ marginTop: 0 }}>{row.systemType}</h2><p><strong>Minimum contract:</strong> {row.required.join(" · ")}</p><p><strong>Safety rules:</strong> {row.rules.join(" · ")}</p></article>)}</section>}

      {tab === "privacy" && <section style={{ display: "grid", gap: 10 }}><article style={{ ...panel, borderColor: "#f59e0b" }}><strong style={{ color: "#92400e" }}>{baseline.dpia.status.replaceAll("_", " ")}</strong><p>This is a complete controller-ready baseline, not a false signature by an organisation that has not deployed the system.</p></article><section style={grid}>{baseline.dpia.dataClasses.map((row: any) => <article key={row.class} style={panel}><strong>{row.class.replaceAll("_", " ")}</strong><p>Personal: {String(row.personal)} · Special category: {String(row.specialCategory)}</p><p>{row.minimise}</p></article>)}</section><article style={panel}><h2>High-risk processing</h2><p>{baseline.dpia.highRisks.join(" · ")}</p><h2>Built-in mitigations</h2><p>{baseline.dpia.mitigations.join(" · ")}</p><h2>Deployment-controller decisions</h2><p>{baseline.dpia.controllerDecisions.join(" · ")}</p></article></section>}

      {tab === "release" && <section style={{ display: "grid", gap: 9 }}>{Object.entries(summary.gates).map(([target, gate]: [string, any]) => <article key={target} style={{ ...panel, borderColor: gate.canRelease ? "#86efac" : "#ef4444" }}><div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><h2 style={{ margin: 0, textTransform: "capitalize" }}>{target.replaceAll("_", " ")}</h2><strong style={{ color: gate.canRelease ? "#166534" : "#991b1b" }}>{gate.canRelease ? "RELEASE GATE PASSED" : "BLOCKED"}</strong></div><p>{gate.boundary}</p>{gate.blockers?.map((item: any) => <div key={`${target}-${item.code}`} style={{ borderLeft: "5px solid #ef4444", paddingLeft: 9, marginTop: 7 }}><strong>{item.code}</strong><div>{item.detail}</div></div>)}</article>)}</section>}
    </>}
  </main>;
}

function Metric({ title, value, detail }: { title: string; value: number; detail: string }) {
  return <article style={panel}><small style={{ ...muted, fontWeight: 850 }}>{title.toUpperCase()}</small><div style={{ fontSize: 39, fontWeight: 950 }}>{value}</div><p style={{ ...muted, marginBottom: 0 }}>{detail}</p></article>;
}
