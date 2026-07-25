from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, SENIOR_ROLES, require_authenticated, require_roles
from app.database import get_session
from app.detailed_hospital_models import (
    AnaesthesiaChartV8,
    ClinicalDocumentV8,
    CommunicationEventV8,
    EstimateV8,
    InpatientCarePlanV8,
    InpatientChartEntryV8,
    PatientClinicalRecordV8,
    PatientOwnerLinkV8,
    ProcedureRecordV8,
)
from app.evidence_service import create_evidence_event
from app.hospital_command_models import (
    ConsentAuthorisationV9,
    EpisodeCheckpointV9,
    EpisodeClosureV9,
    EpisodeHandoverV9,
    EpisodeTransitionV9,
    ReferralIntakeV9,
)
from app.hospital_ops_models import BoardChangeEvent, CanonicalEpisodeState, OperationalBlock, OperationalCommand
from app.v7_event_service import publish_event

router = APIRouter(prefix="/api/v9", tags=["hospital-command-spine-v9"])

PHASES = [
    "referral_received", "intake", "triage", "consult", "admitted", "diagnostics",
    "awaiting_results", "awaiting_consent", "scheduled", "prep", "anaesthesia",
    "procedure", "recovery", "ward", "icu", "discharge_ready", "discharged", "closed",
]
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "referral_received": {"intake", "triage", "closed"},
    "intake": {"triage", "consult", "closed"},
    "triage": {"consult", "admitted", "diagnostics", "closed"},
    "consult": {"admitted", "diagnostics", "awaiting_consent", "discharge_ready", "closed"},
    "admitted": {"diagnostics", "awaiting_consent", "scheduled", "ward", "icu"},
    "diagnostics": {"awaiting_results", "awaiting_consent", "scheduled", "ward", "icu"},
    "awaiting_results": {"awaiting_consent", "scheduled", "ward", "icu", "discharge_ready"},
    "awaiting_consent": {"scheduled", "ward", "icu", "discharge_ready"},
    "scheduled": {"prep", "anaesthesia", "procedure", "ward", "icu"},
    "prep": {"scheduled", "anaesthesia", "procedure"},
    "anaesthesia": {"procedure", "recovery"},
    "procedure": {"recovery", "ward", "icu"},
    "recovery": {"ward", "icu", "discharge_ready"},
    "ward": {"diagnostics", "scheduled", "icu", "discharge_ready"},
    "icu": {"diagnostics", "scheduled", "ward", "discharge_ready"},
    "discharge_ready": {"discharged", "ward", "icu"},
    "discharged": {"closed"},
    "closed": set(),
}
PHASE_OWNERS = {
    "referral_received": "admin", "intake": "admin", "triage": "clinician", "consult": "clinician",
    "admitted": "clinician", "diagnostics": "clinician", "awaiting_results": "clinician",
    "awaiting_consent": "clinician", "scheduled": "ops_manager", "prep": "nurse",
    "anaesthesia": "clinician", "procedure": "clinician", "recovery": "nurse", "ward": "nurse",
    "icu": "nurse", "discharge_ready": "clinician", "discharged": "admin", "closed": "admin",
}
TRANSITION_ROLES: dict[str, set[str]] = {
    "referral_received": {"admin", "ops_manager", "clinician"},
    "intake": {"admin", "ops_manager", "clinician"},
    "triage": set(CLINICAL_ROLES) | {"ops_manager"},
    "consult": set(CLINICAL_ROLES),
    "admitted": set(CLINICAL_ROLES),
    "diagnostics": set(CLINICAL_ROLES),
    "awaiting_results": set(CLINICAL_ROLES),
    "awaiting_consent": set(CLINICAL_ROLES),
    "scheduled": set(CLINICAL_ROLES) | {"ops_manager"},
    "prep": set(CLINICAL_ROLES) | {"ops_manager"},
    "anaesthesia": set(CLINICAL_ROLES),
    "procedure": {"clinician", "clinical_director", "senior_clinician", "supervisor"},
    "recovery": set(CLINICAL_ROLES),
    "ward": set(CLINICAL_ROLES),
    "icu": set(CLINICAL_ROLES),
    "discharge_ready": set(CLINICAL_ROLES),
    "discharged": set(CLINICAL_ROLES) | {"admin", "ops_manager"},
    "closed": set(SENIOR_ROLES) | {"admin"},
}
HANDOVER_REQUIRED_PHASES = {"anaesthesia", "procedure", "recovery", "ward", "icu", "discharged"}
CONSENT_REQUIREMENTS = {
    "admitted": {"admission", "treatment"},
    "diagnostics": {"diagnostics", "treatment"},
    "scheduled": {"procedure", "anaesthesia", "treatment"},
    "prep": {"procedure", "anaesthesia", "treatment"},
    "anaesthesia": {"anaesthesia", "procedure"},
    "procedure": {"procedure"},
}
FINANCIAL_CLOSURE_STATES = {"settled", "insured_pending", "transferred", "written_off", "no_charge"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    data = row.model_dump(mode="json")
    if data:
        return data
    from sqlalchemy import inspect as sa_inspect
    state = sa_inspect(row)
    return {attribute.key: getattr(row, attribute.key) for attribute in state.mapper.column_attrs}


def record_evidence(
    session: Session, *, entity_type: str, entity_ref: str, action: str, episode_ref: str | None,
    patient_ref: str | None, previous: Any, current: Any, reason: str, risk: str = "amber",
) -> str:
    evidence, _ = create_evidence_event(
        session,
        event_type=f"v9_{entity_type}_{action}",
        action=action,
        patient_case_id=patient_ref,
        referral_episode_id=episode_ref,
        previous_state=previous,
        new_state=current,
        reason=reason,
        compliance_domain="hospital_command",
        risk_level=risk,
        source_module="hospital-command-spine-v9",
        source_record_ref=entity_ref,
        correlation_id=episode_ref or patient_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"v9:{entity_type}:{entity_ref}:{action}:{current.get('version', current.get('status', 'event')) if isinstance(current, dict) else 'event'}",
    )
    publish_event(
        session,
        event_type=f"v9_{entity_type}_{action}",
        aggregate_type=entity_type,
        aggregate_ref=entity_ref,
        payload=current if isinstance(current, dict) else {"value": current},
        severity="error" if risk == "red" else "warning" if risk == "amber" else "info",
        correlation_id=episode_ref or patient_ref,
        idempotency_key=f"v9-event:{evidence.event_ref}",
    )
    return evidence.event_ref


def require_episode(session: Session, episode_ref: str, *, lock: bool = False) -> CanonicalEpisodeState:
    query = select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)
    if lock and session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    return row


def require_patient(session: Session, patient_ref: str) -> PatientClinicalRecordV8:
    row = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == patient_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="patient record not found")
    return row


def active_owner_link(session: Session, patient_ref: str, owner_ref: str | None = None) -> PatientOwnerLinkV8 | None:
    query = select(PatientOwnerLinkV8).where(
        PatientOwnerLinkV8.patient_ref == patient_ref,
        PatientOwnerLinkV8.active == True,  # noqa: E712
        PatientOwnerLinkV8.decision_authority == True,  # noqa: E712
    )
    if owner_ref:
        query = query.where(PatientOwnerLinkV8.owner_ref == owner_ref)
    return session.exec(query.order_by(PatientOwnerLinkV8.starts_at.desc())).first()


def active_consents(session: Session, episode_ref: str) -> list[ConsentAuthorisationV9]:
    now = utc_now()
    rows = session.exec(select(ConsentAuthorisationV9).where(
        ConsentAuthorisationV9.episode_ref == episode_ref,
        ConsentAuthorisationV9.status == "active",
    )).all()
    return [row for row in rows if row.valid_from <= now and (row.valid_until is None or row.valid_until >= now)]


def latest_waivers(session: Session, episode_ref: str) -> dict[str, EpisodeCheckpointV9]:
    now = utc_now()
    rows = session.exec(select(EpisodeCheckpointV9).where(
        EpisodeCheckpointV9.episode_ref == episode_ref,
        EpisodeCheckpointV9.status == "waived",
    ).order_by(EpisodeCheckpointV9.created_at.desc())).all()
    result: dict[str, EpisodeCheckpointV9] = {}
    for row in rows:
        if row.checkpoint_code not in result and (row.valid_until is None or row.valid_until >= now):
            result[row.checkpoint_code] = row
    return result


def _latest_entries(entries: list[InpatientChartEntryV8]) -> list[InpatientChartEntryV8]:
    latest: dict[str, InpatientChartEntryV8] = {}
    for row in sorted(entries, key=lambda item: item.recorded_at, reverse=True):
        latest.setdefault(row.care_plan_ref, row)
    return list(latest.values())


def gate(code: str, detail: str, owner_role: str, refs: list[str] | None = None) -> dict[str, Any]:
    return {"code": code, "detail": detail, "ownerRole": owner_role, "relatedRefs": refs or []}


def evaluate_guard(session: Session, episode: CanonicalEpisodeState, target_phase: str) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    waived = latest_waivers(session, episode.episode_ref)

    def block(code: str, detail: str, owner_role: str, refs: list[str] | None = None) -> None:
        item = gate(code, detail, owner_role, refs)
        if code in waived:
            warnings.append({**item, "waivedByCheckpoint": waived[code].checkpoint_ref})
        else:
            blockers.append(item)

    if target_phase not in PHASES:
        block("unknown_target_phase", f"Unknown target phase {target_phase}", "ops_manager")
    if target_phase not in ALLOWED_TRANSITIONS.get(episode.phase, set()):
        block("transition_graph", f"Cannot move {episode.phase} to {target_phase}", PHASE_OWNERS.get(episode.phase, "ops_manager"))

    patient = None
    if episode.patient_ref:
        patient = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == episode.patient_ref)).first()
    if target_phase not in {"referral_received", "closed"} and not patient:
        block("patient_identity", "Canonical episode is not linked to a detailed patient record", "admin")

    referral = session.exec(select(ReferralIntakeV9).where(ReferralIntakeV9.episode_ref == episode.episode_ref)).first()
    if target_phase != "closed" and not referral:
        block("referral_intake", "No governed referral intake exists", "admin")
    elif referral and target_phase in set(PHASES[PHASES.index("consult"):]) and referral.status != "accepted":
        block("referral_acceptance", f"Referral status is {referral.status}", "clinician", [referral.referral_ref])

    owner_link = active_owner_link(session, episode.patient_ref) if episode.patient_ref else None
    if target_phase in set(PHASES[PHASES.index("consult"):]) and not owner_link:
        block("decision_authority", "No active owner link with clinical decision authority", "admin")

    required_consents = CONSENT_REQUIREMENTS.get(target_phase)
    consents = active_consents(session, episode.episode_ref)
    if required_consents and not any(row.consent_type in required_consents for row in consents):
        block("consent", f"Active consent required: {', '.join(sorted(required_consents))}", "clinician")

    blocks = session.exec(select(OperationalBlock).where(OperationalBlock.episode_ref == episode.episode_ref)).all()
    if target_phase in {"scheduled", "prep", "anaesthesia", "procedure"} and not blocks:
        block("operational_schedule", "No canonical operational block exists", "ops_manager")

    charts = session.exec(select(AnaesthesiaChartV8).where(AnaesthesiaChartV8.episode_ref == episode.episode_ref)).all()
    procedures = session.exec(select(ProcedureRecordV8).where(ProcedureRecordV8.episode_ref == episode.episode_ref)).all()
    care_plans = session.exec(select(InpatientCarePlanV8).where(InpatientCarePlanV8.episode_ref == episode.episode_ref)).all()
    chart_entries = session.exec(select(InpatientChartEntryV8).where(InpatientChartEntryV8.episode_ref == episode.episode_ref)).all()
    documents = session.exec(select(ClinicalDocumentV8).where(ClinicalDocumentV8.episode_ref == episode.episode_ref)).all()
    communications = session.exec(select(CommunicationEventV8).where(CommunicationEventV8.episode_ref == episode.episode_ref)).all()
    handovers = session.exec(select(EpisodeHandoverV9).where(EpisodeHandoverV9.episode_ref == episode.episode_ref)).all()
    estimates = session.exec(select(EstimateV8).where(EstimateV8.episode_ref == episode.episode_ref)).all()

    if target_phase == "anaesthesia" and not any(row.status in {"induced", "maintenance"} for row in charts):
        block("anaesthesia_induction", "No detailed anaesthesia chart is in induced or maintenance state", "clinician")
    if target_phase == "procedure" and not any(row.status in {"in_progress", "started"} for row in procedures):
        block("procedure_started", "No detailed procedure record is in progress", "clinician")
    if target_phase == "recovery":
        procedure_complete = any(row.status == "completed" for row in procedures)
        anaesthesia_recovery = any(row.status in {"recovery", "completed"} for row in charts)
        if not procedure_complete and not anaesthesia_recovery:
            block("recovery_entry", "Neither procedure completion nor anaesthesia recovery is recorded", "clinician")
    if target_phase in {"ward", "icu"} and not any(row.status == "active" for row in care_plans):
        block("inpatient_plan", "No active inpatient care plan exists", "nurse")

    target_owner = PHASE_OWNERS.get(target_phase, episode.owner_role)
    if target_phase in HANDOVER_REQUIRED_PHASES and target_owner != episode.owner_role:
        acknowledged = [row for row in handovers if row.status == "acknowledged" and row.to_role == target_owner]
        if not acknowledged:
            block("handover", f"Acknowledged handover to {target_owner} is required", target_owner)

    if target_phase in {"discharge_ready", "discharged", "closed"}:
        active_plans = [row for row in care_plans if row.status == "active"]
        if active_plans:
            block("active_inpatient_plan", "Active inpatient care plans remain open", "nurse", [row.care_plan_ref for row in active_plans])
        red_latest = [row for row in _latest_entries(chart_entries) if row.concern_level == "red"]
        if red_latest:
            block("red_inpatient_concern", "Latest inpatient chart state contains a red concern", "clinician", [row.entry_ref for row in red_latest])
        incomplete_procedures = [row for row in procedures if row.status not in {"completed", "cancelled"}]
        if incomplete_procedures:
            block("procedure_incomplete", "Procedure records remain incomplete", "clinician", [row.procedure_ref for row in incomplete_procedures])
        incomplete_charts = [row for row in charts if row.status != "completed"]
        if incomplete_charts:
            block("anaesthesia_incomplete", "Anaesthesia charts remain incomplete", "clinician", [row.chart_ref for row in incomplete_charts])
        discharge_docs = [row for row in documents if row.document_type in {"discharge", "discharge_summary", "owner_instructions"}]
        if not any(row.status in {"approved", "sent"} for row in discharge_docs):
            block("discharge_document", "No approved discharge document exists", "clinician")
        owner_comms = [row for row in communications if row.audience == "owner" and row.direction == "outbound"]
        if not owner_comms:
            block("owner_communication", "No outbound owner communication is recorded", "clinician")
        referrer_comms = [row for row in communications if row.audience in {"referring_vet", "referrer"} and row.direction == "outbound"]
        if not referrer_comms:
            warnings.append(gate("referrer_communication", "No outbound referring-vet communication is recorded", "clinician"))
        if estimates and not any(row.status == "approved" for row in estimates):
            warnings.append(gate("estimate_status", "Estimates exist but none is approved", "admin", [row.estimate_ref for row in estimates]))

    if target_phase == "discharged":
        discharge_docs = [row for row in documents if row.document_type in {"discharge", "discharge_summary", "owner_instructions"}]
        if not any(row.status == "sent" for row in discharge_docs):
            block("discharge_document_sent", "Discharge documentation has not been sent", "admin")

    if target_phase == "closed":
        closure = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == episode.episode_ref)).first()
        if not closure or closure.status != "approved":
            block("closure_approval", "Approved episode closure record is required", "ops_manager")
        elif closure.outstanding_actions:
            block("closure_actions", "Closure record contains outstanding actions", "ops_manager", [closure.closure_ref])
        open_handovers = [row for row in handovers if row.status == "offered"]
        if open_handovers:
            block("open_handover", "Unacknowledged handovers remain open", "ops_manager", [row.handover_ref for row in open_handovers])

    return {
        "episodeRef": episode.episode_ref,
        "currentPhase": episode.phase,
        "targetPhase": target_phase,
        "allowedByGraph": target_phase in ALLOWED_TRANSITIONS.get(episode.phase, set()),
        "canTransition": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "targetOwnerRole": PHASE_OWNERS.get(target_phase, episode.owner_role),
        "waivers": [row_dict(row) for row in waived.values()],
    }


class ReferralCreate(BaseModel):
    referral_ref: str | None = None
    episode_ref: str | None = None
    patient_ref: str
    premises_ref: str
    source_type: str = "referring_vet"
    source_organisation: str | None = None
    source_contact_name: str | None = None
    source_contact_email: str | None = None
    source_contact_phone: str | None = None
    requested_service: str
    presenting_problem: str
    clinical_summary: str = ""
    urgency: str = "routine"
    requested_timeframe: str | None = None
    attachments: list[dict[str, Any]] = PydanticField(default_factory=list)
    reason: str


class ReferralDecision(BaseModel):
    expected_version: int
    status: str
    reason: str


class ConsentCreate(BaseModel):
    owner_ref: str
    consent_type: str
    scope: dict[str, Any] = PydanticField(default_factory=dict)
    maximum_authorised_pence: int | None = None
    currency: str = "GBP"
    decision_maker_name: str
    captured_channel: str
    valid_until: datetime | None = None
    reason: str


class VersionedReason(BaseModel):
    expected_version: int
    reason: str


class HandoverCreate(BaseModel):
    to_role: str
    to_subject: str | None = None
    from_area_ref: str | None = None
    to_area_ref: str | None = None
    priority: str = "amber"
    situation: str
    background: str = ""
    assessment: str = ""
    recommendation: str = ""
    risks: list[dict[str, Any]] = PydanticField(default_factory=list)
    pending_actions: list[dict[str, Any]] = PydanticField(default_factory=list)
    reason: str


class CheckpointCreate(BaseModel):
    checkpoint_code: str
    status: str = "passed"
    detail: dict[str, Any] = PydanticField(default_factory=dict)
    reason: str
    valid_until: datetime | None = None
    supersedes_checkpoint_ref: str | None = None


class TransitionCommand(BaseModel):
    expected_version: int
    target_phase: str
    idempotency_key: str
    current_area_ref: str | None = None
    reason: str


class ClosurePrepare(BaseModel):
    disposition: str
    discharge_document_ref: str | None = None
    owner_communication_ref: str | None = None
    referrer_communication_ref: str | None = None
    final_estimate_ref: str | None = None
    financial_status: str
    outstanding_actions: list[dict[str, Any]] = PydanticField(default_factory=list)
    retained_risks: list[dict[str, Any]] = PydanticField(default_factory=list)
    reason: str


@router.get("/episode-state-machine")
def state_machine_spec(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {
        "states": PHASES,
        "allowedTransitions": {key: sorted(value) for key, value in ALLOWED_TRANSITIONS.items()},
        "phaseOwners": PHASE_OWNERS,
        "invariant": "CanonicalEpisodeState is the single episode phase authority; every transition is versioned, gated and evidenced.",
        "requestedBy": auth.subject,
    }


@router.post("/referrals")
def create_referral(payload: ReferralCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles("admin", "ops_manager", "clinician", "clinical_director", "senior_clinician"))) -> dict[str, Any]:
    patient = require_patient(session, payload.patient_ref)
    episode_ref = payload.episode_ref or new_ref("episode")
    referral_ref = payload.referral_ref or new_ref("referral")
    if session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first():
        raise HTTPException(status_code=409, detail="canonical episode already exists")
    row = ReferralIntakeV9(
        referral_ref=referral_ref,
        episode_ref=episode_ref,
        patient_ref=payload.patient_ref,
        premises_ref=payload.premises_ref,
        source_type=payload.source_type,
        source_organisation=payload.source_organisation,
        source_contact_name=payload.source_contact_name,
        source_contact_email=payload.source_contact_email,
        source_contact_phone=payload.source_contact_phone,
        requested_service=payload.requested_service,
        presenting_problem=payload.presenting_problem,
        clinical_summary=payload.clinical_summary,
        urgency=payload.urgency,
        requested_timeframe=payload.requested_timeframe,
        attachments=payload.attachments,
        created_by_subject=auth.subject,
    )
    episode = CanonicalEpisodeState(
        episode_ref=episode_ref,
        patient_ref=payload.patient_ref,
        patient_name=patient.display_name,
        premises_ref=payload.premises_ref,
        service_line=payload.requested_service,
        urgency=payload.urgency,
        phase="referral_received",
        status="active",
        owner_role="admin",
        owner_subject=auth.subject,
        next_action="Clinical referral acceptance decision",
    )
    session.add(row)
    session.add(episode)
    session.flush()
    row.evidence_event_ref = record_evidence(
        session, entity_type="referral", entity_ref=referral_ref, action="received",
        episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None,
        current=row_dict(row), reason=payload.reason, risk="amber" if payload.urgency in {"urgent", "emergency", "red"} else "green",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    session.refresh(episode)
    return {"referral": row_dict(row), "episode": row_dict(episode)}


@router.patch("/referrals/{referral_ref}")
def decide_referral(referral_ref: str, payload: ReferralDecision, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles("clinician", "clinical_director", "senior_clinician", "supervisor"))) -> dict[str, Any]:
    query = select(ReferralIntakeV9).where(ReferralIntakeV9.referral_ref == referral_ref)
    if session.get_bind().dialect.name == "postgresql": query = query.with_for_update()
    row = session.exec(query).first()
    if not row: raise HTTPException(status_code=404, detail="referral not found")
    if row.version != payload.expected_version: raise HTTPException(status_code=409, detail={"message": "stale referral", "currentVersion": row.version})
    if payload.status not in {"accepted", "declined", "needs_information"}: raise HTTPException(status_code=422, detail="unsupported referral status")
    previous = row_dict(row)
    row.status = payload.status
    row.acceptance_reason = payload.reason
    row.accepted_by_subject = auth.subject
    row.accepted_at = utc_now() if payload.status == "accepted" else None
    row.version += 1
    row.updated_at = utc_now()
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="referral", entity_ref=referral_ref, action=payload.status, episode_ref=row.episode_ref, patient_ref=row.patient_ref, previous=previous, current=row_dict(row), reason=payload.reason, risk="amber")
    session.add(row)
    session.commit(); session.refresh(row)
    return {"referral": row_dict(row)}


@router.post("/episodes/{episode_ref}/consents")
def create_consent(episode_ref: str, payload: ConsentCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles("admin", "clinician", "clinical_director", "senior_clinician", "supervisor"))) -> dict[str, Any]:
    episode = require_episode(session, episode_ref)
    if not episode.patient_ref: raise HTTPException(status_code=409, detail="episode has no patient reference")
    link = active_owner_link(session, episode.patient_ref, payload.owner_ref)
    if not link: raise HTTPException(status_code=409, detail="owner does not have active clinical decision authority")
    if payload.maximum_authorised_pence is not None and payload.maximum_authorised_pence < 0: raise HTTPException(status_code=422, detail="maximum authorised amount cannot be negative")
    row = ConsentAuthorisationV9(
        consent_ref=new_ref("consent"), episode_ref=episode_ref, patient_ref=episode.patient_ref,
        owner_ref=payload.owner_ref, authority_link_ref=link.link_ref, consent_type=payload.consent_type,
        scope=payload.scope, maximum_authorised_pence=payload.maximum_authorised_pence,
        currency=payload.currency, decision_maker_name=payload.decision_maker_name,
        captured_channel=payload.captured_channel, captured_by_subject=auth.subject,
        valid_until=payload.valid_until,
    )
    session.add(row); session.flush()
    row.evidence_event_ref = record_evidence(session, entity_type="consent", entity_ref=row.consent_ref, action="captured", episode_ref=episode_ref, patient_ref=episode.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"consent": row_dict(row)}


@router.patch("/consents/{consent_ref}/withdraw")
def withdraw_consent(consent_ref: str, payload: VersionedReason, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles("admin", "clinician", "clinical_director", "senior_clinician", "supervisor"))) -> dict[str, Any]:
    query = select(ConsentAuthorisationV9).where(ConsentAuthorisationV9.consent_ref == consent_ref)
    if session.get_bind().dialect.name == "postgresql": query = query.with_for_update()
    row = session.exec(query).first()
    if not row: raise HTTPException(status_code=404, detail="consent not found")
    if row.version != payload.expected_version: raise HTTPException(status_code=409, detail={"message": "stale consent", "currentVersion": row.version})
    if row.status != "active": raise HTTPException(status_code=409, detail="only active consent can be withdrawn")
    previous = row_dict(row)
    row.status = "withdrawn"; row.withdrawn_at = utc_now(); row.withdrawal_reason = payload.reason; row.version += 1; row.updated_at = utc_now()
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="consent", entity_ref=consent_ref, action="withdrawn", episode_ref=row.episode_ref, patient_ref=row.patient_ref, previous=previous, current=row_dict(row), reason=payload.reason, risk="red")
    session.add(row); session.commit(); session.refresh(row)
    return {"consent": row_dict(row)}


@router.post("/episodes/{episode_ref}/handovers")
def create_handover(episode_ref: str, payload: HandoverCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    episode = require_episode(session, episode_ref)
    if payload.to_role not in PHASE_OWNERS.values() and payload.to_role not in {"clinical_director", "senior_clinician", "supervisor", "ops_manager"}: raise HTTPException(status_code=422, detail="unsupported handover role")
    row = EpisodeHandoverV9(
        handover_ref=new_ref("handover"), episode_ref=episode_ref, patient_ref=episode.patient_ref,
        phase=episode.phase, from_role=auth.role, from_subject=auth.subject,
        from_area_ref=payload.from_area_ref or episode.current_area_ref, to_role=payload.to_role,
        to_subject=payload.to_subject, to_area_ref=payload.to_area_ref, priority=payload.priority,
        situation=payload.situation, background=payload.background, assessment=payload.assessment,
        recommendation=payload.recommendation, risks=payload.risks, pending_actions=payload.pending_actions,
    )
    session.add(row); session.flush()
    row.evidence_event_ref = record_evidence(session, entity_type="handover", entity_ref=row.handover_ref, action="offered", episode_ref=episode_ref, patient_ref=episode.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="red" if payload.priority == "red" else "amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"handover": row_dict(row)}


@router.patch("/handovers/{handover_ref}/acknowledge")
def acknowledge_handover(handover_ref: str, payload: VersionedReason, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    query = select(EpisodeHandoverV9).where(EpisodeHandoverV9.handover_ref == handover_ref)
    if session.get_bind().dialect.name == "postgresql": query = query.with_for_update()
    row = session.exec(query).first()
    if not row: raise HTTPException(status_code=404, detail="handover not found")
    if row.version != payload.expected_version: raise HTTPException(status_code=409, detail={"message": "stale handover", "currentVersion": row.version})
    if row.status != "offered": raise HTTPException(status_code=409, detail="handover is not awaiting acknowledgement")
    if auth.role != row.to_role and auth.role not in SENIOR_ROLES: raise HTTPException(status_code=403, detail="handover must be acknowledged by the receiving role")
    previous = row_dict(row)
    row.status = "acknowledged"; row.acknowledged_by_subject = auth.subject; row.acknowledged_at = utc_now(); row.version += 1
    session.add(row)
    episode = require_episode(session, row.episode_ref, lock=True)
    episode.owner_role = row.to_role; episode.owner_subject = auth.subject
    if row.to_area_ref: episode.current_area_ref = row.to_area_ref
    episode.version += 1; episode.updated_at = utc_now(); episode.last_command_ref = row.handover_ref
    session.add(episode)
    row.evidence_event_ref = record_evidence(session, entity_type="handover", entity_ref=handover_ref, action="acknowledged", episode_ref=row.episode_ref, patient_ref=row.patient_ref, previous=previous, current=row_dict(row), reason=payload.reason, risk="amber")
    session.add(row); session.commit(); session.refresh(row); session.refresh(episode)
    return {"handover": row_dict(row), "episode": row_dict(episode)}


@router.post("/episodes/{episode_ref}/checkpoints")
def create_checkpoint(episode_ref: str, payload: CheckpointCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*SENIOR_ROLES))) -> dict[str, Any]:
    episode = require_episode(session, episode_ref)
    if payload.status not in {"passed", "failed", "waived"}: raise HTTPException(status_code=422, detail="checkpoint status must be passed, failed or waived")
    if payload.status == "waived" and not payload.reason.strip(): raise HTTPException(status_code=422, detail="waiver reason is required")
    row = EpisodeCheckpointV9(
        checkpoint_ref=new_ref("checkpoint"), episode_ref=episode_ref,
        checkpoint_code=payload.checkpoint_code, status=payload.status, detail=payload.detail,
        verified_by_subject=auth.subject, verified_by_role=auth.role, reason=payload.reason,
        valid_until=payload.valid_until, supersedes_checkpoint_ref=payload.supersedes_checkpoint_ref,
    )
    session.add(row); session.flush()
    row.evidence_event_ref = record_evidence(session, entity_type="checkpoint", entity_ref=row.checkpoint_ref, action=payload.status, episode_ref=episode_ref, patient_ref=episode.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="red" if payload.status == "waived" else "amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"checkpoint": row_dict(row)}


@router.get("/episodes/{episode_ref}/transition-guard/{target_phase}")
def transition_guard(episode_ref: str, target_phase: str, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    episode = require_episode(session, episode_ref)
    result = evaluate_guard(session, episode, target_phase)
    result["requestedBy"] = auth.subject
    return result


@router.post("/episodes/{episode_ref}/transition")
def transition_episode(episode_ref: str, payload: TransitionCommand, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    existing = session.exec(select(OperationalCommand).where(OperationalCommand.idempotency_key == payload.idempotency_key)).first()
    if existing:
        if existing.target_ref != episode_ref: raise HTTPException(status_code=409, detail="idempotency key belongs to another target")
        return json.loads(existing.result_json or "{}")
    if payload.target_phase not in TRANSITION_ROLES or auth.role not in TRANSITION_ROLES[payload.target_phase]:
        raise HTTPException(status_code=403, detail=f"role {auth.role} cannot transition an episode to {payload.target_phase}")
    episode = require_episode(session, episode_ref, lock=True)
    if episode.version != payload.expected_version: raise HTTPException(status_code=409, detail={"message": "stale canonical episode", "currentVersion": episode.version})
    command = OperationalCommand(
        command_ref=new_ref("command"), command_type="episode_transition_v9", target_type="canonical_episode",
        target_ref=episode_ref, expected_version=payload.expected_version,
        request_json=payload.model_dump_json(), status="received", idempotency_key=payload.idempotency_key,
        actor_subject=auth.subject, actor_name=auth.actor_name, actor_role=auth.role, auth_source=auth.auth_source,
    )
    session.add(command); session.flush()
    guard = evaluate_guard(session, episode, payload.target_phase)
    transition = EpisodeTransitionV9(
        transition_ref=new_ref("transition"), episode_ref=episode_ref, patient_ref=episode.patient_ref,
        from_phase=episode.phase, to_phase=payload.target_phase, command_ref=command.command_ref,
        status="blocked" if not guard["canTransition"] else "completed", blockers=guard["blockers"], warnings=guard["warnings"],
        actor_subject=auth.subject, actor_role=auth.role, reason=payload.reason,
        completed_at=utc_now() if guard["canTransition"] else None,
    )
    if not guard["canTransition"]:
        result = {"ok": False, "episodeRef": episode_ref, "commandRef": command.command_ref, "guard": guard}
        command.status = "rejected"; command.result_json = json.dumps(result, default=str); command.completed_at = utc_now()
        session.add(transition); session.add(command); session.flush()
        transition.evidence_event_ref = record_evidence(session, entity_type="episode_transition", entity_ref=transition.transition_ref, action="blocked", episode_ref=episode_ref, patient_ref=episode.patient_ref, previous={"phase": episode.phase, "version": episode.version}, current=result, reason=payload.reason, risk="red")
        command.evidence_event_ref = transition.evidence_event_ref
        session.add(transition); session.add(command); session.commit()
        return result
    previous = row_dict(episode)
    episode.phase = payload.target_phase
    episode.status = "closed" if payload.target_phase == "closed" else "active"
    episode.owner_role = PHASE_OWNERS[payload.target_phase]
    episode.owner_subject = auth.subject
    if payload.current_area_ref is not None: episode.current_area_ref = payload.current_area_ref
    episode.next_action = None
    episode.gates_json = json.dumps({"lastGuard": guard}, default=str)
    episode.version += 1; episode.last_command_ref = command.command_ref; episode.updated_at = utc_now()
    if payload.target_phase == "closed":
        closure = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == episode_ref)).first()
        if closure:
            closure.status = "completed"; closure.completed_at = utc_now(); closure.version += 1; closure.updated_at = utc_now(); session.add(closure)
    result = {"ok": True, "episode": row_dict(episode), "commandRef": command.command_ref, "guard": guard}
    command.status = "completed"; command.result_json = json.dumps(result, default=str); command.completed_at = utc_now()
    session.add(episode); session.add(transition); session.add(command); session.flush()
    transition.evidence_event_ref = record_evidence(session, entity_type="episode_transition", entity_ref=transition.transition_ref, action="completed", episode_ref=episode_ref, patient_ref=episode.patient_ref, previous=previous, current=row_dict(episode), reason=payload.reason, risk="amber")
    command.evidence_event_ref = transition.evidence_event_ref
    session.add(BoardChangeEvent(event_ref=new_ref("board-event"), premises_ref=episode.premises_ref, operational_date=date.today(), event_type="episode_transitioned_v9", entity_type="canonical_episode", entity_ref=episode_ref, entity_version=episode.version, command_ref=command.command_ref, payload_json=json.dumps(result, default=str)))
    session.add(transition); session.add(command); session.commit(); session.refresh(episode)
    result["episode"] = row_dict(episode)
    return result


@router.post("/episodes/{episode_ref}/closure")
def prepare_closure(episode_ref: str, payload: ClosurePrepare, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles("admin", "ops_manager", "clinician", "clinical_director", "senior_clinician", "supervisor"))) -> dict[str, Any]:
    episode = require_episode(session, episode_ref)
    if not episode.patient_ref: raise HTTPException(status_code=409, detail="episode has no patient reference")
    existing = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == episode_ref)).first()
    if existing: raise HTTPException(status_code=409, detail={"message": "closure already exists", "closureRef": existing.closure_ref})
    row = EpisodeClosureV9(
        closure_ref=new_ref("closure"), episode_ref=episode_ref, patient_ref=episode.patient_ref,
        disposition=payload.disposition, discharge_document_ref=payload.discharge_document_ref,
        owner_communication_ref=payload.owner_communication_ref, referrer_communication_ref=payload.referrer_communication_ref,
        final_estimate_ref=payload.final_estimate_ref, financial_status=payload.financial_status,
        outstanding_actions=payload.outstanding_actions, retained_risks=payload.retained_risks,
        prepared_by_subject=auth.subject,
    )
    session.add(row); session.flush()
    row.evidence_event_ref = record_evidence(session, entity_type="episode_closure", entity_ref=row.closure_ref, action="prepared", episode_ref=episode_ref, patient_ref=episode.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"closure": row_dict(row)}


@router.patch("/closures/{closure_ref}/approve")
def approve_closure(closure_ref: str, payload: VersionedReason, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*SENIOR_ROLES))) -> dict[str, Any]:
    query = select(EpisodeClosureV9).where(EpisodeClosureV9.closure_ref == closure_ref)
    if session.get_bind().dialect.name == "postgresql": query = query.with_for_update()
    row = session.exec(query).first()
    if not row: raise HTTPException(status_code=404, detail="closure not found")
    if row.version != payload.expected_version: raise HTTPException(status_code=409, detail={"message": "stale closure", "currentVersion": row.version})
    if row.status != "draft": raise HTTPException(status_code=409, detail="only a draft closure can be approved")
    failures: list[str] = []
    if row.outstanding_actions: failures.append("outstanding actions remain")
    if row.financial_status not in FINANCIAL_CLOSURE_STATES: failures.append("financial status is not closure-ready")
    if not row.discharge_document_ref: failures.append("discharge document reference missing")
    else:
        document = session.exec(select(ClinicalDocumentV8).where(ClinicalDocumentV8.document_ref == row.discharge_document_ref)).first()
        if not document or document.status != "sent": failures.append("discharge document is not sent")
    if not row.owner_communication_ref: failures.append("owner communication reference missing")
    else:
        communication = session.exec(select(CommunicationEventV8).where(CommunicationEventV8.communication_ref == row.owner_communication_ref)).first()
        if not communication or communication.audience != "owner" or communication.direction != "outbound": failures.append("owner communication evidence is invalid")
    if failures: raise HTTPException(status_code=409, detail={"message": "closure approval blocked", "failures": failures})
    previous = row_dict(row)
    row.status = "approved"; row.approved_by_subject = auth.subject; row.approved_at = utc_now(); row.version += 1; row.updated_at = utc_now()
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="episode_closure", entity_ref=closure_ref, action="approved", episode_ref=row.episode_ref, patient_ref=row.patient_ref, previous=previous, current=row_dict(row), reason=payload.reason, risk="amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"closure": row_dict(row)}


@router.get("/episodes/{episode_ref}/command-view")
def command_view(episode_ref: str, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    episode = require_episode(session, episode_ref)
    referral = session.exec(select(ReferralIntakeV9).where(ReferralIntakeV9.episode_ref == episode_ref)).first()
    consents = session.exec(select(ConsentAuthorisationV9).where(ConsentAuthorisationV9.episode_ref == episode_ref).order_by(ConsentAuthorisationV9.created_at.desc())).all()
    handovers = session.exec(select(EpisodeHandoverV9).where(EpisodeHandoverV9.episode_ref == episode_ref).order_by(EpisodeHandoverV9.created_at.desc())).all()
    checkpoints = session.exec(select(EpisodeCheckpointV9).where(EpisodeCheckpointV9.episode_ref == episode_ref).order_by(EpisodeCheckpointV9.created_at.desc())).all()
    transitions = session.exec(select(EpisodeTransitionV9).where(EpisodeTransitionV9.episode_ref == episode_ref).order_by(EpisodeTransitionV9.created_at.desc())).all()
    closure = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == episode_ref)).first()
    next_targets = sorted(ALLOWED_TRANSITIONS.get(episode.phase, set()))
    guards = {target: evaluate_guard(session, episode, target) for target in next_targets}
    return {
        "episode": row_dict(episode),
        "referral": row_dict(referral) if referral else None,
        "consents": [row_dict(row) for row in consents],
        "handovers": [row_dict(row) for row in handovers],
        "checkpoints": [row_dict(row) for row in checkpoints],
        "transitions": [row_dict(row) for row in transitions[:50]],
        "closure": row_dict(closure) if closure else None,
        "nextTransitions": guards,
        "requestedBy": auth.subject,
    }
