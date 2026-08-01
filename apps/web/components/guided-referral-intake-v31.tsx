"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 14, boxShadow: "0 5px 16px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", minHeight: 48, border: "1px solid #64748b", borderRadius: 9, padding: "10px 11px", fontSize: 16, background: "white", color: "#0f172a", boxSizing: "border-box" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "11px 14px", minHeight: 48, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };

type QueueTab = "new" | "identity" | "triage" | "referrals";

const steps = [
  "Patient and duplicate check",
  "Owner and authority",
  "Referral source",
  "Clinical need and urgency",
  "Documents and review",
  "Confirmation and next action",
];

const emptyForm = {
  premisesRef: "default-premises",
  patientName: "",
  species: "dog",
  breed: "",
  sex: "",
  dateOfBirth: "",
  microchipNumber: "",
  ownerName: "",
  ownerEmail: "",
  ownerPhone: "",
  decisionAuthority: true,
  financialResponsibility: true,
  sourceType: "referring_vet",
  sourceOrganisation: "",
  sourceContactName: "",
  sourceContactEmail: "",
  sourceContactPhone: "",
  requestedService: "",
  presentingProblem: "",
  clinicalSummary: "",
  urgency: "routine",
  requestedTimeframe: "",
  documentType: "referral_letter",
  documentFilename: "",
  documentMimeType: "application/pdf",
  documentStorageRef: "",
  documentChecksum: "",
};

export function GuidedReferralIntakeV31() {
  const [tab, setTab] = useState<QueueTab>("new");
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(emptyForm);
  const [referrals, setReferrals] = useState<any[]>([]);
  const [identityIntakes, setIdentityIntakes] = useState<any[]>([]);
  const [triage, setTriage] = useState<any[]>([]);
  const [identityLinks, setIdentityLinks] = useState<Record<string, string>>({});
  const [created, setCreated] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const [referralData, identityData, triageData] = await Promise.all([
        apiGet<{ items: any[] }>("/api/v9/referrals"),
        apiGet<{ items: any[] }>("/api/v12/identity-intakes"),
        apiGet<{ items: any[] }>("/api/v12/triage"),
      ]);
      setReferrals(referralData.items || []);
      setIdentityIntakes(identityData.items || []);
      setTriage(triageData.items || []);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load live referral queues");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const pendingIdentity = useMemo(() => identityIntakes.filter(item => item.intake?.status === "duplicate_review"), [identityIntakes]);
  const openTriage = useMemo(() => triage.filter(row => row.status !== "completed"), [triage]);

  function stepValid(index: number) {
    if (index === 0) return Boolean(form.patientName.trim() && form.species.trim());
    if (index === 1) return Boolean(form.ownerName.trim() && form.decisionAuthority && form.financialResponsibility);
    if (index === 2) return Boolean(form.sourceType.trim());
    if (index === 3) return Boolean(form.requestedService.trim() && form.presentingProblem.trim() && form.clinicalSummary.trim());
    if (index === 4) {
      const anyDocument = Boolean(form.documentFilename || form.documentStorageRef || form.documentChecksum);
      return !anyDocument || Boolean(form.documentFilename && form.documentStorageRef && form.documentChecksum);
    }
    return true;
  }

  async function createReferral() {
    if (!steps.every((_, index) => stepValid(index))) {
      setError("Complete each required stage before confirming the referral.");
      return;
    }
    setBusy(true); setError(""); setMessage(""); setCreated(null);
    try {
      const documents = form.documentFilename ? [{
        documentType: form.documentType,
        filename: form.documentFilename,
        mimeType: form.documentMimeType,
        storageRef: form.documentStorageRef,
        checksumSha256: form.documentChecksum,
        sourceSystem: "manual_intake",
      }] : [];
      const result = await apiJson<any>("/api/v12/referrals/intake", {
        method: "POST",
        body: JSON.stringify({
          premisesRef: form.premisesRef,
          patientName: form.patientName,
          species: form.species,
          breed: form.breed || null,
          sex: form.sex || null,
          dateOfBirth: form.dateOfBirth || null,
          microchipNumber: form.microchipNumber || null,
          ownerName: form.ownerName,
          ownerEmail: form.ownerEmail || null,
          ownerPhone: form.ownerPhone || null,
          decisionAuthority: form.decisionAuthority,
          financialResponsibility: form.financialResponsibility,
          sourceType: form.sourceType,
          sourceOrganisation: form.sourceOrganisation || null,
          sourceContactName: form.sourceContactName || null,
          sourceContactEmail: form.sourceContactEmail || null,
          sourceContactPhone: form.sourceContactPhone || null,
          requestedService: form.requestedService,
          presentingProblem: form.presentingProblem,
          clinicalSummary: form.clinicalSummary,
          urgency: form.urgency,
          requestedTimeframe: form.requestedTimeframe || null,
          documents,
          reason: "Six-stage referral identity, authority, provenance and clinical intake confirmed by verified operator",
        }),
      });
      setCreated(result);
      if (result.requiresIdentityReview) {
        setMessage("Potential duplicate detected. The referral is held for identity review; no duplicate patient was created.");
        setTab("identity");
      } else {
        setMessage(`Referral ${result.referral.referral_ref} created for episode ${result.episode.episode_ref}.`);
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create referral");
    } finally { setBusy(false); }
  }

  async function resolveIdentity(item: any, decision: "link_existing" | "create_new") {
    const intakeRef = item.intake.intake_ref;
    const patientRef = identityLinks[intakeRef]?.trim() || "";
    if (decision === "link_existing" && !patientRef) {
      setError("Enter the verified existing patient reference before linking.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiJson<any>(`/api/v12/identity-intakes/${intakeRef}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          expectedVersion: item.intake.version,
          decision,
          patientRef: patientRef || null,
          reason: decision === "link_existing" ? "Duplicate candidates reviewed and linked to the verified existing patient" : "Duplicate candidates reviewed and confirmed as a new patient",
        }),
      });
      setMessage(`Identity review completed. Referral ${result.referral.referral_ref} is available for triage.`);
      setCreated(result);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Identity resolution failed");
    } finally { setBusy(false); }
  }

  async function updateTriage(row: any, status: "acknowledged" | "completed") {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/v12/triage/${row.triage_ref}`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: row.version,
          status,
          rationale: row.rationale,
          reason: status === "acknowledged" ? "Verified clinician accepted triage responsibility" : "Verified clinician completed referral triage",
        }),
      });
      setMessage(`Triage ${status}.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Triage update failed");
    } finally { setBusy(false); }
  }

  async function decideReferral(row: any, status: "accepted" | "declined" | "more_information_required") {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiJson<any>(`/api/v12/referrals/${row.referral_ref}/decision`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: row.version,
          status,
          reason: status === "accepted" ? "Referral clinically accepted and proposed operational work requested" : `Referral marked ${status} after recorded clinical review`,
        }),
      });
      setMessage(status === "accepted" && result.proposedBlock ? `Accepted and proposed in ${result.proposedBlock.area_name} at ${new Date(result.proposedBlock.starts_at).toLocaleString()}.` : `Referral ${status.replaceAll("_", " ")}.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Referral decision failed");
    } finally { setBusy(false); }
  }

  const tabs: Array<[QueueTab, string]> = [
    ["new", "New referral"],
    ["identity", `Identity review (${pendingIdentity.length})`],
    ["triage", `Triage (${openTriage.length})`],
    ["referrals", `Referral queue (${referrals.length})`],
  ];

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter,system-ui,sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div><span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>GUIDED REFERRAL INTAKE V31</span><h1 style={{ fontSize: "clamp(36px,8vw,70px)", lineHeight: .93, margin: "6px 0" }}>Referral control</h1></div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}><Link href="/hospital-board" style={{ color: "white" }}>Hospital Today</Link><Link href="/workspace" style={{ color: "white" }}>Patient Command</Link></div>
      </div>
      <p style={{ color: "#94a3b8", maxWidth: 920 }}>One staged intake records identity, authority, provenance, urgency and immutable document references before creating canonical hospital work.</p>
    </header>

    <nav aria-label="Referral control sections" style={{ display: "flex", gap: 7, overflowX: "auto", padding: "10px 0" }}>{tabs.map(([key, label]) => <button key={key} style={{ ...button, flex: "0 0 auto", background: tab === key ? "#0f766e" : "#334155" }} onClick={() => setTab(key)}>{label}</button>)}</nav>
    {error && <div aria-live="assertive" style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginBottom: 9 }}>{error}</div>}
    {message && <div aria-live="polite" style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 9 }}>{message}</div>}

    {tab === "new" && <>
      <ol aria-label="Referral intake progress" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 7, listStyle: "none", padding: 0 }}>
        {steps.map((label, index) => <li key={label}><button onClick={() => setStep(index)} style={{ ...button, width: "100%", textAlign: "left", background: index === step ? "#0f766e" : index < step && stepValid(index) ? "#166534" : "#475569" }}>{index + 1}. {label}</button></li>)}
      </ol>
      <section style={{ ...panel, display: "grid", gap: 10 }}>
        <h2 style={{ margin: 0 }}>{step + 1}. {steps[step]}</h2>
        {step === 0 && <><label>Patient name<input style={field} value={form.patientName} onChange={e => setForm({ ...form, patientName: e.target.value })} /></label><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 8 }}><label>Species<select style={field} value={form.species} onChange={e => setForm({ ...form, species: e.target.value })}><option>dog</option><option>cat</option><option>rabbit</option><option>other</option></select></label><label>Breed<input style={field} value={form.breed} onChange={e => setForm({ ...form, breed: e.target.value })} /></label><label>Sex<input style={field} value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })} /></label><label>Date of birth<input type="date" style={field} value={form.dateOfBirth} onChange={e => setForm({ ...form, dateOfBirth: e.target.value })} /></label></div><label>Microchip number<input style={field} value={form.microchipNumber} onChange={e => setForm({ ...form, microchipNumber: e.target.value })} /></label><p style={{ color: "#475569" }}>The server performs duplicate screening before a patient is created.</p></>}
        {step === 1 && <><label>Owner or authorised representative<input style={field} value={form.ownerName} onChange={e => setForm({ ...form, ownerName: e.target.value })} /></label><label>Email<input type="email" style={field} value={form.ownerEmail} onChange={e => setForm({ ...form, ownerEmail: e.target.value })} /></label><label>Telephone<input style={field} value={form.ownerPhone} onChange={e => setForm({ ...form, ownerPhone: e.target.value })} /></label><label style={{ minHeight: 48, display: "flex", alignItems: "center", gap: 9 }}><input type="checkbox" checked={form.decisionAuthority} onChange={e => setForm({ ...form, decisionAuthority: e.target.checked })} />Clinical decision authority confirmed</label><label style={{ minHeight: 48, display: "flex", alignItems: "center", gap: 9 }}><input type="checkbox" checked={form.financialResponsibility} onChange={e => setForm({ ...form, financialResponsibility: e.target.checked })} />Financial responsibility confirmed</label></>}
        {step === 2 && <><label>Premises reference<input style={field} value={form.premisesRef} onChange={e => setForm({ ...form, premisesRef: e.target.value })} /></label><label>Source type<select style={field} value={form.sourceType} onChange={e => setForm({ ...form, sourceType: e.target.value })}><option value="referring_vet">Referring vet</option><option value="owner">Owner</option><option value="internal_transfer">Internal transfer</option><option value="emergency">Emergency presentation</option></select></label><label>Organisation<input style={field} value={form.sourceOrganisation} onChange={e => setForm({ ...form, sourceOrganisation: e.target.value })} /></label><label>Contact name<input style={field} value={form.sourceContactName} onChange={e => setForm({ ...form, sourceContactName: e.target.value })} /></label><label>Contact email<input type="email" style={field} value={form.sourceContactEmail} onChange={e => setForm({ ...form, sourceContactEmail: e.target.value })} /></label><label>Contact telephone<input style={field} value={form.sourceContactPhone} onChange={e => setForm({ ...form, sourceContactPhone: e.target.value })} /></label></>}
        {step === 3 && <><label>Requested service<input style={field} value={form.requestedService} onChange={e => setForm({ ...form, requestedService: e.target.value })} /></label><label>Presenting problem<textarea style={{ ...field, minHeight: 90 }} value={form.presentingProblem} onChange={e => setForm({ ...form, presentingProblem: e.target.value })} /></label><label>Clinical summary<textarea style={{ ...field, minHeight: 120 }} value={form.clinicalSummary} onChange={e => setForm({ ...form, clinicalSummary: e.target.value })} /></label><label>Urgency<select style={field} value={form.urgency} onChange={e => setForm({ ...form, urgency: e.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option><option value="red">Red</option></select></label><label>Requested timeframe<input style={field} value={form.requestedTimeframe} onChange={e => setForm({ ...form, requestedTimeframe: e.target.value })} /></label></>}
        {step === 4 && <><p style={{ color: "#475569" }}>Documents are optional at first contact. When recorded, filename, approved storage reference and SHA-256 checksum are all required.</p><label>Document type<select style={field} value={form.documentType} onChange={e => setForm({ ...form, documentType: e.target.value })}><option value="referral_letter">Referral letter</option><option value="clinical_history">Clinical history</option><option value="diagnostic_report">Diagnostic report</option><option value="image_manifest">Image manifest</option></select></label><label>Filename<input style={field} value={form.documentFilename} onChange={e => setForm({ ...form, documentFilename: e.target.value })} /></label><label>Approved storage reference<input style={field} value={form.documentStorageRef} onChange={e => setForm({ ...form, documentStorageRef: e.target.value })} /></label><label>SHA-256 checksum<input style={field} value={form.documentChecksum} onChange={e => setForm({ ...form, documentChecksum: e.target.value })} /></label></>}
        {step === 5 && <><dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "6px 12px" }}><dt>Patient</dt><dd>{form.patientName} · {form.species}</dd><dt>Owner</dt><dd>{form.ownerName}</dd><dt>Source</dt><dd>{form.sourceType} · {form.sourceOrganisation || "not supplied"}</dd><dt>Service</dt><dd>{form.requestedService}</dd><dt>Urgency</dt><dd>{form.urgency}</dd><dt>Document</dt><dd>{form.documentFilename || "No document recorded at intake"}</dd></dl><p style={{ color: "#475569" }}>Confirming creates a versioned identity intake. Duplicate candidates stop automatic patient creation and move to the identity-review queue.</p><button disabled={busy} style={button} onClick={() => void createReferral()}>Confirm referral and create next action</button></>}
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><button disabled={step === 0} style={{ ...button, background: "#475569" }} onClick={() => setStep(value => Math.max(0, value - 1))}>Back</button>{step < 5 && <button disabled={!stepValid(step)} style={button} onClick={() => setStep(value => Math.min(5, value + 1))}>Review next stage</button>}</div>
      </section>
      {created?.episode?.episode_ref && <section style={{ ...panel, marginTop: 10, borderColor: "#22c55e" }}><h2>Referral created</h2><p>{created.referral?.referral_ref} · {created.episode.episode_ref}</p><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Link href={`/care?episode=${encodeURIComponent(created.episode.episode_ref)}`} style={{ ...button, textDecoration: "none" }}>Open Care Brief</Link><Link href={`/episode-command?episode=${encodeURIComponent(created.episode.episode_ref)}`} style={{ ...button, textDecoration: "none", background: "#2563eb" }}>Open Episode Command</Link><button style={{ ...button, background: "#475569" }} onClick={() => { setForm(emptyForm); setCreated(null); setStep(0); }}>Start another referral</button></div></section>}
    </>}

    {tab === "identity" && <section style={{ display: "grid", gap: 9 }}>{pendingIdentity.length ? pendingIdentity.map(item => { const ref = item.intake.intake_ref; return <article key={ref} style={panel}><h2>{item.intake.patient_name || "Potential duplicate"}</h2><p>{ref} · candidates {item.candidates?.length || 0}</p>{item.candidates?.map((candidate: any) => <p key={candidate.patient_ref}><strong>{candidate.patient_name}</strong> · {candidate.patient_ref} · score {candidate.score}</p>)}<label>Verified existing patient reference<input style={field} value={identityLinks[ref] || ""} onChange={e => setIdentityLinks({ ...identityLinks, [ref]: e.target.value })} /></label><div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}><button disabled={busy} style={button} onClick={() => void resolveIdentity(item, "link_existing")}>Link verified patient</button><button disabled={busy} style={{ ...button, background: "#2563eb" }} onClick={() => void resolveIdentity(item, "create_new")}>Confirm genuinely new patient</button></div></article>; }) : <article style={panel}>No identity reviews are waiting.</article>}</section>}

    {tab === "triage" && <section style={{ display: "grid", gap: 9 }}>{openTriage.length ? openTriage.map(row => <article key={row.triage_ref} style={panel}><h2>{row.patient_name || row.referral_ref}</h2><p>{row.urgency} · {row.status} · due {row.due_at ? new Date(row.due_at).toLocaleString() : "not supplied"}</p><p>{row.rationale}</p><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button disabled={busy || row.status !== "pending"} style={button} onClick={() => void updateTriage(row, "acknowledged")}>Acknowledge responsibility</button><button disabled={busy || row.status === "completed"} style={{ ...button, background: "#2563eb" }} onClick={() => void updateTriage(row, "completed")}>Complete triage</button></div></article>) : <article style={panel}>No triage work is waiting.</article>}</section>}

    {tab === "referrals" && <section style={{ display: "grid", gap: 9 }}>{referrals.length ? referrals.map(row => <article key={row.referral_ref} style={panel}><h2>{row.patient_name || row.referral_ref}</h2><p>{row.requested_service} · {row.urgency} · {row.status}</p><p>{row.presenting_problem || row.clinical_summary}</p><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button disabled={busy || row.status === "accepted"} style={button} onClick={() => void decideReferral(row, "accepted")}>Accept and propose work</button><button disabled={busy} style={{ ...button, background: "#a16207" }} onClick={() => void decideReferral(row, "more_information_required")}>Request information</button><button disabled={busy} style={{ ...button, background: "#991b1b" }} onClick={() => void decideReferral(row, "declined")}>Decline with recorded review</button></div></article>) : <article style={panel}>No referrals are available.</article>}</section>}
  </main>;
}
