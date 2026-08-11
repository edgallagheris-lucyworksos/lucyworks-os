"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";
import { getOperationalContext } from "@/lib/operational-context";

type QueueTab = "new" | "identity" | "triage" | "referrals";
const steps = ["Patient", "Owner & authority", "Referral source", "Clinical need", "Documents", "Confirm"];

function emptyForm(premisesRef: string) {
  return {
    premisesRef,
    patientName: "", species: "dog", breed: "", sex: "", dateOfBirth: "", microchipNumber: "",
    ownerName: "", ownerEmail: "", ownerPhone: "", decisionAuthority: true, financialResponsibility: true,
    sourceType: "referring_vet", sourceOrganisation: "", sourceContactName: "", sourceContactEmail: "", sourceContactPhone: "",
    requestedService: "", presentingProblem: "", clinicalSummary: "", urgency: "routine", requestedTimeframe: "",
    documentType: "referral_letter", documentFilename: "", documentMimeType: "application/pdf", documentStorageRef: "", documentChecksum: "",
  };
}

export function GuidedReferralIntakeV31() {
  const [{ premisesRef, siteName }] = useState(() => getOperationalContext());
  const [tab, setTab] = useState<QueueTab>("new");
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(() => emptyForm(premisesRef));
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
      setError(reason instanceof Error ? reason.message : "Unable to load referral queues");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const pendingIdentity = useMemo(() => identityIntakes.filter(item => item.intake?.status === "duplicate_review"), [identityIntakes]);
  const openTriage = useMemo(() => triage.filter(row => row.status !== "completed"), [triage]);

  function valid(index: number) {
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
    if (!steps.every((_, index) => valid(index))) { setError("Complete each required stage before confirming the referral."); return; }
    setBusy(true); setError(""); setMessage(""); setCreated(null);
    try {
      const documents = form.documentFilename ? [{ documentType: form.documentType, filename: form.documentFilename, mimeType: form.documentMimeType, storageRef: form.documentStorageRef, checksumSha256: form.documentChecksum, sourceSystem: "manual_intake" }] : [];
      const result = await apiJson<any>("/api/v12/referrals/intake", {
        method: "POST",
        body: JSON.stringify({
          premisesRef: form.premisesRef, patientName: form.patientName, species: form.species, breed: form.breed || null, sex: form.sex || null,
          dateOfBirth: form.dateOfBirth || null, microchipNumber: form.microchipNumber || null, ownerName: form.ownerName, ownerEmail: form.ownerEmail || null,
          ownerPhone: form.ownerPhone || null, decisionAuthority: form.decisionAuthority, financialResponsibility: form.financialResponsibility,
          sourceType: form.sourceType, sourceOrganisation: form.sourceOrganisation || null, sourceContactName: form.sourceContactName || null,
          sourceContactEmail: form.sourceContactEmail || null, sourceContactPhone: form.sourceContactPhone || null, requestedService: form.requestedService,
          presentingProblem: form.presentingProblem, clinicalSummary: form.clinicalSummary, urgency: form.urgency, requestedTimeframe: form.requestedTimeframe || null,
          documents, reason: "Referral identity, authority, provenance and clinical need confirmed by verified operator",
        }),
      });
      setCreated(result);
      if (result.requiresIdentityReview) { setMessage("Possible duplicate found. Review identity before creating a new patient."); setTab("identity"); }
      else setMessage(`${form.patientName} is ready for clinical review.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create referral"); }
    finally { setBusy(false); }
  }

  async function resolveIdentity(item: any, decision: "link_existing" | "create_new") {
    const intakeRef = item.intake.intake_ref;
    const patientRef = identityLinks[intakeRef]?.trim() || "";
    if (decision === "link_existing" && !patientRef) { setError("Enter the verified patient reference before linking."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiJson<any>(`/api/v12/identity-intakes/${intakeRef}/resolve`, { method: "POST", body: JSON.stringify({ expectedVersion: item.intake.version, decision, patientRef: patientRef || null, reason: decision === "link_existing" ? "Duplicate review linked to verified existing patient" : "Duplicate review confirmed a genuinely new patient" }) });
      setMessage("Identity review completed. The referral is ready for triage."); setCreated(result); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Identity resolution failed"); }
    finally { setBusy(false); }
  }

  async function updateTriage(row: any, status: "acknowledged" | "completed") {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiJson(`/api/v12/triage/${row.triage_ref}`, { method: "PATCH", body: JSON.stringify({ expectedVersion: row.version, status, rationale: row.rationale, reason: status === "acknowledged" ? "Clinician accepted triage responsibility" : "Clinician completed referral triage" }) });
      setMessage(status === "acknowledged" ? "Triage responsibility accepted." : "Triage completed."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Triage update failed"); }
    finally { setBusy(false); }
  }

  async function decideReferral(row: any, status: "accepted" | "declined" | "more_information_required") {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiJson<any>(`/api/v12/referrals/${row.referral_ref}/decision`, { method: "PATCH", body: JSON.stringify({ expectedVersion: row.version, status, reason: status === "accepted" ? "Referral clinically accepted and operational work requested" : `Referral marked ${status} after clinical review` }) });
      setMessage(status === "accepted" && result.proposedBlock ? `Accepted and proposed in ${result.proposedBlock.area_name} at ${new Date(result.proposedBlock.starts_at).toLocaleString()}.` : `Referral ${status.replaceAll("_", " ")}.`); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Referral decision failed"); }
    finally { setBusy(false); }
  }

  const tabs: Array<[QueueTab, string, number?]> = [["new", "New referral"], ["identity", "Identity review", pendingIdentity.length], ["triage", "Triage", openTriage.length], ["referrals", "Referral queue", referrals.length]];

  return <main className="ri"><style>{css}</style>
    <header className="ri-head"><div><Link href="/hospital-board" className="ri-mark">LW</Link><div><h1>Referral intake</h1><span>{siteName}</span></div></div><nav><Link href="/hospital-board">Hospital</Link><Link href="/workspace">Workspace</Link></nav></header>
    <nav className="ri-tabs" aria-label="Referral sections">{tabs.map(([key, text, count]) => <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{text}{typeof count === "number" ? <span>{count}</span> : null}</button>)}</nav>
    {error ? <div className="ri-alert error" role="alert">{error}</div> : null}{message ? <div className="ri-alert success" aria-live="polite">{message}</div> : null}

    {tab === "new" ? <div className="ri-layout">
      <aside className="ri-steps">{steps.map((text, index) => <button key={text} className={index === step ? "active" : index < step && valid(index) ? "done" : ""} onClick={() => setStep(index)}><span>{index + 1}</span><strong>{text}</strong></button>)}</aside>
      <section className="ri-panel">
        <div className="ri-panel-head"><div><span>Step {step + 1} of {steps.length}</span><h2>{steps[step]}</h2></div><small>{siteName}</small></div>
        <div className="ri-form">
          {step === 0 && <><label>Patient name<input value={form.patientName} onChange={e => setForm({ ...form, patientName: e.target.value })} autoFocus /></label><div className="ri-grid"><label>Species<select value={form.species} onChange={e => setForm({ ...form, species: e.target.value })}><option>dog</option><option>cat</option><option>rabbit</option><option>other</option></select></label><label>Breed<input value={form.breed} onChange={e => setForm({ ...form, breed: e.target.value })} /></label><label>Sex<input value={form.sex} onChange={e => setForm({ ...form, sex: e.target.value })} /></label><label>Date of birth<input type="date" value={form.dateOfBirth} onChange={e => setForm({ ...form, dateOfBirth: e.target.value })} /></label></div><label>Microchip number<input value={form.microchipNumber} onChange={e => setForm({ ...form, microchipNumber: e.target.value })} /></label><p className="ri-note">LucyWorks checks for possible duplicate patients before creating a new record.</p></>}
          {step === 1 && <><label>Owner or authorised representative<input value={form.ownerName} onChange={e => setForm({ ...form, ownerName: e.target.value })} /></label><div className="ri-grid"><label>Email<input type="email" value={form.ownerEmail} onChange={e => setForm({ ...form, ownerEmail: e.target.value })} /></label><label>Telephone<input value={form.ownerPhone} onChange={e => setForm({ ...form, ownerPhone: e.target.value })} /></label></div><label className="ri-check"><input type="checkbox" checked={form.decisionAuthority} onChange={e => setForm({ ...form, decisionAuthority: e.target.checked })} />Clinical decision authority confirmed</label><label className="ri-check"><input type="checkbox" checked={form.financialResponsibility} onChange={e => setForm({ ...form, financialResponsibility: e.target.checked })} />Financial responsibility confirmed</label></>}
          {step === 2 && <><label>Referral source<select value={form.sourceType} onChange={e => setForm({ ...form, sourceType: e.target.value })}><option value="referring_vet">Referring vet</option><option value="owner">Owner</option><option value="internal_transfer">Internal transfer</option><option value="emergency">Emergency presentation</option></select></label><label>Organisation<input value={form.sourceOrganisation} onChange={e => setForm({ ...form, sourceOrganisation: e.target.value })} /></label><div className="ri-grid"><label>Contact name<input value={form.sourceContactName} onChange={e => setForm({ ...form, sourceContactName: e.target.value })} /></label><label>Contact email<input type="email" value={form.sourceContactEmail} onChange={e => setForm({ ...form, sourceContactEmail: e.target.value })} /></label><label>Contact telephone<input value={form.sourceContactPhone} onChange={e => setForm({ ...form, sourceContactPhone: e.target.value })} /></label></div></>}
          {step === 3 && <><div className="ri-grid"><label>Requested service<input value={form.requestedService} onChange={e => setForm({ ...form, requestedService: e.target.value })} /></label><label>Urgency<select value={form.urgency} onChange={e => setForm({ ...form, urgency: e.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option><option value="red">Red</option></select></label><label>Requested timeframe<input value={form.requestedTimeframe} onChange={e => setForm({ ...form, requestedTimeframe: e.target.value })} /></label></div><label>Presenting problem<textarea value={form.presentingProblem} onChange={e => setForm({ ...form, presentingProblem: e.target.value })} /></label><label>Clinical summary<textarea className="tall" value={form.clinicalSummary} onChange={e => setForm({ ...form, clinicalSummary: e.target.value })} /></label></>}
          {step === 4 && <><p className="ri-note">Documents can follow later. If a document is recorded now, its storage reference and checksum are required.</p><div className="ri-grid"><label>Document type<select value={form.documentType} onChange={e => setForm({ ...form, documentType: e.target.value })}><option value="referral_letter">Referral letter</option><option value="clinical_history">Clinical history</option><option value="diagnostic_report">Diagnostic report</option><option value="image_manifest">Image manifest</option></select></label><label>Filename<input value={form.documentFilename} onChange={e => setForm({ ...form, documentFilename: e.target.value })} /></label></div><label>Approved storage reference<input value={form.documentStorageRef} onChange={e => setForm({ ...form, documentStorageRef: e.target.value })} /></label><label>SHA-256 checksum<input value={form.documentChecksum} onChange={e => setForm({ ...form, documentChecksum: e.target.value })} /></label></>}
          {step === 5 && <><div className="ri-review"><div><span>Patient</span><strong>{form.patientName} · {form.species}</strong></div><div><span>Owner</span><strong>{form.ownerName}</strong></div><div><span>Source</span><strong>{form.sourceOrganisation || form.sourceType.replaceAll("_", " ")}</strong></div><div><span>Service</span><strong>{form.requestedService}</strong></div><div><span>Urgency</span><strong>{form.urgency}</strong></div><div><span>Document</span><strong>{form.documentFilename || "Not supplied at intake"}</strong></div></div><button className="ri-primary" disabled={busy} onClick={() => void createReferral()}>Create referral</button></>}
        </div>
        <footer><button disabled={step === 0} onClick={() => setStep(value => Math.max(0, value - 1))}>Back</button>{step < 5 ? <button className="ri-primary" disabled={!valid(step)} onClick={() => setStep(value => Math.min(5, value + 1))}>Continue</button> : null}</footer>
      </section>
      {created?.episode?.episode_ref ? <section className="ri-created"><div><span>Referral created</span><strong>{form.patientName || created.episode.patient_name || "Patient"}</strong></div><nav><Link href={`/care?episode=${encodeURIComponent(created.episode.episode_ref)}`}>Care brief</Link><Link className="primary" href={`/episode-command?episode=${encodeURIComponent(created.episode.episode_ref)}`}>Open episode</Link><button onClick={() => { setForm(emptyForm(premisesRef)); setCreated(null); setStep(0); }}>New referral</button></nav></section> : null}
    </div> : null}

    {tab === "identity" ? <QueueSection title="Identity review" count={pendingIdentity.length}>{pendingIdentity.length ? pendingIdentity.map(item => { const ref = item.intake.intake_ref; return <article className="ri-card" key={ref}><div><span>Possible duplicate</span><h3>{item.intake.patient_name || "Patient"}</h3><p>{item.candidates?.length || 0} candidate matches require confirmation.</p></div>{item.candidates?.map((candidate: any) => <p className="candidate" key={candidate.patient_ref}><strong>{candidate.patient_name}</strong><span>Match score {candidate.score}</span></p>)}<label>Verified patient reference<input value={identityLinks[ref] || ""} onChange={e => setIdentityLinks({ ...identityLinks, [ref]: e.target.value })} /></label><div className="ri-actions"><button className="ri-primary" disabled={busy} onClick={() => void resolveIdentity(item, "link_existing")}>Link existing patient</button><button disabled={busy} onClick={() => void resolveIdentity(item, "create_new")}>Confirm new patient</button></div></article>; }) : <Empty text="No identity reviews are waiting." />}</QueueSection> : null}

    {tab === "triage" ? <QueueSection title="Triage" count={openTriage.length}>{openTriage.length ? openTriage.map(row => <article className="ri-card" key={row.triage_ref}><div><span>{row.urgency}</span><h3>{row.patient_name || "Referral"}</h3><p>{row.rationale}</p><small>Due {row.due_at ? new Date(row.due_at).toLocaleString() : "not set"}</small></div><div className="ri-actions"><button className="ri-primary" disabled={busy || row.status !== "pending"} onClick={() => void updateTriage(row, "acknowledged")}>Acknowledge</button><button disabled={busy || row.status === "completed"} onClick={() => void updateTriage(row, "completed")}>Complete triage</button></div></article>) : <Empty text="No triage work is waiting." />}</QueueSection> : null}

    {tab === "referrals" ? <QueueSection title="Referral queue" count={referrals.length}>{referrals.length ? referrals.map(row => <article className="ri-card" key={row.referral_ref}><div><span>{row.urgency} · {row.status}</span><h3>{row.patient_name || "Referral"}</h3><p><strong>{row.requested_service}</strong> · {row.presenting_problem || row.clinical_summary}</p></div><div className="ri-actions"><button className="ri-primary" disabled={busy || row.status === "accepted"} onClick={() => void decideReferral(row, "accepted")}>Accept</button><button disabled={busy} onClick={() => void decideReferral(row, "more_information_required")}>Request information</button><button className="danger" disabled={busy} onClick={() => void decideReferral(row, "declined")}>Decline</button></div></article>) : <Empty text="No referrals are waiting." />}</QueueSection> : null}
  </main>;
}

function QueueSection({ title, count, children }: { title: string; count: number; children: React.ReactNode }) { return <section className="ri-queue"><header><h2>{title}</h2><span>{count}</span></header><div>{children}</div></section>; }
function Empty({ text }: { text: string }) { return <div className="ri-empty">{text}</div>; }

const css = `
.ri{min-height:100vh;background:#eef2f7;color:#172033;padding:12px 18px 28px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.ri *{box-sizing:border-box}.ri-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 12px;background:#fff;border:1px solid #d9e1e9;border-radius:11px}.ri-head>div{display:flex;align-items:center;gap:10px}.ri-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(145deg,#163a57,#102a42);color:#fff;text-decoration:none;font-size:11px;font-weight:900}.ri-head h1{margin:0;font-size:17px;color:#142b40}.ri-head span{display:block;margin-top:2px;color:#6f7e91;font-size:9px}.ri-head nav{display:flex;gap:5px}.ri-head nav a{padding:7px 9px;border-radius:7px;color:#294761;text-decoration:none;font-size:10px;font-weight:800}.ri-tabs{display:flex;gap:6px;overflow:auto;padding:10px 0}.ri-tabs button{display:flex;align-items:center;gap:6px;min-height:36px;padding:0 11px;border:1px solid #cbd5df;border-radius:8px;background:#fff;color:#536477;font-size:11px;font-weight:800;white-space:nowrap}.ri-tabs button.active{background:#173f5f;border-color:#173f5f;color:#fff}.ri-tabs button span{display:grid;place-items:center;min-width:18px;height:18px;padding:0 5px;border-radius:99px;background:#edf2f6;color:#40566c;font-size:8px}.ri-tabs button.active span{background:rgba(255,255,255,.17);color:#fff}.ri-alert{padding:10px 12px;margin-bottom:9px;border-radius:9px;border:1px solid;font-size:11px;font-weight:700}.ri-alert.error{background:#fff5f4;border-color:#efb0ab;color:#963a34}.ri-alert.success{background:#f0faf5;border-color:#a9d9c4;color:#2f6d53}.ri-layout{display:grid;grid-template-columns:210px minmax(0,1fr);gap:12px;align-items:start}.ri-steps{display:grid;gap:5px}.ri-steps button{display:flex;align-items:center;gap:9px;min-height:42px;padding:7px 9px;border:1px solid transparent;border-radius:8px;background:transparent;color:#657589;text-align:left}.ri-steps button span{display:grid;place-items:center;width:24px;height:24px;border-radius:99px;background:#dfe6ed;color:#52667b;font-size:9px;font-weight:850}.ri-steps button strong{font-size:10px}.ri-steps button.active{background:#fff;border-color:#d9e1e9;color:#17344d}.ri-steps button.active span{background:#173f5f;color:#fff}.ri-steps button.done span{background:#dff1e8;color:#2d7358}.ri-panel{background:#fff;border:1px solid #d9e1e9;border-radius:11px;overflow:hidden}.ri-panel-head{display:flex;justify-content:space-between;align-items:end;gap:10px;padding:13px 15px;border-bottom:1px solid #e9edf1;background:#f8fafc}.ri-panel-head span{color:#718096;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.ri-panel-head h2{margin:2px 0 0;font-size:18px}.ri-panel-head small{color:#7b8796;font-size:9px}.ri-form{display:grid;gap:11px;padding:15px}.ri label{display:grid;gap:4px;color:#526477;font-size:10px;font-weight:800}.ri input,.ri select,.ri textarea{width:100%;min-height:42px;padding:8px 9px;border:1px solid #bec9d5;border-radius:8px;background:#fff;color:#172033;font-size:13px}.ri textarea{min-height:85px;resize:vertical}.ri textarea.tall{min-height:120px}.ri input:focus,.ri select:focus,.ri textarea:focus{outline:0;border-color:#537b99;box-shadow:0 0 0 3px rgba(47,94,126,.1)}.ri-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:9px}.ri-check{display:flex!important;grid-template-columns:auto 1fr;align-items:center;gap:8px!important;min-height:36px}.ri-check input{width:auto;min-height:auto}.ri-note{margin:0;padding:9px 10px;border-left:3px solid #6c91aa;background:#f5f8fa;border-radius:6px;color:#5e6d7e;font-size:10px;line-height:1.45}.ri-review{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ri-review>div{display:grid;gap:2px;padding:9px 10px;background:#f7f9fb;border:1px solid #e5eaf0;border-radius:8px}.ri-review span{color:#748296;font-size:8px;text-transform:uppercase;font-weight:800}.ri-review strong{font-size:11px;text-transform:capitalize}.ri-panel footer{display:flex;justify-content:space-between;gap:8px;padding:10px 15px;border-top:1px solid #e9edf1;background:#fafbfc}.ri button,.ri-created a{min-height:38px;padding:0 12px;border:1px solid #c7d1dc;border-radius:8px;background:#fff;color:#294761;font-size:10px;font-weight:800}.ri button.ri-primary,.ri-created a.primary{border-color:#173f5f;background:#173f5f;color:#fff}.ri button.danger{border-color:#e1aaa6;color:#933832;background:#fff6f5}.ri button:disabled{opacity:.45;cursor:not-allowed}.ri-created{grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 13px;background:#f0faf5;border:1px solid #addbc6;border-radius:10px}.ri-created>div{display:grid}.ri-created span{color:#58806d;font-size:8px;font-weight:800;text-transform:uppercase}.ri-created strong{font-size:14px}.ri-created nav{display:flex;gap:6px;flex-wrap:wrap}.ri-created a{display:inline-flex;align-items:center;text-decoration:none}.ri-queue{background:#fff;border:1px solid #d9e1e9;border-radius:11px;overflow:hidden}.ri-queue>header{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;border-bottom:1px solid #e8edf2}.ri-queue h2{margin:0;font-size:17px}.ri-queue>header span{display:grid;place-items:center;min-width:25px;height:25px;border-radius:99px;background:#eef2f6;color:#42596f;font-size:9px;font-weight:850}.ri-queue>div{display:grid;gap:8px;padding:10px}.ri-card{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:11px 12px;border:1px solid #e0e6ec;border-radius:9px}.ri-card>div:first-child>span{color:#6c7b8e;font-size:8px;font-weight:800;text-transform:uppercase}.ri-card h3{margin:2px 0;font-size:14px}.ri-card p{margin:3px 0;color:#607083;font-size:10px}.ri-card small{color:#8792a0;font-size:9px}.ri-card label{grid-column:1/-1}.candidate{display:flex;justify-content:space-between!important;padding:6px 8px;background:#f6f8fa;border-radius:6px}.ri-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.ri-empty{padding:20px;color:#708094;font-size:11px;text-align:center}
@media(max-width:760px){.ri{padding:8px}.ri-layout{grid-template-columns:1fr}.ri-steps{grid-template-columns:repeat(6,minmax(36px,1fr));overflow:auto}.ri-steps button{display:grid;justify-items:center;padding:6px 4px;min-height:48px}.ri-steps button strong{display:none}.ri-created{display:grid}.ri-card{grid-template-columns:1fr}.ri-actions{justify-content:flex-start}}
@media(max-width:480px){.ri-head nav a{display:none}.ri-review{grid-template-columns:1fr}.ri-grid{grid-template-columns:1fr}}
`;
