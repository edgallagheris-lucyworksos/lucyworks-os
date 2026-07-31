"use client";

import { useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Provider = { provider_ref: string; name: string; status: string; last_test_status: string };
type Adapter = { adapter_ref: string; name: string; adapter_type: string; processing_location: string; status: string; last_test_status: string; version: number };
type TermPack = { pack_ref: string; name: string; release_label: string; status: string; version: number };
type Simulator = { simulator_ref: string; connector_type: string; name: string; status: string; last_test_status: string; version: number };
type Scenario = { scenario_ref: string; simulator_ref: string; scenario_code: string; title: string; fault_type: string; status: string };
type Pilot = {
  pilot_ref: string; name: string; status: string; mode: string; case_limit: number; cases_started: number; version: number;
  operations_approved_by_name?: string | null; clinical_approved_by_name?: string | null; readiness_assessment_ref?: string | null;
};
type Assessment = { assessment_ref: string; overall_status: string; score: number; blockers: string[]; warnings: string[]; assessed_at: string };
type Artifact = { artifact_ref: string; artifact_type: string; generated_at: string; content: Record<string, unknown> };
type Run = { run_ref: string; scenario_ref: string; detection_status: string; result: Record<string, unknown> };
type Incident = { incident_ref: string; pilot_ref: string; severity: string; category: string; status: string; description: string };
type Centre = {
  siteRef: string; speechAdapters: Adapter[]; terminologyPacks: TermPack[]; simulators: Simulator[]; scenarios: Scenario[];
  recentRuns: Run[]; pilots: Pilot[]; openIncidents: Incident[]; readinessAssessments: Assessment[]; artifacts: Artifact[];
  summary: Record<string, number | string>; boundary: string;
};
type V28Centre = { speechProviders: Provider[] };

type RecognitionWindow = Window & { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 14, padding: 14, display: "grid", gap: 10 };
const input: React.CSSProperties = { minHeight: 42, border: "1px solid #94a3b8", borderRadius: 9, padding: "8px 10px", width: "100%", background: "white", color: "#0f172a" };
const button: React.CSSProperties = { minHeight: 40, border: 0, borderRadius: 9, padding: "8px 12px", background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };
const secondary: React.CSSProperties = { ...button, background: "#334155" };
const danger: React.CSSProperties = { ...button, background: "#b91c1c" };

export function HospitalPilotLabV29() {
  const [siteRef, setSiteRef] = useState("");
  const [organisationRef, setOrganisationRef] = useState("");
  const [centre, setCentre] = useState<Centre | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown>>({});
  const [providerRef, setProviderRef] = useState("");
  const [adapterName, setAdapterName] = useState("Referral streaming speech");
  const [adapterType, setAdapterType] = useState("browser");
  const [processingLocation, setProcessingLocation] = useState("device");
  const [simulatorType, setSimulatorType] = useState("patient_management");
  const [simulatorName, setSimulatorName] = useState("Synthetic patient-management system");
  const [selectedSimulator, setSelectedSimulator] = useState("");
  const [faultType, setFaultType] = useState("incorrect_identifier");
  const [selectedPilot, setSelectedPilot] = useState("");
  const [pilotName, setPilotName] = useState("Bounded referral hospital pilot");
  const [accuracy, setAccuracy] = useState("0.94");
  const [reviewSeconds, setReviewSeconds] = useState("180");
  const [baselineSeconds, setBaselineSeconds] = useState("360");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const approvedProvider = useMemo(() => providers.find(item => item.provider_ref === providerRef) || providers.find(item => item.status === "approved"), [providers, providerRef]);
  const currentPilot = useMemo(() => centre?.pilots.find(item => item.pilot_ref === selectedPilot) || centre?.pilots[0], [centre, selectedPilot]);
  const currentSimulator = useMemo(() => centre?.simulators.find(item => item.simulator_ref === selectedSimulator) || centre?.simulators[0], [centre, selectedSimulator]);
  const latestReadiness = centre?.readinessAssessments[0];

  async function load() {
    if (!siteRef.trim()) { setError("Enter the governed site reference."); return; }
    setBusy(true); setError("");
    try {
      const [v29, v28] = await Promise.all([
        apiGet<Centre>(`/api/v29/pilot-lab/control-centre?siteRef=${encodeURIComponent(siteRef.trim())}`),
        apiGet<V28Centre>(`/api/v28/deployment/control-centre?siteRef=${encodeURIComponent(siteRef.trim())}`),
      ]);
      setCentre(v29);
      setProviders(v28.speechProviders);
      const provider = v28.speechProviders.find(item => item.status === "approved");
      if (provider && !providerRef) setProviderRef(provider.provider_ref);
      if (v29.simulators[0] && !selectedSimulator) setSelectedSimulator(v29.simulators[0].simulator_ref);
      if (v29.pilots[0] && !selectedPilot) setSelectedPilot(v29.pilots[0].pilot_ref);
      setMessage("Pilot laboratory state loaded.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load pilot laboratory"); }
    finally { setBusy(false); }
  }

  async function run<T>(work: () => Promise<T>, success: string) {
    setBusy(true); setError("");
    try { const result = await work(); setMessage(success); await load(); return result; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Action failed"); return null; }
    finally { setBusy(false); }
  }

  async function testDevice() {
    const result: Record<string, unknown> = {
      secureContext: window.isSecureContext,
      online: navigator.onLine,
      speechRecognition: Boolean((window as RecognitionWindow).SpeechRecognition || (window as RecognitionWindow).webkitSpeechRecognition),
      mediaDevices: Boolean(navigator.mediaDevices?.getUserMedia),
      userAgent: navigator.userAgent,
      testedAt: new Date().toISOString(),
    };
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const tracks = stream.getAudioTracks();
      result.microphonePermission = "granted";
      result.audioTrackCount = tracks.length;
      result.audioDeviceLabel = tracks[0]?.label || "available";
      tracks.forEach(track => track.stop());
      setMessage("Microphone, browser and network diagnostics captured.");
    } catch (reason) {
      result.microphonePermission = "denied_or_unavailable";
      result.microphoneError = reason instanceof Error ? reason.message : String(reason);
      setError("Microphone access failed. Check browser and operating-system permissions.");
    }
    setDiagnostics(result);
  }

  async function createAdapter() {
    if (!approvedProvider) { setError("Create, test and approve a v28 speech provider first."); return; }
    await run(() => apiPost("/api/v29/pilot-lab/speech/adapters", {
      organisationRef, siteRef, providerRef: approvedProvider.provider_ref, name: adapterName,
      adapterType, processingLocation, protocol: adapterType === "browser" ? "browser_recognition" : "websocket_stream",
      reconnectEnabled: true, maxReconnectAttempts: 5, reconnectBackoffMs: 1000,
      minimumConfidence: 0.78, maximumLatencyMs: 2000,
      networkRequirements: { minimumMbps: 2, maximumJitterMs: 120 }, configuration: { rawAudioRetention: false },
    }), "Streaming speech adapter created in draft state.");
  }

  async function testAdapter(row: Adapter) {
    await run(() => apiPost(`/api/v29/pilot-lab/speech/adapters/${row.adapter_ref}/test`, {
      expectedVersion: row.version, deviceDiagnostics: diagnostics, measuredLatencyMs: 350,
      reason: "Validate microphone, secure context, processing location, latency, reconnect and no-audio-retention controls.",
    }), "Speech adapter test recorded.");
  }

  async function createTerminology() {
    await run(() => apiPost("/api/v29/pilot-lab/terminology-packs", {
      organisationRef, siteRef, name: "UK referral veterinary terminology", releaseLabel: `v${(centre?.terminologyPacks.length || 0) + 1}`,
      language: "en-GB", categories: {}, correctionRules: [], abbreviations: {}, siteTerms: [], evidenceRefs: ["hospital-pilot-lab-v29"],
    }), "Veterinary terminology release created. A different clinical senior must approve it.");
  }

  async function approveTerms(row: TermPack) {
    await run(() => apiPost(`/api/v29/pilot-lab/terminology-packs/${row.pack_ref}/approve`, {
      expectedVersion: row.version, reason: "Clinical review confirms the terminology, medicine-name warnings and correction proposals are suitable for bounded testing.",
    }), "Terminology release approved.");
  }

  async function createSimulator() {
    await run(() => apiPost("/api/v29/pilot-lab/simulators", {
      organisationRef, siteRef, connectorType: simulatorType, name: simulatorName, seed: 29,
      defaultLatencyMs: 50, configuration: { syntheticOnly: true, writeBack: false },
    }), "Synthetic no-write external-system simulator created.");
  }

  async function testSimulator(row: Simulator) {
    await run(() => apiPost(`/api/v29/pilot-lab/simulators/${row.simulator_ref}/test`, {
      expectedVersion: row.version, reason: "Prove synthetic isolation, visible marking, shadow mode and absence of external write capability.",
    }), "Simulator isolation test recorded.");
  }

  async function createScenario() {
    if (!currentSimulator) { setError("Create and test a simulator first."); return; }
    const code = `${faultType}-${Date.now()}`;
    await run(() => apiPost(`/api/v29/pilot-lab/simulators/${currentSimulator.simulator_ref}/scenarios`, {
      scenarioCode: code, title: `${faultType.replaceAll("_", " ")} detection`, faultType,
      eventType: "synthetic_patient_update", eventCount: faultType === "out_of_order" ? 3 : 1,
      parameters: faultType === "delay" ? { delaySeconds: 3600 } : {},
      expectedDetection: "Visible fault, synthetic isolation and reconciliation without canonical patient attachment.", critical: true,
    }), "Deterministic failure scenario created.");
  }

  async function runScenario(row: Scenario) {
    await run(() => apiPost(`/api/v29/pilot-lab/scenarios/${row.scenario_ref}/run`, {
      pilotRef: currentPilot?.pilot_ref || null,
      reason: "Run a controlled synthetic failure injection and prove visible detection without patient-record contamination.",
    }), "Synthetic fault run completed and reconciliation evidence created.");
  }

  async function assessReadiness() {
    await run(() => apiPost("/api/v29/pilot-lab/readiness/assess", {
      siteRef, pilotRef: currentPilot?.pilot_ref || null, deviceDiagnostics: diagnostics,
      backupVerified: true, restoreVerified: true,
    }), "Hospital readiness assessment generated.");
  }

  async function createPilot() {
    if (!approvedProvider || !currentSimulator) { setError("A tested provider and simulator are required."); return; }
    await run(() => apiPost("/api/v29/pilot-lab/pilots", {
      organisationRef, siteRef, name: pilotName, department: "referral", serviceLine: "referral", mode: "synthetic",
      caseLimit: 25, allowedDeviceRefs: [String(diagnostics.audioDeviceLabel || "browser-device")],
      allowedProviderRefs: [approvedProvider.provider_ref], allowedSimulatorRefs: [currentSimulator.simulator_ref],
      successCriteria: { minimumAccuracy: 0.9, minimumAverageSecondsSaved: 60, maximumReconciliationRate: 0.1, redIncidents: 0 },
      stopCriteria: { maxRedIncidents: 0, minimumAccuracy: 0.75, minimumAccuracySamples: 5, maxOpenReconciliation: 3 },
      rollbackPlan: { action: "Stop new pilot activity and return to the existing hospital workflow", urgentAccess: "preserved" },
    }), "Bounded pilot plan created with v24 authority evidence.");
  }

  async function approvePilot(row: Pilot, approvalType: "operations" | "clinical") {
    await run(() => apiPost(`/api/v29/pilot-lab/pilots/${row.pilot_ref}/approve`, {
      expectedVersion: row.version, approvalType,
      reason: `${approvalType} approval confirms scope, case limit, stop thresholds, rollback and urgent-care preservation.`,
    }), `${approvalType} pilot approval recorded.`);
  }

  async function activatePilot(row: Pilot) {
    if (!latestReadiness) { setError("Run readiness assessment first."); return; }
    await run(() => apiPost(`/api/v29/pilot-lab/pilots/${row.pilot_ref}/activate`, {
      expectedVersion: row.version, readinessAssessmentRef: latestReadiness.assessment_ref,
      restrictionsAcknowledged: true, reason: "Activate the independently approved bounded pilot against the recorded readiness assessment.",
    }), "Pilot activated within its recorded limits.");
  }

  async function recordMeasurements(row: Pilot) {
    await run(async () => {
      await apiPost(`/api/v29/pilot-lab/pilots/${row.pilot_ref}/measurements`, {
        synthetic: true, metricType: "transcription_accuracy", value: Number(accuracy), unit: "ratio", metadata: { source: "reviewed transcript comparison" },
      });
      return apiPost(`/api/v29/pilot-lab/pilots/${row.pilot_ref}/measurements`, {
        synthetic: true, metricType: "review_seconds", value: Number(reviewSeconds), unit: "seconds", baselineValue: Number(baselineSeconds),
        metadata: { source: "bounded pilot timing" },
      });
    }, "Accuracy and time-saving measurements recorded; stop thresholds re-evaluated.");
  }

  async function recordRedIncident(row: Pilot) {
    await run(() => apiPost(`/api/v29/pilot-lab/pilots/${row.pilot_ref}/incidents`, {
      severity: "red", category: "synthetic_safety_test", synthetic: true,
      description: "Controlled red pilot incident proving automatic stop behaviour.",
      immediateAction: "Stop new pilot activity, preserve urgent care through the existing workflow and review evidence.",
    }), "Red incident recorded and automatic pilot-stop rule evaluated.");
  }

  async function createExport(kind: "vendor-spec" | "deployment-pack") {
    await run(() => apiPost(`/api/v29/pilot-lab/exports/${kind}`, { siteRef, pilotRef: currentPilot?.pilot_ref || null }), `${kind === "vendor-spec" ? "Vendor integration specification" : "Hospital deployment pack"} generated.`);
  }

  function downloadArtifact(row: Artifact) {
    const blob = new Blob([JSON.stringify(row.content, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `${row.artifact_type}-${row.artifact_ref}.json`; link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 10, fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18, display: "grid", gap: 8 }}>
        <span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>LUCYWORKS V29</span>
        <h1 style={{ margin: 0, fontSize: "clamp(34px,7vw,64px)", lineHeight: .95 }}>Hospital pilot and integration laboratory</h1>
        <p style={{ color: "#b6c2d1", maxWidth: 980, margin: 0 }}>Test real devices, streaming speech, veterinary terminology, synthetic hospital systems, failure handling, readiness, bounded pilot limits and deployment evidence. No vendor write-back or autonomous clinical signing exists here.</p>
      </header>

      <section style={{ ...panel, marginTop: 10, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
        <label>Organisation reference<input style={input} value={organisationRef} onChange={event => setOrganisationRef(event.target.value)} placeholder="organisation-ref" /></label>
        <label>Governed site reference<input style={input} value={siteRef} onChange={event => setSiteRef(event.target.value)} placeholder="site-ref" /></label>
        <button style={button} disabled={busy} onClick={load}>{busy ? "Working…" : "Load pilot laboratory"}</button>
        <button style={secondary} disabled={busy} onClick={testDevice}>Test this device</button>
      </section>

      {error && <p role="alert" style={{ background: "#fee2e2", border: "1px solid #ef4444", padding: 11, borderRadius: 10, fontWeight: 750 }}>{error}</p>}
      {message && <p style={{ background: "#d1fae5", border: "1px solid #10b981", padding: 11, borderRadius: 10, fontWeight: 750 }}>{message}</p>}
      {centre && <p style={{ background: "#fff7ed", border: "1px solid #f97316", padding: 11, borderRadius: 10, fontWeight: 750 }}>{centre.boundary}</p>}

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(330px,1fr))", gap: 10, marginTop: 10 }}>
        <article style={panel}>
          <h2 style={{ margin: 0 }}>1. Device and streaming speech</h2>
          <label>Approved v28 provider<select style={input} value={providerRef} onChange={event => setProviderRef(event.target.value)}><option value="">Select provider</option>{providers.map(row => <option key={row.provider_ref} value={row.provider_ref}>{row.name} · {row.status}</option>)}</select></label>
          <label>Adapter name<input style={input} value={adapterName} onChange={event => setAdapterName(event.target.value)} /></label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <select style={input} value={adapterType} onChange={event => setAdapterType(event.target.value)}><option value="browser">Browser</option><option value="cloud">Cloud</option><option value="private">Hospital hosted</option></select>
            <select style={input} value={processingLocation} onChange={event => setProcessingLocation(event.target.value)}><option value="device">On device</option><option value="cloud">Cloud</option><option value="hospital">Hospital</option></select>
          </div>
          <button style={button} onClick={createAdapter}>Create adapter</button>
          <pre style={{ margin: 0, padding: 9, background: "#f1f5f9", borderRadius: 8, whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(diagnostics, null, 2)}</pre>
          {centre?.speechAdapters.map(row => <div key={row.adapter_ref} style={{ borderTop: "1px solid #e2e8f0", paddingTop: 8 }}><b>{row.name}</b><p>{row.adapter_type} · {row.processing_location} · {row.last_test_status}</p><button style={secondary} onClick={() => testAdapter(row)}>Run adapter test</button></div>)}
        </article>

        <article style={panel}>
          <h2 style={{ margin: 0 }}>2. Veterinary terminology</h2>
          <p>Creates the governed UK referral terminology, medicine-name warning and correction-proposal release.</p>
          <button style={button} onClick={createTerminology}>Create terminology release</button>
          {centre?.terminologyPacks.map(row => <div key={row.pack_ref} style={{ borderTop: "1px solid #e2e8f0", paddingTop: 8 }}><b>{row.name} {row.release_label}</b><p>Status: {row.status}</p>{row.status !== "approved" && <button style={secondary} onClick={() => approveTerms(row)}>Approve as independent clinical senior</button>}</div>)}
        </article>

        <article style={panel}>
          <h2 style={{ margin: 0 }}>3. Hospital-system simulator</h2>
          <select style={input} value={simulatorType} onChange={event => setSimulatorType(event.target.value)}>{["identity","patient_management","laboratory","imaging","pharmacy","insurance","communications"].map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select>
          <input style={input} value={simulatorName} onChange={event => setSimulatorName(event.target.value)} />
          <button style={button} onClick={createSimulator}>Create isolated simulator</button>
          <select style={input} value={selectedSimulator} onChange={event => setSelectedSimulator(event.target.value)}><option value="">Select simulator</option>{centre?.simulators.map(row => <option key={row.simulator_ref} value={row.simulator_ref}>{row.name}</option>)}</select>
          {currentSimulator && <button style={secondary} onClick={() => testSimulator(currentSimulator)}>Test selected simulator</button>}
          <select style={input} value={faultType} onChange={event => setFaultType(event.target.value)}>{["delay","outage","duplicate","conflict","missing_fields","incorrect_identifier","out_of_order"].map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select>
          <button style={button} onClick={createScenario}>Create fault scenario</button>
          {centre?.scenarios.filter(row => !currentSimulator || row.simulator_ref === currentSimulator.simulator_ref).map(row => <div key={row.scenario_ref} style={{ borderTop: "1px solid #e2e8f0", paddingTop: 8 }}><b>{row.title}</b><p>{row.fault_type}</p><button style={secondary} onClick={() => runScenario(row)}>Run synthetic fault</button></div>)}
        </article>

        <article style={panel}>
          <h2 style={{ margin: 0 }}>4. Readiness</h2>
          <button style={button} onClick={assessReadiness}>Run complete readiness assessment</button>
          {latestReadiness ? <div><strong style={{ fontSize: 24 }}>{latestReadiness.overall_status}</strong><p>Score {latestReadiness.score}%</p>{latestReadiness.blockers.length > 0 && <p>Blockers: {latestReadiness.blockers.join(", ")}</p>}{latestReadiness.warnings.length > 0 && <p>Warnings: {latestReadiness.warnings.join(", ")}</p>}</div> : <p>Not assessed.</p>}
        </article>

        <article style={panel}>
          <h2 style={{ margin: 0 }}>5. Bounded pilot authority</h2>
          <input style={input} value={pilotName} onChange={event => setPilotName(event.target.value)} />
          <button style={button} onClick={createPilot}>Create bounded pilot</button>
          <select style={input} value={selectedPilot} onChange={event => setSelectedPilot(event.target.value)}><option value="">Select pilot</option>{centre?.pilots.map(row => <option key={row.pilot_ref} value={row.pilot_ref}>{row.name} · {row.status}</option>)}</select>
          {currentPilot && <>
            <p><b>{currentPilot.name}</b><br />{currentPilot.status} · cases {currentPilot.cases_started}/{currentPilot.case_limit}</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
              <button style={secondary} onClick={() => approvePilot(currentPilot, "operations")}>Operations approve</button>
              <button style={secondary} onClick={() => approvePilot(currentPilot, "clinical")}>Clinical approve</button>
              <button style={button} onClick={() => activatePilot(currentPilot)}>Activate against readiness</button>
            </div>
            <p>Operations: {currentPilot.operations_approved_by_name || "pending"}<br />Clinical: {currentPilot.clinical_approved_by_name || "pending"}</p>
          </>}
        </article>

        <article style={panel}>
          <h2 style={{ margin: 0 }}>6. Measure and stop safely</h2>
          <label>Transcription accuracy<input style={input} value={accuracy} onChange={event => setAccuracy(event.target.value)} inputMode="decimal" /></label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}><label>Review seconds<input style={input} value={reviewSeconds} onChange={event => setReviewSeconds(event.target.value)} /></label><label>Baseline seconds<input style={input} value={baselineSeconds} onChange={event => setBaselineSeconds(event.target.value)} /></label></div>
          {currentPilot && <><button style={button} onClick={() => recordMeasurements(currentPilot)}>Record reviewed measurements</button><button style={danger} onClick={() => recordRedIncident(currentPilot)}>Run red-incident auto-stop proof</button></>}
          {centre?.openIncidents.map(row => <p key={row.incident_ref} style={{ borderLeft: "5px solid #b91c1c", paddingLeft: 8 }}><b>{row.severity}: {row.category}</b><br />{row.description}</p>)}
        </article>

        <article style={panel}>
          <h2 style={{ margin: 0 }}>7. Vendor and hospital packs</h2>
          <button style={button} onClick={() => createExport("vendor-spec")}>Generate vendor specification</button>
          <button style={secondary} onClick={() => createExport("deployment-pack")}>Generate hospital deployment pack</button>
          {centre?.artifacts.map(row => <div key={row.artifact_ref} style={{ borderTop: "1px solid #e2e8f0", paddingTop: 8 }}><b>{row.artifact_type.replaceAll("_", " ")}</b><p>{new Date(row.generated_at).toLocaleString()}</p><button style={secondary} onClick={() => downloadArtifact(row)}>Download JSON evidence pack</button></div>)}
        </article>
      </section>

      {centre && <section style={{ ...panel, marginTop: 10 }}><h2 style={{ margin: 0 }}>Current control summary</h2><pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(centre.summary, null, 2)}</pre></section>}
    </main>
  );
}
