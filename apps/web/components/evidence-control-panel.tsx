"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type EvidenceEvent = {
  id?: number;
  eventRef?: string;
  eventType?: string;
  action?: string;
  actorName?: string;
  actorRole?: string;
  professionalRole?: string | null;
  reason?: string | null;
  justification?: string | null;
  aiSystem?: string | null;
  aiModel?: string | null;
  humanReviewer?: string | null;
  humanReviewStatus?: string | null;
  supervisorApprovalStatus?: string | null;
  overrideReason?: string | null;
  complianceDomain?: string | null;
  riskLevel?: string | null;
  sourceModule?: string | null;
  createdAt?: string | null;
};

type EvidenceControlPanelProps = {
  patientCaseId: string;
  referralEpisodeId?: string;
  episodeRef: string;
  patientName: string;
  onEvidenceChange?: () => void | Promise<void>;
};

type DecisionForm = {
  action: string;
  reason: string;
  justification: string;
  actorName: string;
  actorRole: string;
  professionalRole: string;
  riskLevel: string;
  complianceDomain: string;
  aiSystem: string;
  aiModel: string;
  aiOutputRef: string;
  humanReviewer: string;
  humanReviewStatus: string;
  overrideReason: string;
};

type EstimateForm = {
  lowerAmount: string;
  upperAmount: string;
  status: string;
  clientDecision: string;
  assumptions: string;
  exclusions: string;
  clinicianJustification: string;
};

type ConsentForm = {
  status: string;
  scope: string;
  risksDiscussed: string;
  alternativesDiscussed: string;
  costDiscussed: boolean;
  clientAuthorisedBy: string;
  witness: string;
};

const defaultDecision: DecisionForm = {
  action: "clinical/admin decision recorded",
  reason: "",
  justification: "",
  actorName: "LucyWorks UI",
  actorRole: "user",
  professionalRole: "",
  riskLevel: "amber",
  complianceDomain: "clinical_governance",
  aiSystem: "",
  aiModel: "",
  aiOutputRef: "",
  humanReviewer: "",
  humanReviewStatus: "not_required",
  overrideReason: "",
};

const defaultEstimate: EstimateForm = {
  lowerAmount: "",
  upperAmount: "",
  status: "draft",
  clientDecision: "not_recorded",
  assumptions: "",
  exclusions: "",
  clinicianJustification: "",
};

const defaultConsent: ConsentForm = {
  status: "pending",
  scope: "procedure, diagnostics, medication and referral-care plan discussed",
  risksDiscussed: "",
  alternativesDiscussed: "",
  costDiscussed: false,
  clientAuthorisedBy: "",
  witness: "",
};

function splitLines(value: string) {
  return value.split(/\n|,/).map((item) => item.trim()).filter(Boolean);
}

function money(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function stamp(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}`;
}

async function postJson(path: string, body: unknown) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path} failed: ${response.status}`);
  return response.json();
}

async function patchJson(path: string, body: unknown) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path} failed: ${response.status}`);
  return response.json();
}

export function EvidenceControlPanel({ patientCaseId, referralEpisodeId, episodeRef, patientName, onEvidenceChange }: EvidenceControlPanelProps) {
  const [events, setEvents] = useState<EvidenceEvent[]>([]);
  const [status, setStatus] = useState("idle");
  const [decision, setDecision] = useState<DecisionForm>(defaultDecision);
  const [estimate, setEstimate] = useState<EstimateForm>(defaultEstimate);
  const [consent, setConsent] = useState<ConsentForm>(defaultConsent);

  const estimateRef = useMemo(() => `estimate-${episodeRef || patientCaseId}`, [episodeRef, patientCaseId]);

  async function refresh() {
    if (!patientCaseId) return;
    try {
      const query = new URLSearchParams({ patient_case_id: patientCaseId });
      if (referralEpisodeId) query.set("referral_episode_id", referralEpisodeId);
      const response = await fetch(`${API_BASE}/api/evidence/events?${query.toString()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("events unavailable");
      const data = await response.json();
      setEvents(Array.isArray(data.events) ? data.events : []);
      setStatus("evidence online");
    } catch {
      setStatus("evidence offline");
    }
  }

  useEffect(() => { void refresh(); }, [patientCaseId, referralEpisodeId]);

  async function afterChange() {
    await refresh();
    await onEvidenceChange?.();
  }

  async function recordDecision() {
    setStatus("recording decision...");
    await postJson("/api/evidence/events", {
      eventType: "decision",
      patientCaseId,
      referralEpisodeId,
      actorName: decision.actorName,
      actorRole: decision.actorRole,
      professionalRole: decision.professionalRole || undefined,
      action: decision.action,
      reason: decision.reason || undefined,
      justification: decision.justification || undefined,
      aiSystem: decision.aiSystem || undefined,
      aiModel: decision.aiModel || undefined,
      aiOutputRef: decision.aiOutputRef || undefined,
      humanReviewer: decision.humanReviewer || undefined,
      humanReviewStatus: decision.humanReviewStatus,
      supervisorRequired: decision.riskLevel === "red" || decision.humanReviewStatus === "required",
      supervisorApprovalStatus: decision.riskLevel === "red" ? "required" : "not_required",
      overrideReason: decision.overrideReason || undefined,
      complianceDomain: decision.complianceDomain,
      riskLevel: decision.riskLevel,
      sourceModule: "patient-care",
      evidenceLinks: [{ type: "patient_case", id: patientCaseId }, { type: "referral_episode", id: referralEpisodeId || episodeRef }],
    });
    setDecision(defaultDecision);
    await afterChange();
  }

  async function recordEstimate() {
    setStatus("recording estimate...");
    const created = await postJson("/api/evidence/estimates", {
      estimateRef,
      patientCaseId,
      referralEpisodeId,
      status: estimate.status,
      lowerAmount: money(estimate.lowerAmount),
      upperAmount: money(estimate.upperAmount),
      assumptions: splitLines(estimate.assumptions),
      excludedItems: splitLines(estimate.exclusions),
      clientDecision: estimate.clientDecision,
      clinicianJustification: estimate.clinicianJustification || undefined,
      createdBy: "patient-care-ui",
    });
    await postJson("/api/evidence/events", {
      eventType: "estimate_version",
      patientCaseId,
      referralEpisodeId,
      actorName: "patient-care-ui",
      actorRole: "admin_or_clinician",
      action: `estimate ${estimate.status} / ${estimate.clientDecision}`,
      reason: "versioned estimate recorded",
      newState: created.estimate,
      complianceDomain: "client_information",
      riskLevel: estimate.clientDecision === "accepted" || estimate.status === "approved" ? "green" : "amber",
      sourceModule: "patient-care",
      evidenceLinks: [{ type: "estimate", id: estimateRef }],
    });
    if (referralEpisodeId) {
      await patchJson(`/api/patient-care/episodes/${referralEpisodeId}/state`, {
        estimateStatus: estimate.clientDecision === "accepted" || estimate.status === "approved" ? "approved" : estimate.status,
        nextAction: "estimate recorded",
        actor: "patient-care-ui",
        note: "estimate evidence recorded",
      });
    }
    setEstimate(defaultEstimate);
    await afterChange();
  }

  async function recordConsent() {
    setStatus("recording consent...");
    const consentRef = stamp(`consent-${episodeRef || patientCaseId}`);
    const created = await postJson("/api/evidence/consents", {
      consentRef,
      patientCaseId,
      referralEpisodeId,
      consentType: "procedure",
      status: consent.status,
      scope: consent.scope,
      risksDiscussed: splitLines(consent.risksDiscussed),
      alternativesDiscussed: splitLines(consent.alternativesDiscussed),
      costDiscussed: consent.costDiscussed,
      estimateRef,
      clientAuthorisedBy: consent.clientAuthorisedBy || undefined,
      recordedBy: "patient-care-ui",
      witness: consent.witness || undefined,
    });
    await postJson("/api/evidence/events", {
      eventType: "consent_record",
      patientCaseId,
      referralEpisodeId,
      actorName: "patient-care-ui",
      actorRole: "admin_or_clinician",
      action: `consent ${consent.status}`,
      reason: "client consent state recorded",
      newState: created.consent,
      clientAuthorisation: { authorisedBy: consent.clientAuthorisedBy, status: consent.status, scope: consent.scope },
      complianceDomain: "consent",
      riskLevel: consent.status === "authorised" || consent.status === "clear" || consent.status === "approved" ? "green" : "amber",
      sourceModule: "patient-care",
      evidenceLinks: [{ type: "consent", id: consentRef }, { type: "estimate", id: estimateRef }],
    });
    if (referralEpisodeId) {
      await patchJson(`/api/patient-care/episodes/${referralEpisodeId}/state`, {
        consentStatus: consent.status === "authorised" || consent.status === "approved" ? "approved" : consent.status,
        nextAction: "consent recorded",
        actor: "patient-care-ui",
        note: "consent evidence recorded",
      });
    }
    setConsent(defaultConsent);
    await afterChange();
  }

  return <section className="evidencePanel">
    <div className="evidenceHead">
      <div>
        <span>Evidence core</span>
        <h3>Decision, consent and estimate record</h3>
        <p>{patientName} · {episodeRef} · {status}</p>
      </div>
      <button type="button" onClick={() => void refresh()}>Refresh evidence</button>
    </div>

    <details open className="evidenceForm">
      <summary>Record decision / AI provenance</summary>
      <div className="formGrid">
        <label>Action<input value={decision.action} onChange={(event) => setDecision({ ...decision, action: event.target.value })} /></label>
        <label>Actor<input value={decision.actorName} onChange={(event) => setDecision({ ...decision, actorName: event.target.value })} /></label>
        <label>Professional role<input value={decision.professionalRole} onChange={(event) => setDecision({ ...decision, professionalRole: event.target.value })} placeholder="vet / RVN / admin / manager" /></label>
        <label>Risk<select value={decision.riskLevel} onChange={(event) => setDecision({ ...decision, riskLevel: event.target.value })}><option>green</option><option>amber</option><option>red</option></select></label>
        <label>Reason<textarea value={decision.reason} onChange={(event) => setDecision({ ...decision, reason: event.target.value })} /></label>
        <label>Justification<textarea value={decision.justification} onChange={(event) => setDecision({ ...decision, justification: event.target.value })} /></label>
        <label>AI system<input value={decision.aiSystem} onChange={(event) => setDecision({ ...decision, aiSystem: event.target.value })} placeholder="optional" /></label>
        <label>AI model<input value={decision.aiModel} onChange={(event) => setDecision({ ...decision, aiModel: event.target.value })} placeholder="optional" /></label>
        <label>AI output ref<input value={decision.aiOutputRef} onChange={(event) => setDecision({ ...decision, aiOutputRef: event.target.value })} placeholder="optional" /></label>
        <label>Human reviewer<input value={decision.humanReviewer} onChange={(event) => setDecision({ ...decision, humanReviewer: event.target.value })} placeholder="named reviewer" /></label>
        <label>Review status<select value={decision.humanReviewStatus} onChange={(event) => setDecision({ ...decision, humanReviewStatus: event.target.value })}><option>not_required</option><option>required</option><option>accepted</option><option>edited</option><option>rejected</option></select></label>
        <label>Override reason<input value={decision.overrideReason} onChange={(event) => setDecision({ ...decision, overrideReason: event.target.value })} placeholder="required for unsafe override" /></label>
      </div>
      <button type="button" onClick={() => void recordDecision()}>Record evidence event</button>
    </details>

    <details className="evidenceForm">
      <summary>Record estimate version</summary>
      <div className="formGrid">
        <label>Lower £<input inputMode="decimal" value={estimate.lowerAmount} onChange={(event) => setEstimate({ ...estimate, lowerAmount: event.target.value })} /></label>
        <label>Upper £<input inputMode="decimal" value={estimate.upperAmount} onChange={(event) => setEstimate({ ...estimate, upperAmount: event.target.value })} /></label>
        <label>Status<select value={estimate.status} onChange={(event) => setEstimate({ ...estimate, status: event.target.value })}><option>draft</option><option>presented</option><option>approved</option><option>changed</option><option>withdrawn</option></select></label>
        <label>Client decision<select value={estimate.clientDecision} onChange={(event) => setEstimate({ ...estimate, clientDecision: event.target.value })}><option>not_recorded</option><option>accepted</option><option>declined</option><option>unable_to_contact</option><option>emergency_authority</option></select></label>
        <label>Assumptions<textarea value={estimate.assumptions} onChange={(event) => setEstimate({ ...estimate, assumptions: event.target.value })} placeholder="one per line" /></label>
        <label>Excluded items<textarea value={estimate.exclusions} onChange={(event) => setEstimate({ ...estimate, exclusions: event.target.value })} placeholder="one per line" /></label>
        <label>Clinician justification<textarea value={estimate.clinicianJustification} onChange={(event) => setEstimate({ ...estimate, clinicianJustification: event.target.value })} /></label>
      </div>
      <button type="button" onClick={() => void recordEstimate()}>Save estimate version</button>
    </details>

    <details className="evidenceForm">
      <summary>Record consent</summary>
      <div className="formGrid">
        <label>Status<select value={consent.status} onChange={(event) => setConsent({ ...consent, status: event.target.value })}><option>pending</option><option>authorised</option><option>approved</option><option>declined</option><option>verbal</option><option>emergency_authority</option></select></label>
        <label>Authorised by<input value={consent.clientAuthorisedBy} onChange={(event) => setConsent({ ...consent, clientAuthorisedBy: event.target.value })} /></label>
        <label>Witness<input value={consent.witness} onChange={(event) => setConsent({ ...consent, witness: event.target.value })} /></label>
        <label className="check"><input type="checkbox" checked={consent.costDiscussed} onChange={(event) => setConsent({ ...consent, costDiscussed: event.target.checked })} /> Cost discussed</label>
        <label>Scope<textarea value={consent.scope} onChange={(event) => setConsent({ ...consent, scope: event.target.value })} /></label>
        <label>Risks discussed<textarea value={consent.risksDiscussed} onChange={(event) => setConsent({ ...consent, risksDiscussed: event.target.value })} placeholder="one per line" /></label>
        <label>Alternatives discussed<textarea value={consent.alternativesDiscussed} onChange={(event) => setConsent({ ...consent, alternativesDiscussed: event.target.value })} placeholder="one per line" /></label>
      </div>
      <button type="button" onClick={() => void recordConsent()}>Save consent record</button>
    </details>

    <section className="eventList">
      <h3>Evidence timeline</h3>
      {events.length ? events.slice(0, 10).map((event) => <article key={event.eventRef || event.id}>
        <time>{event.createdAt ? new Date(event.createdAt).toLocaleString([], { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" }) : "recorded"}</time>
        <div>
          <b>{event.action || event.eventType}</b>
          <p>{event.reason || event.justification || "No reason recorded"}</p>
          <small>{event.actorName || "system"} · {event.professionalRole || event.actorRole || "role not set"} · {event.complianceDomain || "domain not set"} · {event.riskLevel || "risk not set"}</small>
          {event.aiSystem || event.aiModel ? <small>AI: {event.aiSystem || "AI"} {event.aiModel || ""} · review {event.humanReviewStatus || "not recorded"}</small> : null}
          {event.overrideReason ? <small>Override: {event.overrideReason}</small> : null}
        </div>
      </article>) : <p className="empty">No evidence events recorded for this episode yet.</p>}
    </section>
  </section>;
}
