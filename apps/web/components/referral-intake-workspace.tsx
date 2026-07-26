"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

const panel: React.CSSProperties = { background: "white", border: "1px solid #cbd5e1", borderRadius: 15, padding: 14, boxShadow: "0 5px 16px rgba(15,23,42,.05)" };
const field: React.CSSProperties = { width: "100%", minHeight: 46, border: "1px solid #94a3b8", borderRadius: 9, padding: "9px 10px", fontSize: 16, background: "white", color: "#0f172a", boxSizing: "border-box" };
const button: React.CSSProperties = { border: 0, borderRadius: 9, padding: "10px 13px", minHeight: 46, background: "#0f766e", color: "white", fontWeight: 850, cursor: "pointer" };

type Tab = "intake" | "identity" | "triage" | "referrals";

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

export function ReferralIntakeWorkspace() {
  const [tab, setTab] = useState<Tab>("intake");
  const [form, setForm] = useState(emptyForm);
  const [referrals, setReferrals] = useState<any[]>([]);
  const [identityIntakes, setIdentityIntakes] = useState<any[]>([]);
  const [triage, setTriage] = useState<any[]>([]);
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
      setReferrals(referralData.items);
      setIdentityIntakes(identityData.items);
      setTriage(triageData.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load referral control data");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function createReferral() {
    setBusy(true); setError(""); setMessage(""); setCreated(null);
    try {
      const documents = form.documentFilename && form.documentStorageRef && form.documentChecksum ? [{
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
          reason: "Referral identity, authority, provenance and clinical intake recorded by verified operator",
        }),
      });
      setCreated(result);
      if (result.requiresIdentityReview) {
        setMessage("Potential duplicate detected. Referral creation is held until identity review is completed.");
        setTab("identity");
      } else {
        setMessage(`Canonical referral ${result.referral.referral_ref} and episode ${result.episode.episode_ref} created.`);
        setForm(emptyForm);
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create referral identity intake");
    } finally { setBusy(false); }
  }

  async function resolveIdentity(intake: any, decision: "link_existing" | "create_new", patientRef?: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiJson<any>(`/api/v12/identity-intakes/${intake.intake.intake_ref}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          expectedVersion: intake.intake.version,
          decision,
          patientRef: patientRef || null,
          reason: decision === "link_existing" ? "Potential duplicate reviewed and linked to the selected existing patient" : "Potential matches reviewed and confirmed as a genuinely new patient",
        }),
      });
      setMessage(`Identity resolved. Referral ${result.referral.referral_ref} created.`);
      setCreated(result);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Identity resolution failed");
    } finally { setBusy(false); }
  }

  async function updateTriage(row: any, status: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/v12/triage/${row.triage_ref}`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: row.version,
          status,
          rationale: row.rationale,
          reason: status === "acknowledged" ? "Clinician accepted triage responsibility" : "Clinical referral triage completed",
        }),
      });
      setMessage(`Triage ${status}.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Triage update failed");
    } finally { setBusy(false); }
  }

  async function decideReferral(row: any, status: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiJson<any>(`/api/v12/referrals/${row.referral_ref}/decision`, {
        method: "PATCH",
        body: JSON.stringify({
          expectedVersion: row.version,
          status,
          reason: status === "accepted" ? "Referral clinically accepted; create a proposed operational block" : `Referral marked ${status} after clinical review`,
        }),
      });
      setMessage(status === "accepted" && result.proposedBlock ? `Accepted and proposed in ${result.proposedBlock.area_name} at ${new Date(result.proposedBlock.starts_at).toLocaleString()}.` : `Referral ${status}.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Referral decision failed");
    } finally { setBusy(false); }
  }

  const pendingIdentity = identityIntakes.filter(item => item.intake.status === "duplicate_review");
  const tabs: Array<[Tab, string]> = [["intake", "New referral"], ["identity", `Identity review (${pendingIdentity.length})`], ["triage", `Triage (${triage.filter(row => row.status !== "completed").length})`], ["referrals", `Referral queue (${referrals.length})`]];

  return <main style={{ minHeight: "100vh", background: "#e9eef5", color: "#0f172a", padding: 12, fontFamily: "Inter, system-ui, sans-serif" }}>
    <header style={{ background: "#071019", color: "white", borderRadius: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div><span style={{ color: "#2dd4bf", fontSize: 11, fontWeight: 900, letterSpacing: ".13em" }}>REFERRAL IDENTITY & TRIAGE V12</span><h1 style={{ fontSize: "clamp(36px,8vw,70px)", lineHeight: .93, margin: "6px 0" }}>Referral control</h1></div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}><Link href="/hospital-board" style={{ color: "white" }}>Hospital board</Link><Link href="/system-control" style={{ color: "white" }}>System control</Link></div>
      </div>
      <p style={{ color: "#94a3b8", maxWidth: 950 }}>Start with the incoming referral, not a pre-existing patient reference. The system screens duplicates, records owner authority, creates the canonical record, calculates response deadlines and converts accepted referrals into proposed operational work.</p>
    </header>

    <nav style={{ display: "flex", gap: 7, overflowX: "auto", padding: "10px 0" }}>{tabs.map(([key, label]) => <button key={key} style={{ ...button, flex: "0 0 auto", background: tab === key ? "#0f766e" : "#334155" }} onClick={() => setTab(key)}>{label}</button>)}</nav>
    {error && <div aria-live="assertive" style={{ ...panel, borderColor: "#ef4444", color: "#991b1b", marginBottom: 9 }}>{error}</div>}
    {message && <div aria-live="polite" style={{ ...panel, borderColor: "#22c55e", color: "#166534", marginBottom: 9 }}>{message}</div>}

    {tab === "intake" && <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,360px),1fr))", gap: 10 }}>
      <article style={{ ...panel, display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Patient identity</h2>
        <input placeholder="Patient name" style={field} value={form.patientName} onChange={e => setForm({ ...form, patientName: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 8 }}><select style={field} value={form.species} onChange={e => setForm({ ...form, species: e.target.value })}><option>dog</option><option>cat</option><option>rabbit</option><option>other</option></select><input placeholder="Breed" style={field} value={form.breed} onChange={e => setForm({ ...form, breed: e.target.value })} /></div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 8 }}><input placeholder="Sex" style={field} value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })} /><input type="date" aria-label="Date of birth" style={field} value={form.dateOfBirth} onChange={e => setForm({ ...form, dateOfBirth: e.target.value })} /></div>
        <input placeholder="Microchip number" style={field} value={form.microchipNumber} onChange={e => setForm({ ...form, microchipNumber: e.target.value })} />
        <h2 style={{ marginBottom: 0 }}>Owner and authority</h2>
        <input placeholder="Owner name" style={field} value={form.ownerName} onChange={e => setForm({ ...form, ownerName: e.target.value })} />
        <input type="email" placeholder="Owner email" style={field} value={form.ownerEmail} onChange={e => setForm({ ...form, ownerEmail: e.target.value })} />
        <input placeholder="Owner telephone" style={field} value={form.ownerPhone} onChange={e => setForm({ ...form, ownerPhone: e.target.value })} />
        <label><input type="checkbox" checked={form.decisionAuthority} onChange={e => setForm({ ...form, decisionAuthority: e.target.checked })} /> Claims clinical decision authority</label>
        <label><input type="checkbox" checked={form.financialResponsibility} onChange={e => setForm({ ...form, financialResponsibility: e.target.checked })} /> Claims financial responsibility</label>
      </article>

      <article style={{ ...panel, display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Referral source and clinical need</h2>
        <input placeholder="Premises reference" style={field} value={form.premisesRef} onChange={e => setForm({ ...form, premisesRef: e.target.value })} />
        <select style={field} value={form.sourceType} onChange={e => setForm({ ...form, sourceType: e.target.value })}><option value="referring_vet">Referring vet</option><option value="owner">Owner</option><option value="internal_transfer">Internal transfer</option><option value="emergency">Emergency presentation</option></select>
        <input placeholder="Source organisation" style={field} value={form.sourceOrganisation} onChange={e => setForm({ ...form, sourceOrganisation: e.target.value })} />
        <input placeholder="Source contact name" style={field} value={form.sourceContactName} onChange={e => setForm({ ...form, sourceContactName: e.target.value })} />
        <input type="email" placeholder="Source email" style={field} value={form.sourceContactEmail} onChange={e => setForm({ ...form, sourceContactEmail: e.target.value })} />
        <input placeholder="Source telephone" style={field} value={form.sourceContactPhone} onChange={e => setForm({ ...form, sourceContactPhone: e.target.value })} />
        <input placeholder="Requested service" style={field} value={form.requestedService} onChange={e => setForm({ ...form, requestedService: e.target.value })} />
        <textarea placeholder="Presenting problem" style={{ ...field, minHeight: 90 }} value={form.presentingProblem} onChange={e => setForm({ ...form, presentingProblem: e.target.value })} />
        <textarea placeholder="Clinical summary" style={{ ...field, minHeight: 110 }} value={form.clinicalSummary} onChange={e => setForm({ ...form, clinicalSummary: e.target.value })} />
        <select style={field} value={form.urgency} onChange={e => setForm({ ...form, urgency: e.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option><option value="red">Red</option></select>
        <input placeholder="Requested timeframe" style={field} value={form.requestedTimeframe} onChange={e => setForm({ ...form, requestedTimeframe: e.target.value })} />
      </article>

      <article style={{ ...panel, display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Referral document provenance</h2>
        <p style={{ color: "#64748b", marginTop: 0 }}>Optional at intake. Store the file in the approved document store, then record its immutable reference and SHA-256.</p>
        <select style={field} value={form.documentType} onChange={e => setForm({ ...form, documentType: e.target.value })}><option value="referral_letter">Referral letter</option><option value="clinical_history">Clinical history</option><option value="laboratory_result">Laboratory result</option><option value="imaging_report">Imaging report</option><option value="owner_document">Owner document</option></select>
        <input placeholder="Filename" style={field} value={form.documentFilename} onChange={e => setForm({ ...form, documentFilename: e.target.value })} />
        <input placeholder="Storage reference" style={field} value={form.documentStorageRef} onChange={e => setForm({ ...form, documentStorageRef: e.target.value })} />
        <input placeholder="64-character SHA-256" style={field} value={form.documentChecksum} onChange={e => setForm({ ...form, documentChecksum: e.target.value })} />
        <button disabled={busy || !form.patientName || !form.species || !form.ownerName || !form.requestedService || !form.presentingProblem} style={button} onClick={() => void createReferral()}>{busy ? "Recording…" : "Create governed referral intake"}</button>
        {created && !created.requiresIdentityReview && <section style={{ ...panel, borderColor: "#22c55e" }}><strong>Created</strong><p>{created.referral?.referral_ref} · {created.episode?.episode_ref}</p><Link href={`/episode-command?episode=${encodeURIComponent(created.episode?.episode_ref || "")}`}>Open episode command →</Link></section>}
      </article>
    </section>}

    {tab === "identity" && <section style={{ display: "grid", gap: 9 }}>
      {!pendingIdentity.length && <article style={panel}>No identity reviews are waiting.</article>}
      {pendingIdentity.map(item => <article key={item.intake.intake_ref} style={{ ...panel, borderColor: "#ef4444" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><div><strong style={{ fontSize: 21 }}>{item.intake.patient_name}</strong><p>{item.intake.species} · {item.intake.microchip_number || "no microchip recorded"} · owner {item.intake.owner_name}</p></div><b>{item.identityReviews.length} possible matches</b></div>
        <p>Referral creation is held. Select the correct existing patient or confirm that this is a new identity.</p>
        <div style={{ display: "grid", gap: 7 }}>{item.identityReviews.map((review: any) => <div key={review.review_ref} style={{ border: "1px solid #cbd5e1", borderRadius: 10, padding: 10 }}><strong>{review.candidate_patient_ref} · match {review.match_score}%</strong><p>{review.reasons.join(" · ")}</p><button disabled={busy} style={button} onClick={() => void resolveIdentity(item, "link_existing", review.candidate_patient_ref)}>Link this patient</button></div>)}</div>
        <button disabled={busy} style={{ ...button, marginTop: 9, background: "#334155" }} onClick={() => void resolveIdentity(item, "create_new")}>Matches reviewed — create new patient</button>
      </article>)}
    </section>}

    {tab === "triage" && <section style={{ display: "grid", gap: 9 }}>
      {triage.map(row => <article key={row.triage_ref} style={{ ...panel, borderColor: row.responseOverdue || row.clinicalReviewOverdue ? "#ef4444" : row.category === "emergency" ? "#ef4444" : row.category === "urgent" ? "#f59e0b" : "#cbd5e1" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong style={{ fontSize: 20 }}>{row.category.toUpperCase()} · score {row.score}</strong><b>{row.status}</b></div>
        <p>{row.rationale}</p><p><strong>Response due:</strong> {new Date(row.response_due_at).toLocaleString()} · <strong>clinical review:</strong> {new Date(row.clinical_review_due_at).toLocaleString()}</p>
        {row.red_flags?.length ? <p style={{ color: "#991b1b" }}><strong>Detected red flags:</strong> {row.red_flags.join(" · ")}</p> : null}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{row.status === "pending" && <button disabled={busy} style={button} onClick={() => void updateTriage(row, "acknowledged")}>Acknowledge</button>}{row.status !== "completed" && <button disabled={busy} style={{ ...button, background: "#334155" }} onClick={() => void updateTriage(row, "completed")}>Complete clinical triage</button>}</div>
      </article>)}
    </section>}

    {tab === "referrals" && <section style={{ display: "grid", gap: 9 }}>
      {referrals.map(row => <article key={row.referral_ref} style={{ ...panel, borderColor: row.urgency === "red" || row.urgency === "emergency" ? "#ef4444" : row.status === "needs_information" ? "#f59e0b" : "#cbd5e1" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong style={{ fontSize: 21 }}>{row.patientName || row.patient_ref}</strong><b>{row.urgency} · {row.status}</b></div>
        <p>{row.requested_service} · phase {row.episodePhase}</p><p>{row.presenting_problem}</p><small>{row.source_organisation || row.source_type} · received {new Date(row.received_at).toLocaleString()}</small>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 9 }}><Link href={`/episode-command?episode=${encodeURIComponent(row.episode_ref)}`}>Episode command →</Link>{row.status === "received" || row.status === "needs_information" ? <><button disabled={busy} style={button} onClick={() => void decideReferral(row, "accepted")}>Accept and propose block</button><button disabled={busy} style={{ ...button, background: "#b45309" }} onClick={() => void decideReferral(row, "needs_information")}>Request information</button><button disabled={busy} style={{ ...button, background: "#991b1b" }} onClick={() => void decideReferral(row, "declined")}>Decline</button></> : null}</div>
      </article>)}
    </section>}
  </main>;
}
