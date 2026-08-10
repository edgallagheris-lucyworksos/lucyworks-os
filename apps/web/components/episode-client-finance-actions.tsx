"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";

type CommandView = {
  episode: { episode_ref: string; patient_ref?: string; premises_ref?: string; patient_name?: string };
  consents?: Array<{ owner_ref?: string; status?: string }>;
};

type EstimateLine = {
  category: string;
  description: string;
  quantity: number;
  lowerUnitPence: number;
  upperUnitPence: number;
  taxRatePercent: number;
  optional: boolean;
};

type CommunicationResponse = { communication: { evidence_event_ref?: string; communication_ref: string } };

const field: React.CSSProperties = {
  width: "100%",
  minHeight: 42,
  border: "1px solid #b8c4d1",
  borderRadius: 8,
  padding: "8px 9px",
  background: "white",
  color: "#14243a",
  fontSize: 14,
  boxSizing: "border-box",
};

function pence(value: string) {
  const pounds = Number(value);
  return Number.isFinite(pounds) ? Math.round(pounds * 100) : 0;
}

function pounds(value: number) {
  return (value / 100).toFixed(2);
}

export function EpisodeClientFinanceActions() {
  const [episodeRef, setEpisodeRef] = useState("");
  const [command, setCommand] = useState<CommandView | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [estimateChannel, setEstimateChannel] = useState("email");
  const [ownerAcknowledged, setOwnerAcknowledged] = useState(false);
  const [authorisedLimit, setAuthorisedLimit] = useState("");
  const [reasonForChange, setReasonForChange] = useState("");
  const [lines, setLines] = useState<EstimateLine[]>([
    { category: "procedure", description: "", quantity: 1, lowerUnitPence: 0, upperUnitPence: 0, taxRatePercent: 20, optional: false },
  ]);

  const [complaintChannel, setComplaintChannel] = useState("phone");
  const [complaintCategory, setComplaintCategory] = useState("communication");
  const [complaintSeverity, setComplaintSeverity] = useState("standard");
  const [complaintSummary, setComplaintSummary] = useState("");

  const [medicationName, setMedicationName] = useState("");
  const [prescriptionOffered, setPrescriptionOffered] = useState(true);
  const [prescriptionFee, setPrescriptionFee] = useState("");
  const [clientChoice, setClientChoice] = useState("hospital_supply");

  useEffect(() => {
    const read = () => setEpisodeRef(new URLSearchParams(window.location.search).get("episode") || "");
    read();
    window.addEventListener("popstate", read);
    const timer = window.setInterval(read, 1500);
    return () => {
      window.removeEventListener("popstate", read);
      window.clearInterval(timer);
    };
  }, []);

  const load = useCallback(async () => {
    if (!episodeRef) {
      setCommand(null);
      return;
    }
    try {
      setCommand(await apiGet<CommandView>(`/api/v9/episodes/${encodeURIComponent(episodeRef)}/command-view`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load episode context");
    }
  }, [episodeRef]);

  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(success);
      window.dispatchEvent(new Event("lucyworks:episode-updated"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  function updateLine(index: number, patch: Partial<EstimateLine>) {
    setLines(current => current.map((line, row) => row === index ? { ...line, ...patch } : line));
  }

  async function issueEstimate() {
    if (!command?.episode.patient_ref) return;
    if (lines.some(line => !line.description.trim() || line.upperUnitPence < line.lowerUnitPence || line.lowerUnitPence < 0)) {
      setError("Every estimate line needs a description and a valid lower/upper range.");
      return;
    }
    const ownerRef = command.consents?.find(item => item.status === "active" && item.owner_ref)?.owner_ref;
    await run(
      () => apiJson(`/api/v32/episodes/${encodeURIComponent(episodeRef)}/estimates/deliver-and-issue`, {
        method: "POST",
        body: JSON.stringify({
          patientRef: command.episode.patient_ref,
          ownerRef,
          channel: estimateChannel,
          lines,
          authorisedLimitPence: authorisedLimit ? pence(authorisedLimit) : undefined,
          ownerAcknowledged,
          reasonForChange: reasonForChange.trim() || undefined,
          deliverySummary: "Written treatment estimate supplied to the client from the episode command.",
          reason: "Staff issued written estimate from episode command",
        }),
      }),
      "Written estimate delivered and issued with authority and communication evidence recorded.",
    );
  }

  async function recordComplaint() {
    if (!command?.episode.patient_ref || !complaintSummary.trim()) {
      setError("Complaint summary is required.");
      return;
    }
    await run(
      () => apiJson("/api/v32/complaints", {
        method: "POST",
        body: JSON.stringify({
          premisesRef: command.episode.premises_ref || "default-premises",
          episodeRef,
          patientRef: command.episode.patient_ref,
          channel: complaintChannel,
          category: complaintCategory,
          severity: complaintSeverity,
          summary: complaintSummary.trim(),
          assignedRole: "ops_manager",
          reason: "Client concern recorded from episode command",
        }),
      }),
      "Complaint recorded, assigned and linked to this episode.",
    );
    setComplaintSummary("");
  }

  async function recordPrescriptionChoice() {
    if (!command?.episode.patient_ref || !medicationName.trim()) {
      setError("Medication name is required.");
      return;
    }
    if (clientChoice === "written_prescription" && !prescriptionOffered) {
      setError("A written prescription cannot be selected until the option has been explained and offered.");
      return;
    }
    const ownerRef = command.consents?.find(item => item.status === "active" && item.owner_ref)?.owner_ref;
    await run(async () => {
      let informationDeliveryRef: string | undefined;
      if (prescriptionOffered) {
        const communication = await apiJson<CommunicationResponse>(`/api/v8/episodes/${encodeURIComponent(episodeRef)}/communications`, {
          method: "POST",
          body: JSON.stringify({
            patient_ref: command.episode.patient_ref,
            owner_ref: ownerRef,
            audience: "owner",
            channel: "in_person",
            direction: "outbound",
            subject: "Written prescription choice",
            summary: `Written prescription option and fee information explained for ${medicationName.trim()}.`,
            outcome: "information supplied",
            consent_or_authorisation: { writtenPrescriptionOptionExplained: true },
            reason: "Prescription choice information supplied from episode command",
          }),
        });
        informationDeliveryRef = communication.communication.evidence_event_ref || communication.communication.communication_ref;
      }
      return apiJson(`/api/v32/episodes/${encodeURIComponent(episodeRef)}/prescription-choice`, {
        method: "POST",
        body: JSON.stringify({
          patientRef: command.episode.patient_ref,
          ownerRef,
          medicationName: medicationName.trim(),
          writtenPrescriptionOffered: prescriptionOffered,
          prescriptionFeePence: prescriptionFee ? pence(prescriptionFee) : undefined,
          clientChoice,
          informationDeliveryRef,
          reason: "Client prescription choice recorded from episode command",
        }),
      });
    }, "Prescription choice and client-information evidence recorded against this episode.");
    setMedicationName("");
  }

  if (!episodeRef || !command) return null;

  return (
    <section className="ecfa" aria-label="Client and financial actions">
      <style>{css}</style>
      <header>
        <div><span>Episode actions</span><h2>Client & financial control</h2></div>
        <p>Normal staff actions; evidence, authority checks and audit records are created underneath.</p>
      </header>

      {error ? <div className="ecfa-alert error" role="alert">{error}</div> : null}
      {message ? <div className="ecfa-alert success" role="status">{message}</div> : null}

      <div className="ecfa-grid">
        <details open>
          <summary>Issue written estimate</summary>
          <div className="form">
            {lines.map((line, index) => (
              <div className="line" key={index}>
                <label>Category<input style={field} value={line.category} onChange={event => updateLine(index, { category: event.target.value })} /></label>
                <label className="wide">Description<input style={field} value={line.description} onChange={event => updateLine(index, { description: event.target.value })} placeholder="MRI, procedure, hospitalisation…" /></label>
                <label>Low £<input style={field} inputMode="decimal" value={pounds(line.lowerUnitPence)} onChange={event => updateLine(index, { lowerUnitPence: pence(event.target.value) })} /></label>
                <label>High £<input style={field} inputMode="decimal" value={pounds(line.upperUnitPence)} onChange={event => updateLine(index, { upperUnitPence: pence(event.target.value) })} /></label>
                {lines.length > 1 ? <button type="button" className="minor" onClick={() => setLines(current => current.filter((_, row) => row !== index))}>Remove</button> : null}
              </div>
            ))}
            <button type="button" className="minor" onClick={() => setLines(current => [...current, { category: "procedure", description: "", quantity: 1, lowerUnitPence: 0, upperUnitPence: 0, taxRatePercent: 20, optional: false }])}>+ Add line</button>
            <div className="row">
              <label>Delivery<select style={field} value={estimateChannel} onChange={event => setEstimateChannel(event.target.value)}><option value="email">Email</option><option value="sms">SMS</option><option value="portal">Client portal</option><option value="printed">Printed</option><option value="in_person">In person</option></select></label>
              <label>Authorised limit £<input style={field} inputMode="decimal" value={authorisedLimit} onChange={event => setAuthorisedLimit(event.target.value)} placeholder="Optional" /></label>
            </div>
            <label>Reason for material change<input style={field} value={reasonForChange} onChange={event => setReasonForChange(event.target.value)} placeholder="Required if a previous written estimate has materially increased" /></label>
            <label className="check"><input type="checkbox" checked={ownerAcknowledged} onChange={event => setOwnerAcknowledged(event.target.checked)} /> Client acknowledged receipt</label>
            <button type="button" className="primary" disabled={busy} onClick={() => void issueEstimate()}>Deliver & issue estimate</button>
          </div>
        </details>

        <details>
          <summary>Record client concern / complaint</summary>
          <div className="form">
            <div className="row"><label>Channel<select style={field} value={complaintChannel} onChange={event => setComplaintChannel(event.target.value)}><option>phone</option><option>email</option><option>portal</option><option>in_person</option></select></label><label>Severity<select style={field} value={complaintSeverity} onChange={event => setComplaintSeverity(event.target.value)}><option value="standard">Standard</option><option value="serious">Serious</option><option value="critical">Critical</option></select></label></div>
            <label>Category<input style={field} value={complaintCategory} onChange={event => setComplaintCategory(event.target.value)} /></label>
            <label>What has the client raised?<textarea style={{ ...field, minHeight: 90 }} value={complaintSummary} onChange={event => setComplaintSummary(event.target.value)} /></label>
            <button type="button" className="primary" disabled={busy} onClick={() => void recordComplaint()}>Record & assign</button>
          </div>
        </details>

        <details>
          <summary>Record prescription choice</summary>
          <div className="form">
            <label>Medication<input style={field} value={medicationName} onChange={event => setMedicationName(event.target.value)} /></label>
            <div className="row"><label>Client choice<select style={field} value={clientChoice} onChange={event => setClientChoice(event.target.value)}><option value="hospital_supply">Hospital supply</option><option value="written_prescription">Written prescription</option><option value="declined">Declined</option><option value="not_applicable">Not applicable</option></select></label><label>Prescription fee £<input style={field} inputMode="decimal" value={prescriptionFee} onChange={event => setPrescriptionFee(event.target.value)} placeholder="0.00" /></label></div>
            <label className="check"><input type="checkbox" checked={prescriptionOffered} onChange={event => setPrescriptionOffered(event.target.checked)} /> Written prescription option explained/offered</label>
            <button type="button" className="primary" disabled={busy} onClick={() => void recordPrescriptionChoice()}>Record client choice</button>
          </div>
        </details>
      </div>
    </section>
  );
}

const css = `
.ecfa{margin:0 12px 14px;background:#fff;border:1px solid #d7dee8;border-radius:14px;box-shadow:0 5px 18px rgba(15,23,42,.05);color:#172033;font-family:Inter,system-ui,sans-serif;overflow:hidden}.ecfa *{box-sizing:border-box}.ecfa>header{display:flex;justify-content:space-between;gap:14px;align-items:end;padding:13px 15px;background:#f8fafc;border-bottom:1px solid #e5eaf0}.ecfa header span{display:block;color:#65758a;font-size:10px;font-weight:800;letter-spacing:.11em;text-transform:uppercase}.ecfa h2{margin:2px 0 0;font-size:17px}.ecfa header p{margin:0;max-width:520px;color:#68778a;font-size:11px;line-height:1.4}.ecfa-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:#e5eaf0}.ecfa details{background:white;padding:0}.ecfa summary{cursor:pointer;padding:12px 14px;font-size:13px;font-weight:800;color:#213a52}.form{display:grid;gap:8px;padding:0 14px 14px}.form label{display:grid;gap:3px;color:#526174;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em}.line{display:grid;grid-template-columns:1fr 2fr .8fr .8fr;gap:6px;padding:8px;background:#f8fafc;border:1px solid #e3e9ef;border-radius:9px}.line .wide{min-width:0}.row{display:grid;grid-template-columns:1fr 1fr;gap:7px}.check{display:flex!important;align-items:center;gap:7px!important;text-transform:none!important;letter-spacing:0!important;font-size:12px!important}.check input{width:17px;height:17px}.primary,.minor{border:0;border-radius:8px;padding:9px 11px;font-weight:800;cursor:pointer}.primary{background:#173f5f;color:white;min-height:42px}.primary:disabled{opacity:.55;cursor:wait}.minor{background:#edf2f7;color:#294761}.ecfa-alert{margin:10px 14px 0;border-radius:8px;padding:9px 11px;font-size:12px;font-weight:700}.ecfa-alert.error{background:#fff1f2;color:#991b1b;border:1px solid #fecdd3}.ecfa-alert.success{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0}
@media(max-width:980px){.ecfa-grid{grid-template-columns:1fr}.ecfa>header{align-items:flex-start;flex-direction:column}.line{grid-template-columns:1fr 1fr}.line .wide{grid-column:1/-1}}
@media(max-width:560px){.ecfa{margin:0 7px 10px}.row{grid-template-columns:1fr}.line{grid-template-columns:1fr 1fr}.line label:first-child,.line .wide{grid-column:1/-1}}
`;
