"use client";

import { useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { apiGet, apiPost } from "@/lib/api";

const roles = ["admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor"];

type Context = { organisationRef: string; siteRef: string; premisesRef: string; version: number };
type Site = { siteRef: string; premisesRef: string; name: string; configurationState: string; role: string; isPrimary: boolean };
type Command = { commandRef: string; commandType: string; status: string; patientRef?: string; episodeRef?: string; sourceRoute: string; safetyRecordRef?: string; actor: { name: string; role: string }; createdAt: string };
type Impact = { impactRef: string; impactType: string; severity: string; serviceRef?: string; affectedPatientCount: number; boardSummary: string; ownerRole?: string; createdAt: string };
type Route = { routeKey: string; method: string; legacyPath: string; canonicalCommandType: string; canonicalPath: string; retirementState: string };

type ContextPayload = { context: Context; sites: Site[] };
type ViewPayload = { summary: { activeImpacts: number; openCommands: number; affectedPatients: number; severityCounts: Record<string, number> }; impacts: Impact[]; commands: Command[] };
type ConvergencePayload = { routes: Route[] };

function ContextControl() {
  const [context, setContext] = useState<ContextPayload | null>(null);
  const [view, setView] = useState<ViewPayload | null>(null);
  const [convergence, setConvergence] = useState<ConvergencePayload | null>(null);
  const [commandType, setCommandType] = useState("service_restriction");
  const [summary, setSummary] = useState("");
  const [patientRef, setPatientRef] = useState("");
  const [episodeRef, setEpisodeRef] = useState("");
  const [serviceRef, setServiceRef] = useState("");
  const [severity, setSeverity] = useState("amber");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const [contextData, viewData, convergenceData] = await Promise.all([
        apiGet<ContextPayload>("/api/v26/context"),
        apiGet<ViewPayload>("/api/v26/operational-view"),
        apiGet<ConvergencePayload>("/api/v26/convergence"),
      ]);
      setContext(contextData);
      setView(viewData);
      setConvergence(convergenceData);
      setMessage("");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Unable to load operating context");
    }
  }

  useEffect(() => { void load(); }, []);

  const cards: Array<[string, number]> = useMemo(() => [
    ["Active impacts", view?.summary.activeImpacts || 0],
    ["Affected patients", view?.summary.affectedPatients || 0],
    ["Open commands", view?.summary.openCommands || 0],
    ["Red or critical", (view?.summary.severityCounts.red || 0) + (view?.summary.severityCounts.critical || 0)],
  ], [view]);

  async function createCommand() {
    if (!summary.trim()) {
      setMessage("Summary is required.");
      return;
    }
    try {
      await apiPost("/api/v26/commands", {
        commandType,
        idempotencyKey: `ui-${commandType}-${Date.now()}`,
        payload: {
          summary,
          severity,
          patientRef: patientRef || undefined,
          episodeRef: episodeRef || undefined,
          serviceRef: serviceRef || undefined,
          boardSummary: summary,
        },
      });
      setSummary("");
      setMessage("Canonical command recorded. Human review remains required.");
      await load();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Command failed");
    }
  }

  return (
    <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
        <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>V26 OPERATIONAL CONVERGENCE</span>
        <h1 style={{ margin: "6px 0", fontSize: "clamp(34px,7vw,64px)", lineHeight: .95 }}>One hospital context. One command path.</h1>
        <p style={{ color: "#cbd5e1", maxWidth: 900 }}>Every command is bound to an authorised organisation, site and premises. Legacy URLs are canonicalised, cross-site writes are rejected, and the system records operational protection without making autonomous clinical decisions.</p>
      </header>

      {message && <p role="status" style={{ padding: 10, borderRadius: 10, background: message.includes("required") || message.includes("failed") ? "#fee2e2" : "#dcfce7", fontWeight: 800 }}>{message}</p>}

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 8, marginTop: 10 }}>
        {cards.map(([label, value]) => <article key={label} style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 13, padding: 13 }}><div style={{ color: "#64748b", fontWeight: 800 }}>{label}</div><strong style={{ fontSize: 32 }}>{value}</strong></article>)}
      </section>

      <section style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(310px,1fr))", gap: 10 }}>
        <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 14 }}>
          <h2>Active authority</h2>
          <p><b>Organisation:</b> {context?.context.organisationRef || "—"}</p>
          <p><b>Site:</b> {context?.context.siteRef || "—"}</p>
          <p><b>Premises:</b> {context?.context.premisesRef || "—"}</p>
          <p><b>Context version:</b> {context?.context.version || "—"}</p>
          <h3>Authorised sites</h3>
          {(context?.sites || []).map(site => <div key={site.siteRef} style={{ padding: 9, marginTop: 6, border: "1px solid #e2e8f0", borderRadius: 9 }}><b>{site.name}</b><br />{site.siteRef} · {site.premisesRef}<br /><small>{site.role} · {site.configurationState}</small></div>)}
        </article>

        <article style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 14 }}>
          <h2>Record a governed command</h2>
          <label>Command type<select value={commandType} onChange={event => setCommandType(event.target.value)} style={{ width: "100%", padding: 9, margin: "5px 0 10px" }}>
            {["service_restriction", "equipment_downtime", "medication_supply_delay", "consent_review_request", "estimate_review_request", "discharge_review_request", "safety_escalation"].map(value => <option key={value}>{value}</option>)}
          </select></label>
          <label>Summary<textarea value={summary} onChange={event => setSummary(event.target.value)} rows={3} style={{ width: "100%", padding: 9, margin: "5px 0 10px" }} /></label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
            <label>Patient ref<input value={patientRef} onChange={event => setPatientRef(event.target.value)} style={{ width: "100%", padding: 8 }} /></label>
            <label>Episode ref<input value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} style={{ width: "100%", padding: 8 }} /></label>
            <label>Service ref<input value={serviceRef} onChange={event => setServiceRef(event.target.value)} style={{ width: "100%", padding: 8 }} /></label>
            <label>Severity<select value={severity} onChange={event => setSeverity(event.target.value)} style={{ width: "100%", padding: 8 }}><option>amber</option><option>red</option><option>critical</option></select></label>
          </div>
          <button onClick={() => void createCommand()} style={{ width: "100%", marginTop: 12, padding: 11, border: 0, borderRadius: 9, background: "#0f766e", color: "white", fontWeight: 900 }}>Record command</button>
          <p style={{ color: "#64748b" }}>This creates a hold, task or escalation for a named human. It does not complete consent, discharge, prescribing or treatment.</p>
        </article>
      </section>

      <section style={{ marginTop: 10, background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 14 }}>
        <h2>Active operational impacts</h2>
        {(view?.impacts || []).length === 0 && <p>No active impacts recorded for this site.</p>}
        {(view?.impacts || []).map(item => <article key={item.impactRef} style={{ borderLeft: `7px solid ${item.severity === "critical" || item.severity === "red" ? "#991b1b" : "#d97706"}`, padding: 10, marginTop: 7, background: "#f8fafc" }}><b>{item.impactType.replaceAll("_", " ")}</b> · {item.severity}<br />{item.boardSummary}<br /><small>{item.affectedPatientCount} affected patients · owner {item.ownerRole || "unassigned"} · {item.serviceRef || "no service ref"}</small></article>)}
      </section>

      <section style={{ marginTop: 10, background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 14 }}>
        <h2>Open canonical commands</h2>
        {(view?.commands || []).map(item => <article key={item.commandRef} style={{ padding: 9, borderBottom: "1px solid #e2e8f0" }}><b>{item.commandType.replaceAll("_", " ")}</b> · {item.status}<br /><small>{item.commandRef} · {item.actor.name} ({item.actor.role}) · source {item.sourceRoute}</small></article>)}
      </section>

      <details style={{ marginTop: 10, background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 14 }}>
        <summary style={{ cursor: "pointer", fontWeight: 900, fontSize: 20 }}>Legacy-route convergence register</summary>
        {(convergence?.routes || []).map(item => <p key={item.routeKey}><b>{item.method} {item.legacyPath}</b><br />→ {item.canonicalCommandType} through {item.canonicalPath} · retirement {item.retirementState}</p>)}
      </details>
    </main>
  );
}

export default function OperatingContextPage() {
  return <AuthGuard allowedRoles={roles}><ContextControl /></AuthGuard>;
}
