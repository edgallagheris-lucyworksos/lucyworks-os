"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type CaptureMode = "clinical_dictation" | "consultation_transcription" | "voice_command" | "typed_predictive";
type Suggestion = { id: string; type: string; value: any; sourceText: string; confidence: number };
type SpeechResponse = {
  capture: { capture_ref: string; status: string; version: number; transcript_text: string; redacted_transcript_text?: string | null };
  draft: {
    draft_ref: string;
    status: string;
    version: number;
    proposed_sections: Record<string, string>;
    suggestions: Suggestion[];
    negations: Suggestion[];
    uncertainties: Suggestion[];
    medication_proposals: Suggestion[];
    observations: Suggestion[];
    task_proposals: Suggestion[];
  };
  context: { episodeRef: string; patientRef: string; patientName: string; phase: string };
  medicationFoundationLink?: string;
  boundary?: string;
};
type RecognitionResultEvent = Event & {
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
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

const sectionLabels: Record<string, string> = {
  presenting_complaint: "Presenting complaint",
  history: "History",
  examination: "Examination",
  assessment: "Assessment",
  plan: "Plan",
  owner_discussion: "Owner discussion",
};

function confidence(value: number) {
  if (value >= 0.9) return "high";
  if (value >= 0.75) return "medium";
  return "low";
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

export function SpeechCaptureV19({
  episodeRef,
  mode = "clinical_dictation",
  createClinicalNote = true,
  compact = false,
  onConfirmed,
}: {
  episodeRef: string;
  mode?: CaptureMode;
  createClinicalNote?: boolean;
  compact?: boolean;
  onConfirmed?: (result: any) => void;
}) {
  const [captureMode, setCaptureMode] = useState<CaptureMode>(mode);
  const [transcript, setTranscript] = useState("");
  const [partial, setPartial] = useState("");
  const [notice, setNotice] = useState(false);
  const [recording, setRecording] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [response, setResponse] = useState<SpeechResponse | null>(null);
  const [sections, setSections] = useState<Record<string, string>>({});
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [acceptedTasks, setAcceptedTasks] = useState<Set<string>>(new Set());
  const [terms, setTerms] = useState<Array<{ term: string; type: string; source: string }>>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const recognitionRef = useRef<RecognitionLike | null>(null);

  const recognitionAvailable = useMemo(() => {
    if (typeof window === "undefined") return false;
    const candidate = window as typeof window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };
    return Boolean(candidate.SpeechRecognition || candidate.webkitSpeechRecognition);
  }, []);

  const lastTerm = useMemo(() => {
    const match = transcript.trim().match(/([A-Za-z][A-Za-z-]{1,40})$/);
    return match?.[1] || "";
  }, [transcript]);

  useEffect(() => {
    if (lastTerm.length < 2) { setTerms([]); return; }
    const timer = window.setTimeout(async () => {
      try {
        const result = await apiGet<{ items: Array<{ term: string; type: string; source: string }> }>(`/api/v19/speech/terms?q=${encodeURIComponent(lastTerm)}`);
        setTerms(result.items.slice(0, 8));
      } catch {
        setTerms([]);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [lastTerm]);

  useEffect(() => () => recognitionRef.current?.stop(), []);

  function startRecording() {
    setError(""); setStatus("");
    if (!episodeRef.trim()) { setError("Open or enter a patient episode before dictating."); return; }
    if (!notice) { setError("Acknowledge the recording and privacy notice first."); return; }
    const candidate = window as typeof window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };
    const Constructor = candidate.SpeechRecognition || candidate.webkitSpeechRecognition;
    if (!Constructor) { setError("Live browser transcription is unavailable here. Type or paste the transcript instead."); return; }
    const recognition = new Constructor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-GB";
    recognition.onresult = event => {
      let finalText = "";
      let interimText = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) finalText += `${result[0].transcript} `;
        else interimText += result[0].transcript;
      }
      if (finalText) setTranscript(current => `${current}${current.trim() ? " " : ""}${finalText.trim()}`);
      setPartial(interimText);
    };
    recognition.onerror = event => {
      setError(`Microphone transcription stopped${event.error ? `: ${event.error}` : "."}`);
      setRecording(false);
    };
    recognition.onend = () => { setRecording(false); setPartial(""); };
    recognitionRef.current = recognition;
    recognition.start();
    setRecording(true);
    setStatus("Recording and transcribing. Raw audio is not retained by LucyWorks.");
  }

  function stopRecording() {
    recognitionRef.current?.stop();
    setRecording(false);
    setPartial("");
    setStatus("Recording stopped. Review the transcript before creating a structured draft.");
  }

  function insertTerm(term: string) {
    setTranscript(current => current.replace(/([A-Za-z][A-Za-z-]{1,40})$/, term));
    setTerms([]);
  }

  async function createDraft() {
    if (!episodeRef.trim()) { setError("Episode reference is required."); return; }
    if (!notice) { setError("Acknowledge the recording and privacy notice first."); return; }
    if (!transcript.trim()) { setError("Record, type or paste a transcript first."); return; }
    setBusy(true); setError(""); setStatus("Extracting proposed structured fields"); setReviewed(false);
    try {
      const result = await apiPost<SpeechResponse>("/api/v19/speech/captures", {
        episodeRef: episodeRef.trim(),
        captureMode,
        sourceType: recognitionAvailable ? "browser_speech_or_typed" : "typed",
        transcript: transcript.trim(),
        language: "en-GB",
        noticeVersion: "v19-default",
        noticeAcknowledged: true,
        rawAudioRetained: false,
      });
      setResponse(result);
      setSections(result.draft.proposed_sections || {});
      setAccepted(new Set(result.draft.suggestions.filter(item => item.type === "section" || item.type === "observation").map(item => item.id)));
      setAcceptedTasks(new Set());
      setStatus(`Draft ready for ${result.context.patientName}. Transcript remains separate until confirmation.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Speech capture failed");
    } finally { setBusy(false); }
  }

  function toggleSuggestion(id: string) {
    setAccepted(current => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleTask(id: string) {
    setAcceptedTasks(current => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    setAccepted(current => new Set(current).add(id));
  }

  async function confirm() {
    if (!response || !reviewed) return;
    setBusy(true); setError(""); setStatus("Writing reviewed record and accepted work");
    const allIds = response.draft.suggestions.map(item => item.id);
    try {
      const result = await apiPost<any>(`/api/v19/speech/captures/${response.capture.capture_ref}/confirm`, {
        expectedCaptureVersion: response.capture.version,
        expectedDraftVersion: response.draft.version,
        finalSections: sections,
        acceptedSuggestionIds: [...accepted],
        rejectedSuggestionIds: allIds.filter(id => !accepted.has(id)),
        acceptedTaskIds: [...acceptedTasks],
        createClinicalNote,
        noteType: captureMode === "consultation_transcription" ? "consultation" : "clinical_dictation",
        noteTitle: createClinicalNote ? "Reviewed veterinary speech capture" : "Reviewed operational speech capture",
        reason: "Responsible user reviewed transcript, edited the structured draft and explicitly confirmed accepted content",
      });
      setStatus(createClinicalNote
        ? `Confirmed. Signed note created${result.workItems?.length ? ` and ${result.workItems.length} owned task(s) added` : ""}.`
        : `Confirmed. ${result.workItems?.length || 0} owned task(s) created; no clinical note was written.`);
      setResponse(current => current ? { ...current, capture: result.capture, draft: result.draft } : current);
      onConfirmed?.(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Confirmation failed");
    } finally { setBusy(false); }
  }

  const suggestions = response?.draft.suggestions || [];
  const medications = response?.draft.medication_proposals || [];
  const uncertainties = response?.draft.uncertainties || [];
  const negations = response?.draft.negations || [];
  const tasks = response?.draft.task_proposals || [];
  const confirmed = response?.capture.status === "confirmed";

  return <section className={`sp ${compact ? "compact" : ""}`}>
    <style>{css}</style>
    <header className="sp-head"><div><span>LUCYWORKSAI · GOVERNED SPEECH V19</span><h2>{createClinicalNote ? "Dictate, review, confirm" : "Speak, review, create owned work"}</h2><p>Speech becomes a proposed draft. The transcript, edits and final confirmation remain separate evidence.</p></div><b className={recording ? "recording" : "idle"}>{recording ? "● RECORDING" : "MIC READY"}</b></header>

    <div className="identity"><b>Episode</b><span>{episodeRef || "No episode selected"}</span>{response?.context ? <><b>Patient</b><span>{response.context.patientName} · {label(response.context.phase)}</span></> : null}</div>

    {!response ? <>
      <div className="settings">
        <label>Capture mode<select value={captureMode} onChange={event => setCaptureMode(event.target.value as CaptureMode)}><option value="clinical_dictation">Clinical dictation</option><option value="consultation_transcription">Consultation transcription</option><option value="voice_command">Low-risk work capture</option><option value="typed_predictive">Typed predictive wording</option></select></label>
        <label className="notice"><input type="checkbox" checked={notice} onChange={event => setNotice(event.target.checked)} /><span>I have followed the organisation recording notice and lawful-basis process. Raw audio retention is off.</span></label>
      </div>
      <div className="mic-row"><button className={recording ? "stop" : "primary"} onClick={recording ? stopRecording : startRecording} disabled={!episodeRef.trim()}>{recording ? "Stop recording" : recognitionAvailable ? "Start microphone" : "Microphone unavailable"}</button><button onClick={() => { setTranscript(""); setPartial(""); }}>Clear</button></div>
      <label>Source transcript<textarea rows={compact ? 6 : 10} value={transcript} onChange={event => setTranscript(event.target.value)} placeholder="Dictate, type or paste the veterinary consultation or operational update." /></label>
      {partial ? <div className="partial" aria-live="polite">Live: {partial}</div> : null}
      {terms.length ? <div className="terms" aria-label="Predictive veterinary wording">{terms.map(item => <button key={`${item.type}-${item.term}`} onClick={() => insertTerm(item.term)}><b>{item.term}</b><small>{item.type} · {item.source}</small></button>)}</div> : null}
      <button className="primary" disabled={busy || !episodeRef.trim() || !transcript.trim() || !notice} onClick={() => void createDraft()}>{busy ? "Creating draft…" : "Create structured draft"}</button>
    </> : <>
      <div className="boundary">{response.boundary || "Nothing enters the verified record until an authorised user confirms it."}</div>
      <div className="review-grid">
        <article><h3>Source transcript</h3><p>{response.capture.redacted_transcript_text || response.capture.transcript_text}</p><small>Original transcript retained as evidence · raw audio not retained</small></article>
        <article><h3>Reviewed clinical sections</h3>{Object.keys(sectionLabels).map(key => <label key={key}>{sectionLabels[key]}<textarea rows={3} value={sections[key] || ""} onChange={event => setSections(current => ({ ...current, [key]: event.target.value }))} /></label>)}</article>
      </div>

      {(negations.length || uncertainties.length) ? <div className="signals"><div><h3>Negation preserved</h3>{negations.length ? negations.map(item => <span key={item.id}>{String(item.value)}</span>) : <small>None detected</small>}</div><div><h3>Uncertainty highlighted</h3>{uncertainties.length ? uncertainties.map(item => <span key={item.id}>{String(item.value)}</span>) : <small>None detected</small>}</div></div> : null}

      <div className="suggestions"><h3>Proposed structured fields</h3>{suggestions.map(item => <label className={`suggestion ${confidence(item.confidence)}`} key={item.id}><input type="checkbox" checked={accepted.has(item.id)} onChange={() => toggleSuggestion(item.id)} /><span><b>{label(item.type)} · {Math.round(item.confidence * 100)}%</b><small>{item.type === "medication_proposal" ? `${item.value.productName} · ${item.value.doseExpression || "dose not heard"} · ${item.value.routeExpression || "route not heard"}` : item.sourceText}</small></span></label>)}</div>

      {medications.length ? <div className="meds"><h3>Medication proposals only</h3>{medications.map(item => <article key={item.id}><b>{item.value.productName}</b><span>{item.value.doseExpression || "No dose extracted"} · {item.value.routeExpression || "No route extracted"} · {item.value.frequencyExpression || "No frequency extracted"}</span><small>{item.value.boundary}</small></article>)}{response.medicationFoundationLink ? <Link href={response.medicationFoundationLink}>Open deterministic Medication Safety</Link> : null}</div> : null}

      {tasks.length ? <div className="tasks"><h3>Work proposals</h3>{tasks.map(item => <label key={item.id}><input type="checkbox" checked={acceptedTasks.has(item.id)} onChange={() => toggleTask(item.id)} /><span><b>{item.value.title}</b><small>{label(item.value.ownerRole)} · {item.value.sectionName} · {item.value.urgency.toUpperCase()}</small></span></label>)}</div> : null}

      {!confirmed ? <label className="notice confirm"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} /><span>I have compared the transcript with this draft, corrected errors, and selected only content that should enter the record or work queue.</span></label> : null}
      {!confirmed ? <div className="confirm-row"><button onClick={() => { setResponse(null); setReviewed(false); }} disabled={busy}>Return to transcript</button><button className="primary" disabled={busy || !reviewed} onClick={() => void confirm()}>{busy ? "Confirming…" : createClinicalNote ? "Confirm signed note and work" : "Confirm owned work"}</button></div> : <div className="confirmed">Confirmed by the verified reviewer. Refresh persistence is available through the capture record.</div>}
    </>}

    <div aria-live="polite" className="messages">{status ? <p>{status}</p> : null}{error ? <p className="error">{error}</p> : null}</div>
  </section>;
}

const css = `
.sp{display:grid;gap:10px;background:#f8fafc;border:1px solid #cbd5e1;border-radius:16px;padding:12px;color:#0f172a;font-family:Inter,system-ui,sans-serif}.sp *{box-sizing:border-box}.sp-head{display:flex;justify-content:space-between;gap:12px;background:#071019;color:white;border-radius:13px;padding:13px}.sp-head span{font-size:10px;letter-spacing:.12em;color:#2dd4bf;font-weight:950}.sp-head h2{margin:4px 0;font-size:28px}.sp-head p{margin:0;color:#b6c2d1}.sp-head>b{height:max-content;border-radius:999px;padding:7px 10px;font-size:10px}.sp-head .recording{background:#fee2e2;color:#991b1b}.sp-head .idle{background:#dcfce7;color:#166534}.identity{display:grid;grid-template-columns:max-content 1fr;gap:5px 10px;border:1px solid #cbd5e1;background:white;border-radius:10px;padding:9px}.identity b{color:#475569}.settings{display:grid;grid-template-columns:minmax(180px,280px) 1fr;gap:9px}.sp label{display:grid;gap:4px;font-size:12px;font-weight:900}.sp textarea,.sp select{width:100%;border:1px solid #94a3b8;border-radius:9px;padding:9px;background:white;color:#0f172a;font:inherit;font-weight:500}.notice{grid-template-columns:22px 1fr!important;align-items:start;background:white;border:1px solid #cbd5e1;border-radius:10px;padding:9px}.notice input,.suggestion input,.tasks input{width:20px;height:20px}.mic-row,.confirm-row{display:flex;gap:8px;flex-wrap:wrap}.sp button,.sp a{min-height:44px;border:1px solid #64748b;border-radius:9px;background:white;color:#0f172a;padding:9px 12px;font-weight:900;text-decoration:none;cursor:pointer}.sp button.primary,.sp a{background:#0f766e;color:white;border-color:#0f766e}.sp button.stop{background:#b91c1c;color:white;border-color:#b91c1c}.sp button:disabled{opacity:.5;cursor:not-allowed}.partial{border-left:5px solid #0ea5e9;background:#eff6ff;padding:8px}.terms{display:flex;gap:6px;overflow:auto}.terms button{display:grid;text-align:left;min-width:160px}.terms small{font-weight:500;color:#64748b}.boundary{border:1px solid #f59e0b;background:#fffbeb;color:#92400e;border-radius:9px;padding:9px;font-weight:800}.review-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.review-grid>article,.signals>div,.suggestions,.meds,.tasks{display:grid;gap:7px;background:white;border:1px solid #cbd5e1;border-radius:11px;padding:10px}.review-grid h3,.signals h3,.suggestions h3,.meds h3,.tasks h3{margin:0}.review-grid article:first-child p{white-space:pre-wrap;line-height:1.5}.review-grid small,.suggestion small,.meds small,.tasks small{color:#64748b}.signals{display:grid;grid-template-columns:1fr 1fr;gap:9px}.signals span{border-left:5px solid #f59e0b;background:#fffbeb;padding:7px}.suggestion,.tasks label{grid-template-columns:22px 1fr;align-items:start;border:1px solid #e2e8f0;border-radius:8px;padding:8px}.suggestion span,.tasks span,.meds article{display:grid;gap:3px}.suggestion.low{border-color:#ef4444;background:#fff1f2}.suggestion.medium{border-color:#f59e0b}.meds{border-color:#f59e0b}.meds article{border-bottom:1px solid #e2e8f0;padding-bottom:7px}.confirm{border-color:#0f766e;background:#f0fdfa}.confirmed{border:1px solid #22c55e;background:#f0fdf4;color:#166534;border-radius:9px;padding:10px;font-weight:900}.messages p{margin:0;color:#166534}.messages .error{color:#b91c1c}.sp.compact .sp-head h2{font-size:22px}@media(max-width:760px){.sp{padding:7px}.sp-head,.settings{grid-template-columns:1fr;display:grid}.review-grid,.signals{grid-template-columns:1fr}.mic-row button,.confirm-row button{flex:1}.sp-head h2{font-size:24px}}
`;
