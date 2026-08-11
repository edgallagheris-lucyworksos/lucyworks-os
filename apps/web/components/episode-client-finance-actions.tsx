"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

type CommandView = {
  episode: { episode_ref: string; patient_ref?: string; premises_ref?: string };
  consents?: Array<{ owner_ref?: string; status?: string }>;
};
type Identity = { user: { role: string } };
type EstimateLine = { category: string; description: string; quantity: number; lowerUnitPence: number; upperUnitPence: number; taxRatePercent: number; optional: boolean };

const FINANCIAL_ROLES = new Set(["admin", "ops_manager", "hospital_director", "governance_lead"]);
const COMPLAINT_ROLES = new Set(["admin", "ops_manager", "hospital_director", "governance_lead", "clinical_director"]);
const PRESCRIPTION_ROLES = new Set(["admin", "ops_manager", "clinician", "senior_clinician", "clinical_director"]);

function pence(value: string) {
  const pounds = Number(value);
  return Number.isFinite(pounds) ? Math.round(pounds * 100) : 0;
}
function pounds(value: number) { return (value / 100).toFixed(2); }
const field: React.CSSProperties = { width: "100%", minHeight: 42, border: "1px solid #b8c4d1", borderRadius: 8, padding: "8px 9px", background: "white", color: "#14243a", fontSize: 14, boxSizing: "border-box" };

export function EpisodeClientFinanceActions() {
  const [episodeRef, setEpisodeRef] = useState("");
  const [command, setCommand] = useState<CommandView | null>(null);
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [estimateChannel, setEstimateChannel] = useState("email");
  const [ownerAcknowledged, setOwnerAcknowledged] = useState(false);
  const [authorisedLimit, setAuthorisedLimit] = useState("");
  const [reasonForChange, setReasonForChange] = useState("");
  const [lines, setLines] = useState<EstimateLine[]>([{ category: "procedure", description: "", quantity: 1, lowerUnitPence: 0, upperUnitPence: 0, taxRatePercent: 20, optional: false }]);

  const [chargeCategory, setChargeCategory] = useState("procedure");
  const [chargeDescription, setChargeDescription] = useState("");
  const [chargeQuantity, setChargeQuantity] = useState("1");
  const [chargeUnitPrice, setChargeUnitPrice] = useState("");
  const [externalSupplier, setExternalSupplier] = useState("");
  const [thirdPartyCost, setThirdPartyCost] = useState("");
  const [chargeMarkup, setChargeMarkup] = useState("");

  const [complaintChannel, setComplaintChannel] = useState("phone");
  const [complaintSeverity, setComplaintSeverity] = useState("standard");
  const [complaintCategory, setComplaintCategory] = useState("communication");
  const [complaintSummary, setComplaintSummary] = useState("");

  const [medicationName, setMedicationName] = useState("");
  const [prescriptionOffered, setPrescriptionOffered] = useState(true);
  const [prescriptionFee, setPrescriptionFee] = useState("");
  const [clientChoice, setClientChoice] = useState("hospital_supply");
  const [prescriptionChannel, setPrescriptionChannel] = useState("in_person");

  useEffect(() => {
    const read = () => setEpisodeRef(new URLSearchParams(window.location.search).get("episode") || "");
    read();
    window.addEventListener("popstate", read);
    const timer = window.setInterval(read, 1500);
    return () => { window.removeEventListener("popstate", read); window.clearInterval(timer); };
  }, []);

  const load = useCallback(async () => {
    if (!episodeRef) { setCommand(null); return; }
    try {
      const [episode, identity] = await Promise.all([
        apiGet<CommandView>(`/api/v9/episodes/${encodeURIComponent(episodeRef)}/command-view`),
        apiGet<Identity>("/api/auth/me"),
      ]);
      setCommand(episode);
      setRole(identity.user.role || "");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load episode actions");
    }
  }, [episodeRef]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await action();
      setMessage(success);
      window.dispatchEvent(new Event("lucyworks:episode-updated"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Action failed");
    } finally { setBusy(false); }
  }

  const ownerRef = command?.consents?.find(item => item.status === "active" && item.owner_ref)?.owner_ref;
  const patientRef = command?.episode.patient_ref;

  function updateLine(index: number, patch: Partial<EstimateLine>) {
    setLines(current => current.map((line, row) => row === index ? { ...line, ...patch } : line));
  }

  async function issueEstimate() {
    if (!patientRef) return;
    if (lines.some(line => !line.description.trim() || line.lowerUnitPence < 0 || line.upperUnitPence < line.lowerUnitPence)) {
      setError("Every estimate line needs a description and a valid lower/upper range."); return;
    }
    await run(() => apiJson(`/api/v32/episodes/${encodeURIComponent(episodeRef)}/estimates/deliver-and-issue`, {
      method: "POST",
      body: JSON.stringify({ patientRef, ownerRef, channel: estimateChannel, lines, authorisedLimitPence: authorisedLimit ? pence(authorisedLimit) : undefined, ownerAcknowledged, reasonForChange: reasonForChange.trim() || undefined, deliverySummary: "Written treatment estimate supplied from patient episode control.", reason: "Written estimate delivered and issued by authorised staff" }),
    }), "Estimate delivered and issued; authority and delivery evidence recorded.");
  }

  async function recordCharge() {
    if (!patientRef || !chargeDescription.trim()) { setError("Charge description is required."); return; }
    const quantity = Number(chargeQuantity);
    const unitPence = pence(chargeUnitPrice);
    if (!Number.isFinite(quantity) || quantity <= 0 || unitPence < 0) { setError("Charge quantity and unit price are invalid."); return; }
    const thirdParty = Boolean(externalSupplier.trim() || thirdPartyCost || chargeMarkup);
    const cost = thirdPartyCost ? pence(thirdPartyCost) : undefined;
    const markup = chargeMarkup ? pence(chargeMarkup) : undefined;
    const gross = Math.round(quantity * unitPence);
    if (thirdParty && (!externalSupplier.trim() || cost === undefined || markup === undefined)) { setError("Third-party charges require supplier, supplier cost and markup together."); return; }
    if (thirdParty && (cost || 0) + (markup || 0) !== gross) { setError(`Supplier cost plus markup must equal the £${pounds(gross)} gross charge.`); return; }
    await run(() => apiJson(`/api/v32/episodes/${encodeURIComponent(episodeRef)}/charges`, {
      method: "POST",
      body: JSON.stringify({ patientRef, category: chargeCategory.trim(), description: chargeDescription.trim(), quantity, unitPence, thirdPartyCostPence: cost, markupPence: markup, externalSupplier: externalSupplier.trim() || undefined, sourceSystem: "lucyworks", reason: "Performed service charge recorded from patient episode control" }),
    }), "Charge recorded against this patient episode.");
    setChargeDescription(""); setChargeUnitPrice(""); setExternalSupplier(""); setThirdPartyCost(""); setChargeMarkup("");
  }

  async function recordComplaint() {
    if (!patientRef || !complaintSummary.trim()) { setError("Complaint summary is required."); return; }
    await run(() => apiJson("/api/v32/complaints", {
      method: "POST",
      body: JSON.stringify({ premisesRef: command?.episode.premises_ref || "default-premises", episodeRef, patientRef, ownerRef, channel: complaintChannel, category: complaintCategory, severity: complaintSeverity, summary: complaintSummary.trim(), assignedRole: "ops_manager", reason: "Client concern recorded from patient episode control" }),
    }), "Client concern recorded, assigned and linked to this episode.");
    setComplaintSummary("");
  }

  async function recordPrescriptionChoice() {
    if (!patientRef || !medicationName.trim()) { setError("Medication name is required."); return; }
    if (clientChoice === "written_prescription" && !prescriptionOffered) { setError("A written prescription cannot be selected until that option has been offered."); return; }
    await run(() => apiJson(`/api/v32/episodes/${encodeURIComponent(episodeRef)}/prescription-choice/deliver-and-record`, {
      method: "POST",
      body: JSON.stringify({ patientRef, ownerRef, medicationName: medicationName.trim(), writtenPrescriptionOffered: prescriptionOffered, prescriptionFeePence: prescriptionFee ? pence(prescriptionFee) : undefined, clientChoice, channel: prescriptionChannel, informationSummary: prescriptionOffered ? `Written prescription option and fee information explained for ${medicationName.trim()}.` : undefined, reason: "Prescription information delivered and client choice recorded from patient episode control" }),
    }), "Prescription information and client choice recorded in one governed action.");
    setMedicationName("");
  }

  if (!episodeRef || !command) return null;
  const canFinance = FINANCIAL_ROLES.has(role);
  const canComplaint = COMPLAINT_ROLES.has(role);
  const canPrescription = PRESCRIPTION_ROLES.has(role);
  if (!canFinance && !canComplaint && !canPrescription) return null;

  return <section className="ecfa" aria-label="Client and financial actions">
    <style>{css}</style>
    <header><div><span>Episode actions</span><h2>Client & financial control</h2></div><p>Only actions authorised for your role are shown. Evidence and authority checks are recorded underneath.</p></header>
    {error ? <div className="alert error" role="alert">{error}</div> : null}
    {message ? <div className="alert success" role="status">{message}</div> : null}
    <div className="grid">
      {canFinance ? <details open><summary>Issue written estimate</summary><div className="form">
        {lines.map((line, index) => <div className="estimateLine" key={index}>
          <label>Category<input style={field} value={line.category} onChange={event => updateLine(index, { category: event.target.value })} /></label>
          <label className="wide">Description<input style={field} value={line.description} onChange={event => updateLine(index, { description: event.target.value })} placeholder="MRI, procedure, hospitalisation…" /></label>
          <label>Low £<input style={field} inputMode="decimal" value={pounds(line.lowerUnitPence)} onChange={event => updateLine(index, { lowerUnitPence: pence(event.target.value) })} /></label>
          <label>High £<input style={field} inputMode="decimal" value={pounds(line.upperUnitPence)} onChange={event => updateLine(index, { upperUnitPence: pence(event.target.value) })} /></label>
          {lines.length > 1 ? <button className="minor" onClick={() => setLines(current => current.filter((_, row) => row !== index))}>Remove</button> : null}
        </div>)}
        <button className="minor" onClick={() => setLines(current => [...current, { category: "procedure", description: "", quantity: 1, lowerUnitPence: 0, upperUnitPence: 0, taxRatePercent: 20, optional: false }])}>+ Add line</button>
        <div className="row"><label>Delivery<select style={field} value={estimateChannel} onChange={event => setEstimateChannel(event.target.value)}><option value="email">Email</option><option value="sms">SMS</option><option value="portal">Client portal</option><option value="printed">Printed</option><option value="in_person">In person</option></select></label><label>Authorised limit £<input style={field} value={authorisedLimit} onChange={event => setAuthorisedLimit(event.target.value)} placeholder="Optional" /></label></div>
        <label>Reason for material change<input style={field} value={reasonForChange} onChange={event => setReasonForChange(event.target.value)} placeholder="Required when an existing estimate materially increases" /></label>
        <label className="check"><input type="checkbox" checked={ownerAcknowledged} onChange={event => setOwnerAcknowledged(event.target.checked)} /> Client acknowledged receipt</label>
        <button className="primary" disabled={busy} onClick={() => void issueEstimate()}>Deliver & issue estimate</button>
      </div></details> : null}

      {canFinance ? <details open><summary>Record performed charge</summary><div className="form">
        <div className="row"><label>Category<input style={field} value={chargeCategory} onChange={event => setChargeCategory(event.target.value)} /></label><label>Quantity<input style={field} value={chargeQuantity} onChange={event => setChargeQuantity(event.target.value)} /></label></div>
        <label>Description<input style={field} value={chargeDescription} onChange={event => setChargeDescription(event.target.value)} placeholder="Performed service or supplied item" /></label>
        <label>Unit price £<input style={field} value={chargeUnitPrice} onChange={event => setChargeUnitPrice(event.target.value)} /></label>
        <details className="nested"><summary>Third-party supplier / markup</summary><div className="form compact"><label>Supplier<input style={field} value={externalSupplier} onChange={event => setExternalSupplier(event.target.value)} /></label><div className="row"><label>Supplier cost £<input style={field} value={thirdPartyCost} onChange={event => setThirdPartyCost(event.target.value)} /></label><label>Markup £<input style={field} value={chargeMarkup} onChange={event => setChargeMarkup(event.target.value)} /></label></div></div></details>
        <button className="primary" disabled={busy} onClick={() => void recordCharge()}>Record charge</button>
      </div></details> : null}

      {canComplaint ? <details><summary>Record client concern / complaint</summary><div className="form">
        <div className="row"><label>Channel<select style={field} value={complaintChannel} onChange={event => setComplaintChannel(event.target.value)}><option value="phone">Phone</option><option value="email">Email</option><option value="portal">Portal</option><option value="in_person">In person</option></select></label><label>Severity<select style={field} value={complaintSeverity} onChange={event => setComplaintSeverity(event.target.value)}><option value="standard">Standard</option><option value="serious">Serious</option><option value="critical">Critical</option></select></label></div>
        <label>Category<input style={field} value={complaintCategory} onChange={event => setComplaintCategory(event.target.value)} /></label>
        <label>What has the client raised?<textarea style={{ ...field, minHeight: 88 }} value={complaintSummary} onChange={event => setComplaintSummary(event.target.value)} /></label>
        <button className="primary" disabled={busy} onClick={() => void recordComplaint()}>Record & assign</button>
      </div></details> : null}

      {canPrescription ? <details><summary>Record prescription choice</summary><div className="form">
        <label>Medication<input style={field} value={medicationName} onChange={event => setMedicationName(event.target.value)} /></label>
        <div className="row"><label>Client choice<select style={field} value={clientChoice} onChange={event => setClientChoice(event.target.value)}><option value="hospital_supply">Hospital supply</option><option value="written_prescription">Written prescription</option><option value="declined">Declined</option><option value="not_applicable">Not applicable</option></select></label><label>Information channel<select style={field} value={prescriptionChannel} onChange={event => setPrescriptionChannel(event.target.value)}><option value="in_person">In person</option><option value="phone">Phone</option><option value="email">Email</option><option value="portal">Portal</option><option value="printed">Printed</option></select></label></div>
        <label>Prescription fee £<input style={field} value={prescriptionFee} onChange={event => setPrescriptionFee(event.target.value)} placeholder="0.00" /></label>
        <label className="check"><input type="checkbox" checked={prescriptionOffered} onChange={event => setPrescriptionOffered(event.target.checked)} /> Written prescription option explained/offered</label>
        <button className="primary" disabled={busy} onClick={() => void recordPrescriptionChoice()}>Record information & choice</button>
      </div></details> : null}
    </div>
  </section>;
}

const css = `
.ecfa{margin:0 12px 14px;background:#fff;border:1px solid #d7dee8;border-radius:14px;box-shadow:0 5px 18px rgba(15,23,42,.05);color:#172033;font-family:Inter,system-ui,sans-serif;overflow:hidden}.ecfa *{box-sizing:border-box}.ecfa>header{display:flex;justify-content:space-between;gap:14px;align-items:end;padding:13px 15px;background:#f8fafc;border-bottom:1px solid #e5eaf0}.ecfa header span{display:block;color:#65758a;font-size:10px;font-weight:800;letter-spacing:.11em;text-transform:uppercase}.ecfa h2{margin:2px 0 0;font-size:17px}.ecfa header p{margin:0;max-width:520px;color:#68778a;font-size:11px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:#e5eaf0}.grid>details{background:#fff}.grid>details>summary{cursor:pointer;padding:12px 14px;font-size:13px;font-weight:800;color:#213a52}.form{display:grid;gap:8px;padding:0 14px 14px}.form.compact{padding:0 8px 8px}.form label{display:grid;gap:3px;color:#526174;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em}.row{display:grid;grid-template-columns:1fr 1fr;gap:7px}.estimateLine{display:grid;grid-template-columns:1fr 2fr .8fr .8fr;gap:6px;padding:8px;border:1px solid #e3e9ef;border-radius:9px;background:#f8fafc}.estimateLine .wide{min-width:0}.check{display:flex!important;align-items:center;gap:7px!important;text-transform:none!important;letter-spacing:0!important;font-size:12px!important}.check input{width:17px;height:17px}.primary,.minor{border:0;border-radius:8px;padding:9px 11px;font-weight:800;cursor:pointer}.primary{background:#173f5f;color:white;min-height:42px}.primary:disabled{opacity:.55;cursor:wait}.minor{background:#edf2f7;color:#294761}.nested{border:1px solid #e3e9ef;border-radius:8px;background:#f8fafc}.nested>summary{padding:9px;font-size:11px;font-weight:800}.alert{margin:10px 14px 0;border-radius:8px;padding:9px 11px;font-size:12px;font-weight:700}.alert.error{background:#fff1f2;color:#991b1b;border:1px solid #fecdd3}.alert.success{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0}
@media(max-width:980px){.grid{grid-template-columns:1fr}.ecfa>header{align-items:flex-start;flex-direction:column}.estimateLine{grid-template-columns:1fr 1fr}.estimateLine .wide{grid-column:1/-1}}
@media(max-width:560px){.ecfa{margin:0 7px 10px}.row{grid-template-columns:1fr}.estimateLine{grid-template-columns:1fr 1fr}.estimateLine label:first-child,.estimateLine .wide{grid-column:1/-1}}
`;
