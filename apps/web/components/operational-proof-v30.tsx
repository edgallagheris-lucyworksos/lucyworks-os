"use client";

import { useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Run = {
  run_ref: string;
  organisation_ref: string;
  site_ref: string;
  premises_ref: string;
  episode_ref?: string | null;
  patient_ref?: string | null;
  status: string;
  current_stage: string;
  passed_count: number;
  blocked_count: number;
  scenario_count: number;
  version: number;
  summary: Record<string, unknown>;
  external_boundaries: string[];
};
type Step = {
  step_ref: string;
  sequence: number;
  step_code: string;
  title: string;
  surface: string;
  expected: string;
  status: string;
  observed: Record<string, unknown>;
  failure_root_cause?: string | null;
  corrective_action?: string | null;
};
type Scenario = {
  scenario_ref: string;
  scenario_code: string;
  title: string;
  expected_detection: string;
  status: string;
  observed: Record<string, unknown>;
};
type MobileAssessment = {
  assessment_ref: string;
  device_label: string;
  status: string;
  manual_hardware_confirmation: boolean;
  limitations: string[];
};
type RunDetail = {
  run: Run;
  steps: Step[];
  scenarios: Scenario[];
  mobileAssessments: MobileAssessment[];
};
type ScenarioDraft = {
  observed: string;
  failureDetected: boolean;
  accountableOwnerVisible: boolean;
  nextActionVisible: boolean;
  evidenceVisible: boolean;
  urgentAccessPreserved: boolean;
};

const initialDraft = (): ScenarioDraft => ({
  observed: "",
  failureDetected: false,
  accountableOwnerVisible: false,
  nextActionVisible: false,
  evidenceVisible: false,
  urgentAccessPreserved: true,
});

const card: React.CSSProperties = {
  background: "white",
  border: "1px solid #cbd5e1",
  borderRadius: 14,
  padding: 14,
};
const input: React.CSSProperties = {
  minHeight: 44,
  border: "1px solid #94a3b8",
  borderRadius: 9,
  padding: "9px 11px",
  fontSize: 16,
  width: "100%",
};
const button: React.CSSProperties = {
  minHeight: 44,
  border: 0,
  borderRadius: 10,
  padding: "10px 14px",
  background: "#0f766e",
  color: "white",
  fontWeight: 850,
  cursor: "pointer",
};

export function OperationalProofV30() {
  const [organisationRef, setOrganisationRef] = useState("");
  const [siteRef, setSiteRef] = useState("");
  const [premisesRef, setPremisesRef] = useState("");
  const [episodeRef, setEpisodeRef] = useState("");
  const [patientRef, setPatientRef] = useState("");
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [scenarioDrafts, setScenarioDrafts] = useState<Record<string, ScenarioDraft>>({});
  const [manualAndroidConfirmation, setManualAndroidConfirmation] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown>>({});
  const [report, setReport] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const run = detail?.run;
  const completeScenarios = useMemo(
    () => detail?.scenarios.filter(item => item.status === "pass").length || 0,
    [detail],
  );

  async function load(runRef: string) {
    const loaded = await apiGet<RunDetail>(`/api/v30/operational-proof/runs/${encodeURIComponent(runRef)}`);
    setDetail(loaded);
    setScenarioDrafts(current => {
      const next = { ...current };
      for (const item of loaded.scenarios) next[item.scenario_code] ||= initialDraft();
      return next;
    });
  }

  async function createRun() {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost<{ run: Run }>("/api/v30/operational-proof/runs", {
        organisationRef: organisationRef.trim(),
        siteRef: siteRef.trim(),
        premisesRef: premisesRef.trim(),
        operationalDate: new Date().toISOString().slice(0, 10),
        mode: "synthetic",
        reason: "Create a governed connected operational proof run.",
      });
      await load(result.run.run_ref);
      setMessage("Proof run created. Attach the canonical episode after starting the synthetic referral journey.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create proof run");
    } finally { setBusy(false); }
  }

  async function attachEpisode() {
    if (!run) return;
    setBusy(true); setError("");
    try {
      const result = await apiPost<{ run: Run }>(
        `/api/v30/operational-proof/runs/${run.run_ref}/attach-episode`,
        {
          expectedVersion: run.version,
          episodeRef: episodeRef.trim(),
          patientRef: patientRef.trim() || null,
          reason: "Bind the proof to the canonical patient and episode.",
        },
      );
      await load(result.run.run_ref);
      setMessage("Canonical episode attached.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to attach episode");
    } finally { setBusy(false); }
  }

  async function evaluateJourney() {
    if (!run) return;
    setBusy(true); setError("");
    try {
      const result = await apiPost<{ run: Run }>(
        `/api/v30/operational-proof/runs/${run.run_ref}/evaluate`,
        {},
      );
      await load(result.run.run_ref);
      setMessage(result.run.blocked_count ? "Connected journey has blocked steps. Correct those paths and rerun." : "Connected journey passed.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to evaluate connected journey");
    } finally { setBusy(false); }
  }

  function updateScenario(code: string, patch: Partial<ScenarioDraft>) {
    setScenarioDrafts(current => ({
      ...current,
      [code]: { ...(current[code] || initialDraft()), ...patch },
    }));
  }

  async function recordScenario(code: string) {
    if (!run) return;
    const draft = scenarioDrafts[code] || initialDraft();
    setBusy(true); setError("");
    try {
      const result = await apiPost<{ run: Run; scenario: Scenario }>(
        `/api/v30/operational-proof/runs/${run.run_ref}/scenarios/${code}`,
        {
          observed: { operatorEvidence: draft.observed.trim() },
          failureDetected: draft.failureDetected,
          accountableOwnerVisible: draft.accountableOwnerVisible,
          nextActionVisible: draft.nextActionVisible,
          evidenceVisible: draft.evidenceVisible,
          urgentAccessPreserved: draft.urgentAccessPreserved,
          reason: `Record controlled ${code} stress evidence.`,
        },
      );
      await load(result.run.run_ref);
      setMessage(`${result.scenario.title}: ${result.scenario.status}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to record stress scenario");
    } finally { setBusy(false); }
  }

  async function runMobileDiagnostics() {
    setError("");
    const values: Record<string, unknown> = {
      secureContext: window.isSecureContext,
      online: navigator.onLine,
      touchCapable: navigator.maxTouchPoints > 0,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      microphoneAvailable: Boolean(navigator.mediaDevices?.getUserMedia),
      operatingSystem: navigator.userAgent,
      browser: navigator.userAgent,
      testedAt: new Date().toISOString(),
    };
    if (navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        values.microphonePermission = "granted";
        values.deviceLabel = stream.getAudioTracks()[0]?.label || "available microphone";
        stream.getTracks().forEach(track => track.stop());
      } catch (reason) {
        values.microphonePermission = "denied_or_unavailable";
        values.microphoneError = reason instanceof Error ? reason.message : String(reason);
      }
    }
    setDiagnostics(values);
    setMessage("Browser diagnostics recorded. They do not replace the physical Android journey.");
  }

  async function saveMobileAssessment() {
    if (!run) return;
    if (!diagnostics.testedAt) {
      setError("Run browser diagnostics first.");
      return;
    }
    setBusy(true); setError("");
    try {
      await apiPost(
        `/api/v30/operational-proof/runs/${run.run_ref}/mobile-assessments`,
        {
          deviceLabel: String(diagnostics.deviceLabel || "browser device"),
          operatingSystem: String(diagnostics.operatingSystem || "unknown"),
          browser: String(diagnostics.browser || "unknown"),
          viewportWidth: Number(diagnostics.viewportWidth || 0),
          viewportHeight: Number(diagnostics.viewportHeight || 0),
          secureContext: Boolean(diagnostics.secureContext),
          online: Boolean(diagnostics.online),
          touchCapable: Boolean(diagnostics.touchCapable),
          microphoneAvailable: Boolean(diagnostics.microphoneAvailable),
          checks: {
            microphonePermission: diagnostics.microphonePermission === "granted",
            noHiddenHorizontalActionArea: document.documentElement.scrollWidth <= window.innerWidth + 2,
            minimumTouchTargets: true,
            keyboardSafeSubmitControls: manualAndroidConfirmation,
            refreshPersistence: manualAndroidConfirmation,
          },
          manualHardwareConfirmation: manualAndroidConfirmation,
          reason: manualAndroidConfirmation
            ? "Named operator completed the physical Android acceptance journey."
            : "Automated browser diagnostics recorded; physical Android confirmation remains outstanding.",
        },
      );
      await load(run.run_ref);
      setMessage(manualAndroidConfirmation ? "Physical Android confirmation recorded." : "Automated diagnostics saved with the manual boundary still open.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save mobile assessment");
    } finally { setBusy(false); }
  }

  async function completeRun() {
    if (!run) return;
    setBusy(true); setError("");
    try {
      const result = await apiPost<{ run: Run }>(
        `/api/v30/operational-proof/runs/${run.run_ref}/complete`,
        {
          expectedVersion: run.version,
          reason: "Complete the recorded connected journey, stress and mobile proof.",
        },
      );
      await load(result.run.run_ref);
      setMessage(`Proof completed: ${result.run.status}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Proof cannot complete");
    } finally { setBusy(false); }
  }

  async function loadReport() {
    if (!run) return;
    setBusy(true); setError("");
    try {
      const result = await apiGet<{ markdown: string }>(
        `/api/v30/operational-proof/runs/${run.run_ref}/report`,
      );
      setReport(result.markdown);
      setMessage("Evidence report loaded.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load evidence report");
    } finally { setBusy(false); }
  }

  return (
    <main style={{ minHeight: "100vh", padding: 12, background: "#e8eef5", color: "#0f172a", fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
        <span style={{ color: "#2dd4bf", fontSize: 12, fontWeight: 900, letterSpacing: ".12em" }}>OPERATIONAL PROOF · V30</span>
        <h1 style={{ fontSize: "clamp(34px,8vw,68px)", lineHeight: .95, margin: "8px 0" }}>Prove the hospital journey</h1>
        <p style={{ color: "#bdc8d6", maxWidth: 900 }}>
          One canonical referral from intake to closure, visible on Patient Command, Hospital Today, accountable role queues and the evidence chain. Synthetic success does not authorise real hospital deployment.
        </p>
      </header>

      {(message || error) && <section style={{ ...card, marginTop: 10, borderColor: error ? "#dc2626" : "#0f766e" }}>
        {error ? <strong style={{ color: "#b91c1c" }}>{error}</strong> : <strong>{message}</strong>}
      </section>}

      <section style={{ ...card, marginTop: 10 }}>
        <h2 style={{ marginTop: 0 }}>1. Create and bind the proof</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 9 }}>
          <label>Organisation reference<input style={input} value={organisationRef} onChange={event => setOrganisationRef(event.target.value)} /></label>
          <label>Site reference<input style={input} value={siteRef} onChange={event => setSiteRef(event.target.value)} /></label>
          <label>Premises reference<input style={input} value={premisesRef} onChange={event => setPremisesRef(event.target.value)} /></label>
        </div>
        <button style={{ ...button, marginTop: 10 }} disabled={busy} onClick={createRun}>Create proof run</button>
        {run && <>
          <p><strong>Run:</strong> <code>{run.run_ref}</code> · <strong>Status:</strong> {run.status} · <strong>Stage:</strong> {run.current_stage}</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 9 }}>
            <label>Canonical episode reference<input style={input} value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} /></label>
            <label>Canonical patient reference<input style={input} value={patientRef} onChange={event => setPatientRef(event.target.value)} /></label>
          </div>
          <button style={{ ...button, marginTop: 10 }} disabled={busy} onClick={attachEpisode}>Attach canonical episode</button>
        </>}
      </section>

      {run && <section style={{ ...card, marginTop: 10 }}>
        <h2 style={{ marginTop: 0 }}>2. Evaluate the connected journey</h2>
        <button style={button} disabled={busy || !run.episode_ref} onClick={evaluateJourney}>Evaluate referral to closure</button>
        <p>{run.passed_count}/12 passed · {run.blocked_count} blocked</p>
        <div style={{ display: "grid", gap: 8 }}>
          {detail?.steps.map(step => <article key={step.step_ref} style={{ border: "1px solid #e2e8f0", borderLeft: `6px solid ${step.status === "pass" ? "#0f766e" : step.status === "blocked" ? "#dc2626" : "#94a3b8"}`, borderRadius: 10, padding: 11 }}>
            <strong>{step.sequence}. {step.title}</strong> <span>— {step.surface}</span>
            <div style={{ fontWeight: 850, marginTop: 5 }}>{step.status.toUpperCase()}</div>
            {step.failure_root_cause && <p style={{ color: "#b91c1c" }}>{step.failure_root_cause}</p>}
            {step.corrective_action && <p>{step.corrective_action}</p>}
          </article>)}
        </div>
      </section>}

      {run && <section style={{ ...card, marginTop: 10 }}>
        <h2 style={{ marginTop: 0 }}>3. Record all eight controlled failures</h2>
        <p>{completeScenarios}/8 passed. A scenario cannot pass unless detection, owner, next action, evidence and urgent access are all confirmed.</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 10 }}>
          {detail?.scenarios.map(scenario => {
            const draft = scenarioDrafts[scenario.scenario_code] || initialDraft();
            return <article key={scenario.scenario_ref} style={card}>
              <h3 style={{ marginTop: 0 }}>{scenario.title}</h3>
              <p>{scenario.expected_detection}</p>
              <p><strong>Recorded status:</strong> {scenario.status}</p>
              <label>Observed evidence
                <textarea style={{ ...input, minHeight: 90 }} value={draft.observed} onChange={event => updateScenario(scenario.scenario_code, { observed: event.target.value })} />
              </label>
              {[
                ["failureDetected", "Failure was detected"],
                ["accountableOwnerVisible", "Accountable owner was visible"],
                ["nextActionVisible", "Next action was visible"],
                ["evidenceVisible", "Evidence/audit record was visible"],
                ["urgentAccessPreserved", "Urgent patient access remained available"],
              ].map(([key, title]) => <label key={key} style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 40 }}>
                <input type="checkbox" checked={Boolean(draft[key as keyof ScenarioDraft])} onChange={event => updateScenario(scenario.scenario_code, { [key]: event.target.checked } as Partial<ScenarioDraft>)} />
                {title}
              </label>)}
              <button style={{ ...button, marginTop: 7 }} disabled={busy || !draft.observed.trim()} onClick={() => recordScenario(scenario.scenario_code)}>Record scenario result</button>
            </article>;
          })}
        </div>
      </section>}

      {run && <section style={{ ...card, marginTop: 10 }}>
        <h2 style={{ marginTop: 0 }}>4. Mobile acceptance</h2>
        <p>Browser diagnostics can prove viewport, security, connectivity, touch and microphone access. They cannot prove physical keyboard overlap or actual Android usability.</p>
        <button style={button} onClick={runMobileDiagnostics}>Test this device</button>
        {Boolean(diagnostics.testedAt) && <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", background: "#f8fafc", padding: 10, borderRadius: 10 }}>{JSON.stringify(diagnostics, null, 2)}</pre>}
        <label style={{ display: "flex", gap: 9, alignItems: "flex-start", marginTop: 10 }}>
          <input type="checkbox" checked={manualAndroidConfirmation} onChange={event => setManualAndroidConfirmation(event.target.checked)} />
          <span><strong>I personally completed the physical Android journey</strong><br />Login → Quick Input → create patient-linked work → find it in Patient Command/Workspace → act → refresh → verify persistence and named audit.</span>
        </label>
        <button style={{ ...button, marginTop: 10 }} disabled={busy || !diagnostics.testedAt} onClick={saveMobileAssessment}>Save mobile evidence</button>
        {detail?.mobileAssessments.map(item => <p key={item.assessment_ref}><strong>{item.device_label}:</strong> {item.status}</p>)}
      </section>}

      {run && <section style={{ ...card, marginTop: 10 }}>
        <h2 style={{ marginTop: 0 }}>5. Complete and export</h2>
        <button style={button} disabled={busy} onClick={completeRun}>Complete governed proof</button>
        <button style={{ ...button, background: "#1d4ed8", marginLeft: 8 }} disabled={busy} onClick={loadReport}>Load evidence report</button>
        {report && <textarea readOnly style={{ ...input, minHeight: 360, marginTop: 10, fontFamily: "ui-monospace, monospace" }} value={report} />}
        <h3>External boundaries</h3>
        <ul>{run.external_boundaries.map(item => <li key={item}>{item}</li>)}</ul>
      </section>}
    </main>
  );
}
