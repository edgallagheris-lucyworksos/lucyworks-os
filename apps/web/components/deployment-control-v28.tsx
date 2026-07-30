"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Provider = {
  provider_ref: string; name: string; provider_type: string; status: string; version: number;
  last_test_status: string; supports_streaming: boolean; supports_word_confidence: boolean;
};
type Connector = {
  connector_ref: string; connector_type: string; vendor_name: string; environment: string;
  mode: string; status: string; version: number; last_test_status: string; stale: boolean;
};
type Reconciliation = {
  item_ref: string; connector_ref: string; event_ref: string; external_ref: string;
  status: string; severity: string; reason: string; version: number;
};
type SpeechSession = {
  session_ref: string; provider_ref: string; status: string; version: number; segment_count: number;
  transcript_text: string; quality_summary: Record<string, unknown>; linked_capture_ref?: string | null;
};
type Centre = {
  siteRef: string;
  speechProviders: Provider[];
  speechSessions: SpeechSession[];
  connectors: Connector[];
  openReconciliation: Reconciliation[];
  summary: Record<string, number>;
  boundary: string;
};
type RecognitionResultEvent = Event & {
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string; confidence?: number } }>;
  resultIndex: number;
};
type RecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: Event & { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type RecognitionConstructor = new () => RecognitionLike;

const connectorTypes = ["identity", "patient_management", "laboratory", "imaging", "pharmacy", "insurance", "communications"];

export function DeploymentControlV28() {
  const [siteRef, setSiteRef] = useState("");
  const [organisationRef, setOrganisationRef] = useState("");
  const [centre, setCentre] = useState<Centre | null>(null);
  const [providerName, setProviderName] = useState("Hospital browser speech");
  const [providerType, setProviderType] = useState("browser");
  const [providerHost, setProviderHost] = useState("");
  const [connectorType, setConnectorType] = useState("patient_management");
  const [vendorName, setVendorName] = useState("");
  const [connectorHost, setConnectorHost] = useState("");
  const [episodeRef, setEpisodeRef] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [speechSession, setSpeechSession] = useState<SpeechSession | null>(null);
  const [partial, setPartial] = useState("");
  const [recording, setRecording] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown>>({});
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const recognitionRef = useRef<RecognitionLike | null>(null);
  const sessionRef = useRef("");
  const sessionVersion = useRef(0);
  const sequence = useRef(0);
  const appendQueue = useRef<Promise<void>>(Promise.resolve());

  const recognitionAvailable = useMemo(() => {
    if (typeof window === "undefined") return false;
    const candidate = window as typeof window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };
    return Boolean(candidate.SpeechRecognition || candidate.webkitSpeechRecognition);
  }, []);

  async function load() {
    if (!siteRef.trim()) { setError("Enter the governed site reference."); return; }
    setBusy(true); setError("");
    try {
      const result = await apiGet<Centre>(`/api/v28/deployment/control-centre?siteRef=${encodeURIComponent(siteRef.trim())}`);
      setCentre(result);
      const approved = result.speechProviders.find(item => item.status === "approved");
      if (approved && !selectedProvider) setSelectedProvider(approved.provider_ref);
      setMessage("Current deployment state loaded.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load deployment control"); }
    finally { setBusy(false); }
  }

  async function createProvider() {
    setBusy(true); setError("");
    try {
      await apiPost("/api/v28/deployment/speech/providers", {
        organisationRef: organisationRef.trim(), siteRef: siteRef.trim(), name: providerName.trim(),
        providerType, endpointHost: providerHost.trim() || null, processingRegion: "GB", language: "en-GB",
        supportsStreaming: true, supportsDiarization: false, supportsWordTimestamps: providerType !== "browser",
        supportsWordConfidence: true, rawAudioRetention: false, configuration: {},
      });
      setMessage("Speech provider created in draft state. Test it before approval.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create speech provider"); }
    finally { setBusy(false); }
  }

  async function providerAction(provider: Provider, action: "test" | "approve") {
    setBusy(true); setError("");
    try {
      await apiPost(`/api/v28/deployment/speech/providers/${provider.provider_ref}/${action}`, {
        expectedVersion: provider.version,
        reason: action === "test" ? "Run device, privacy and configuration checks." : "Approve the independently tested speech provider.",
      });
      setMessage(action === "test" ? "Provider test recorded." : "Provider approved for governed sessions.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : `Unable to ${action} provider`); }
    finally { setBusy(false); }
  }

  async function createConnector() {
    setBusy(true); setError("");
    try {
      await apiPost("/api/v28/deployment/connectors", {
        organisationRef: organisationRef.trim(), siteRef: siteRef.trim(), connectorType,
        vendorName: vendorName.trim(), environment: "sandbox", endpointHost: connectorHost.trim() || null,
        staleAfterSeconds: 900, configuration: {},
      });
      setMessage("Connector registered disabled. It cannot read or write until tested and independently promoted.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create connector"); }
    finally { setBusy(false); }
  }

  async function connectorAction(connector: Connector, action: "test" | "promote") {
    setBusy(true); setError("");
    try {
      if (action === "test") {
        await apiPost(`/api/v28/deployment/connectors/${connector.connector_ref}/test`, {
          expectedVersion: connector.version, reason: "Validate sandbox endpoint, secret presence and no-write policy.",
        });
        setMessage("Connector test recorded. No vendor write was attempted.");
      } else {
        await apiPost(`/api/v28/deployment/connectors/${connector.connector_ref}/promotions`, {
          expectedVersion: connector.version, requestedMode: "shadow",
          reason: "Request bounded no-write shadow operation.", evidenceRefs: ["deployment-control-v28"],
        });
        setMessage("Shadow promotion requested. A different senior user must approve it.");
      }
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : `Unable to ${action} connector`); }
    finally { setBusy(false); }
  }

  async function runDeviceTest() {
    setError(""); setMessage("Testing microphone access and browser capability.");
    const result: Record<string, unknown> = {
      secureContext: window.isSecureContext,
      online: navigator.onLine,
      speechRecognition: recognitionAvailable,
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
      setMessage(recognitionAvailable ? "Microphone and browser transcription are available." : "Microphone works, but this browser has no live SpeechRecognition API.");
    } catch (reason) {
      result.microphonePermission = "denied_or_unavailable";
      result.microphoneError = reason instanceof Error ? reason.message : String(reason);
      setError("Microphone access failed. Check browser and operating-system permissions.");
    }
    setDiagnostics(result);
  }

  function buildRecognition() {
    const candidate = window as typeof window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };
    const Constructor = candidate.SpeechRecognition || candidate.webkitSpeechRecognition;
    if (!Constructor) throw new Error("This browser does not expose live speech recognition.");
    const recognition = new Constructor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-GB";
    recognition.onresult = event => {
      let interim = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result.isFinal) { interim += result[0].transcript; continue; }
        const text = result[0].transcript.trim();
        if (!text) continue;
        const nextSequence = ++sequence.current;
        const expectedVersion = sessionVersion.current;
        appendQueue.current = appendQueue.current.then(async () => {
          const appended = await apiPost<{ session: SpeechSession }>(`/api/v28/deployment/speech/sessions/${sessionRef.current}/segments`, {
            expectedVersion: sessionVersion.current || expectedVersion,
            sequence: nextSequence,
            text,
            confidence: typeof result[0].confidence === "number" ? result[0].confidence : null,
            isFinal: true,
            source: "browser",
            words: [],
          });
          sessionVersion.current = appended.session.version;
          setSpeechSession(appended.session);
        }).catch(reason => {
          setError(reason instanceof Error ? reason.message : "A speech segment could not be saved");
          recognitionRef.current?.stop();
        });
      }
      setPartial(interim);
    };
    recognition.onerror = event => {
      setRecording(false);
      setError(`Browser transcription stopped${event.error ? `: ${event.error}` : "."} The saved session can be resumed.`);
    };
    recognition.onend = () => { setRecording(false); setPartial(""); };
    return recognition;
  }

  async function startSpeech() {
    if (!selectedProvider || !episodeRef.trim()) { setError("Select an approved provider and enter a canonical episode reference."); return; }
    setBusy(true); setError(""); setDraft(null);
    try {
      const started = await apiPost<{ session: SpeechSession }>("/api/v28/deployment/speech/sessions", {
        providerRef: selectedProvider, siteRef: siteRef.trim(), episodeRef: episodeRef.trim(),
        captureMode: "consultation_transcription", language: "en-GB",
        noticeVersion: "v28-device-test", noticeAcknowledged: true, rawAudioRetained: false,
        deviceDiagnostics: diagnostics,
      });
      sessionRef.current = started.session.session_ref;
      sessionVersion.current = started.session.version;
      sequence.current = started.session.segment_count;
      setSpeechSession(started.session);
      const recognition = buildRecognition();
      recognitionRef.current = recognition;
      recognition.start();
      setRecording(true);
      setMessage("Governed speech session started. Final segments are saved as they arrive; raw audio is not retained by LucyWorks.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to start governed speech session"); }
    finally { setBusy(false); }
  }

  async function interruptSpeech() {
    if (!speechSession) return;
    recognitionRef.current?.stop();
    await appendQueue.current;
    try {
      const result = await apiPost<{ session: SpeechSession }>(`/api/v28/deployment/speech/sessions/${speechSession.session_ref}/interrupt`, {
        expectedVersion: sessionVersion.current, reason: "User stopped or device/network interruption recorded from deployment control.",
      });
      sessionVersion.current = result.session.version;
      setSpeechSession(result.session); setRecording(false); setMessage("Session interrupted safely. Saved segments remain available.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to interrupt session"); }
  }

  async function resumeSpeech() {
    if (!speechSession) return;
    setError("");
    try {
      const result = await apiPost<{ session: SpeechSession }>(`/api/v28/deployment/speech/sessions/${speechSession.session_ref}/resume`, {
        expectedVersion: sessionVersion.current, reason: "User resumed after checking the microphone and connection.",
      });
      sessionVersion.current = result.session.version;
      setSpeechSession(result.session);
      const recognition = buildRecognition(); recognitionRef.current = recognition; recognition.start(); setRecording(true);
      setMessage("Session resumed. Sequence numbering continues from the saved transcript.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to resume session"); }
  }

  async function completeSpeech() {
    if (!speechSession) return;
    recognitionRef.current?.stop();
    await appendQueue.current;
    setBusy(true); setError("");
    try {
      const result = await apiPost<{ session: SpeechSession; draft: Record<string, unknown> }>(`/api/v28/deployment/speech/sessions/${speechSession.session_ref}/complete`, {
        expectedVersion: sessionVersion.current, reason: "Complete the captured transcript and create a proposed human-review draft.",
      });
      sessionVersion.current = result.session.version;
      setSpeechSession(result.session); setDraft(result.draft); setRecording(false);
      setMessage("Speech session completed. A proposed v19 draft exists, but nothing is signed until an authorised user reviews and confirms it.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to complete speech session"); }
    finally { setBusy(false); }
  }

  useEffect(() => () => recognitionRef.current?.stop(), []);

  const approvedProviders = centre?.speechProviders.filter(item => item.status === "approved") || [];

  return <main className="dc">
    <style>{css}</style>
    <header><span>LUCYWORKS OS · V28</span><h1>Real hospital connection control</h1><p>Test speech devices, approve transcription providers, stage hospital integrations and reconcile uncertain data without external write-back.</p></header>

    <section className="context">
      <label>Organisation reference<input value={organisationRef} onChange={event => setOrganisationRef(event.target.value)} placeholder="organisation-ref" /></label>
      <label>Site reference<input value={siteRef} onChange={event => setSiteRef(event.target.value)} placeholder="site-ref" /></label>
      <button onClick={() => void load()} disabled={busy || !siteRef.trim()}>Load control centre</button>
    </section>

    {centre ? <>
      <section className="summary">{Object.entries(centre.summary).map(([key, value]) => <article key={key}><b>{value}</b><span>{key.replaceAll(/([A-Z])/g, " $1")}</span></article>)}</section>
      <p className="boundary">{centre.boundary}</p>

      <section className="grid">
        <article className="panel"><h2>Speech providers</h2><div className="form"><input value={providerName} onChange={event => setProviderName(event.target.value)} placeholder="Provider name" /><select value={providerType} onChange={event => setProviderType(event.target.value)}><option value="browser">Browser</option><option value="cloud">Cloud</option><option value="private">Private / hospital hosted</option></select><input value={providerHost} onChange={event => setProviderHost(event.target.value)} placeholder="Endpoint host for external providers" /><button onClick={() => void createProvider()} disabled={busy || !organisationRef.trim() || !providerName.trim()}>Create draft provider</button></div>{centre.speechProviders.map(provider => <div className="record" key={provider.provider_ref}><b>{provider.name}</b><span>{provider.provider_type} · {provider.status} · test {provider.last_test_status}</span><div><button onClick={() => void providerAction(provider, "test")} disabled={busy}>Test</button><button onClick={() => void providerAction(provider, "approve")} disabled={busy || provider.last_test_status !== "passed"}>Approve</button></div></div>)}</article>

        <article className="panel"><h2>Hospital connectors</h2><div className="form"><select value={connectorType} onChange={event => setConnectorType(event.target.value)}>{connectorTypes.map(item => <option key={item}>{item}</option>)}</select><input value={vendorName} onChange={event => setVendorName(event.target.value)} placeholder="Vendor / system name" /><input value={connectorHost} onChange={event => setConnectorHost(event.target.value)} placeholder="Endpoint host" /><button onClick={() => void createConnector()} disabled={busy || !organisationRef.trim() || !vendorName.trim()}>Register disabled connector</button></div>{centre.connectors.map(connector => <div className={`record ${connector.stale ? "danger" : ""}`} key={connector.connector_ref}><b>{connector.vendor_name}</b><span>{connector.connector_type} · {connector.environment} · {connector.status} · {connector.mode}{connector.stale ? " · STALE" : ""}</span><div><button onClick={() => void connectorAction(connector, "test")} disabled={busy}>Test</button><button onClick={() => void connectorAction(connector, "promote")} disabled={busy || connector.last_test_status !== "passed" || connector.status === "active"}>Request shadow</button></div></div>)}</article>
      </section>

      <section className="panel speech"><h2>Real-device governed speech test</h2><p>This sends final transcript segments, confidence and diagnostics. It does not upload or retain raw audio.</p><div className="speech-controls"><select value={selectedProvider} onChange={event => setSelectedProvider(event.target.value)}><option value="">Select approved provider</option>{approvedProviders.map(provider => <option value={provider.provider_ref} key={provider.provider_ref}>{provider.name}</option>)}</select><input value={episodeRef} onChange={event => setEpisodeRef(event.target.value)} placeholder="Canonical EP-..." /><button onClick={() => void runDeviceTest()}>Test microphone</button>{!speechSession ? <button className="primary" onClick={() => void startSpeech()} disabled={busy || !recognitionAvailable}>Start governed speech</button> : null}{speechSession?.status === "active" ? <button className="stop" onClick={() => void interruptSpeech()}>Interrupt safely</button> : null}{speechSession?.status === "interrupted" ? <button className="primary" onClick={() => void resumeSpeech()}>Resume</button> : null}{speechSession && ["active", "interrupted"].includes(speechSession.status) ? <button onClick={() => void completeSpeech()} disabled={busy || speechSession.segment_count < 1}>Complete to review draft</button> : null}</div><pre>{JSON.stringify(diagnostics, null, 2)}</pre>{speechSession ? <div className="session"><b>{speechSession.status} · {speechSession.segment_count} saved segment(s)</b><p>{speechSession.transcript_text || partial || "Listening…"}</p>{partial ? <small>Live interim: {partial}</small> : null}</div> : null}{draft ? <pre>{JSON.stringify(draft, null, 2)}</pre> : null}</section>

      <section className="panel"><h2>Open reconciliation</h2>{centre.openReconciliation.length ? centre.openReconciliation.map(item => <div className={`record ${item.severity === "red" ? "danger" : ""}`} key={item.item_ref}><b>{item.external_ref}</b><span>{item.reason}</span><small>{item.connector_ref} · {item.event_ref} · {item.severity}</small></div>) : <p>No unresolved patient or episode matches.</p>}</section>
    </> : null}

    <div className="messages" aria-live="polite">{message ? <p>{message}</p> : null}{error ? <p className="error">{error}</p> : null}</div>
  </main>;
}

const css = `
.dc{min-height:100vh;background:#e9eef5;color:#0f172a;padding:10px;font-family:Inter,system-ui,sans-serif}.dc *{box-sizing:border-box}.dc>header{background:#071019;color:white;border-radius:18px;padding:18px}.dc>header span{color:#2dd4bf;font-weight:950;letter-spacing:.12em;font-size:11px}.dc h1{font-size:clamp(36px,7vw,68px);line-height:.94;letter-spacing:-.055em;margin:7px 0}.dc>header p{color:#b6c2d1;max-width:900px}.context,.speech-controls{display:flex;gap:8px;flex-wrap:wrap;align-items:end;background:white;border:1px solid #cbd5e1;border-radius:14px;padding:11px;margin-top:9px}.dc label,.form{display:grid;gap:4px;font-size:12px;font-weight:900}.dc input,.dc select{min-height:44px;border:1px solid #94a3b8;border-radius:9px;padding:8px;background:white;color:#0f172a}.dc button{min-height:44px;border:1px solid #475569;border-radius:9px;padding:8px 12px;background:white;color:#0f172a;font-weight:900;cursor:pointer}.dc button.primary,.context button{background:#0f766e;color:white;border-color:#0f766e}.dc button.stop{background:#b91c1c;color:white;border-color:#b91c1c}.dc button:disabled{opacity:.5;cursor:not-allowed}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-top:9px}.summary article{display:grid;background:white;border:1px solid #cbd5e1;border-radius:12px;padding:10px}.summary b{font-size:30px}.summary span{text-transform:capitalize;color:#64748b}.boundary{background:#fffbeb;color:#92400e;border:1px solid #f59e0b;border-radius:10px;padding:10px;font-weight:850}.grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.panel{background:white;border:1px solid #cbd5e1;border-radius:14px;padding:12px;margin-top:9px}.panel h2{margin:0 0 8px;font-size:25px}.form{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border-bottom:1px solid #e2e8f0;padding-bottom:9px}.record{display:grid;gap:4px;border:1px solid #e2e8f0;border-left:6px solid #0f766e;border-radius:9px;padding:8px;margin-top:7px}.record.danger{border-left-color:#dc2626;background:#fff1f2}.record span,.record small{color:#64748b}.record>div{display:flex;gap:6px;flex-wrap:wrap}.speech p{color:#475569}.session{border:1px solid #0f766e;background:#f0fdfa;border-radius:10px;padding:10px;margin-top:8px}.session p{white-space:pre-wrap;color:#0f172a}.dc pre{white-space:pre-wrap;overflow:auto;background:#071019;color:#dbeafe;border-radius:10px;padding:10px;max-height:280px}.messages{position:sticky;bottom:6px;margin-top:9px}.messages p{background:#dcfce7;color:#166534;border:1px solid #86efac;border-radius:10px;padding:9px}.messages p.error{background:#fee2e2;color:#991b1b;border-color:#fca5a5}@media(max-width:800px){.grid{grid-template-columns:1fr}.context>* ,.speech-controls>*{flex:1 1 100%}.dc{padding:6px}.dc>header{padding:14px}}
`;
