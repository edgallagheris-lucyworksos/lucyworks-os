from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, require_roles
from app.database import get_session
from app.detailed_hospital_models import CommunicationEventV8, PatientOwnerLinkV8
from app.evidence_service import create_evidence_event
from app.hospital_command_models import ConsentAuthorisationV9
from app.regulated_workflow_v32_routes import EstimateLineInput, RegulatedEstimateCreate, create_regulated_estimate

router = APIRouter(prefix="/api/v32", tags=["regulated-workflow-v32"])
FINANCIAL_ROLES = ("admin", "ops_manager", "hospital_director", "governance_lead")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class DeliverAndIssueEstimate(BaseModel):
    patientRef: str
    ownerRef: str | None = None
    channel: str = "email"
    lines: list[EstimateLineInput]
    authorisedLimitPence: int | None = None
    ownerAcknowledged: bool = False
    reasonForChange: str | None = None
    deliverySummary: str = "Written estimate supplied to the client."
    reason: str = "Estimate delivered and issued"


def active_authority(session: Session, episode_ref: str, patient_ref: str, owner_ref: str | None) -> tuple[str, str]:
    now = utc_now()
    consent_query = select(ConsentAuthorisationV9).where(
        ConsentAuthorisationV9.episode_ref == episode_ref,
        ConsentAuthorisationV9.patient_ref == patient_ref,
        ConsentAuthorisationV9.status == "active",
    ).order_by(ConsentAuthorisationV9.created_at.desc())
    consents = session.exec(consent_query).all()
    for consent in consents:
        if owner_ref and consent.owner_ref != owner_ref:
            continue
        if consent.valid_until and consent.valid_until < now:
            continue
        return consent.owner_ref, consent.evidence_event_ref or consent.consent_ref

    link_query = select(PatientOwnerLinkV8).where(
        PatientOwnerLinkV8.patient_ref == patient_ref,
        PatientOwnerLinkV8.active == True,  # noqa: E712
        PatientOwnerLinkV8.decision_authority == True,  # noqa: E712
    )
    links = session.exec(link_query).all()
    for link in links:
        if owner_ref and link.owner_ref != owner_ref:
            continue
        return link.owner_ref, link.evidence_event_ref or link.link_ref

    raise HTTPException(status_code=409, detail="no active owner decision-authority record is available for this patient")


@router.post("/episodes/{episode_ref}/estimates/deliver-and-issue")
def deliver_and_issue_estimate(
    episode_ref: str,
    payload: DeliverAndIssueEstimate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*FINANCIAL_ROLES)),
) -> dict[str, Any]:
    if not payload.lines:
        raise HTTPException(status_code=422, detail="estimate requires at least one line")
    if payload.channel not in {"email", "sms", "portal", "printed", "in_person"}:
        raise HTTPException(status_code=422, detail="unsupported estimate delivery channel")

    owner_ref, authority_ref = active_authority(session, episode_ref, payload.patientRef, payload.ownerRef)

    active_consent = session.exec(
        select(ConsentAuthorisationV9)
        .where(
            ConsentAuthorisationV9.episode_ref == episode_ref,
            ConsentAuthorisationV9.owner_ref == owner_ref,
            ConsentAuthorisationV9.status == "active",
        )
        .order_by(ConsentAuthorisationV9.created_at.desc())
    ).first()
    if (
        payload.authorisedLimitPence is not None
        and active_consent
        and active_consent.maximum_authorised_pence is not None
        and payload.authorisedLimitPence > active_consent.maximum_authorised_pence
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "requested estimate authority exceeds the active client financial limit",
                "activeLimitPence": active_consent.maximum_authorised_pence,
            },
        )

    communication = CommunicationEventV8(
        communication_ref=new_ref("communication"),
        patient_ref=payload.patientRef,
        episode_ref=episode_ref,
        owner_ref=owner_ref,
        audience="owner",
        channel=payload.channel,
        direction="outbound",
        subject="Written treatment estimate",
        summary=payload.deliverySummary.strip() or "Written estimate supplied to the client.",
        outcome="acknowledged" if payload.ownerAcknowledged else "delivered",
        consent_or_authorisation={
            "estimateDelivery": True,
            "ownerAcknowledged": payload.ownerAcknowledged,
            "decisionAuthorityRef": authority_ref,
        },
        actor_subject=auth.subject,
    )
    session.add(communication)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="v32_estimate_written_delivery",
        action="deliver_written_estimate",
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        patient_case_id=payload.patientRef,
        referral_episode_id=episode_ref,
        previous_state=None,
        new_state={
            "communicationRef": communication.communication_ref,
            "channel": communication.channel,
            "ownerRef": owner_ref,
            "ownerAcknowledged": payload.ownerAcknowledged,
            "decisionAuthorityRef": authority_ref,
        },
        reason=payload.reason,
        justification="Written estimate delivery and owner-authority evidence",
        evidence_links=[{"type": "communication", "id": communication.communication_ref}],
        compliance_domain="financial_consent",
        risk_level="green",
        source_module="regulated-workflow-v32",
        source_record_ref=communication.communication_ref,
        correlation_id=episode_ref,
        entity_type="communication",
        entity_id=communication.communication_ref,
        idempotency_key=f"v32:estimate-delivery:{communication.communication_ref}",
    )
    communication.evidence_event_ref = event.event_ref
    session.add(communication)
    session.flush()

    estimate_payload = RegulatedEstimateCreate(
        patientRef=payload.patientRef,
        lines=payload.lines,
        status="issued",
        authorisedLimitPence=payload.authorisedLimitPence,
        ownerAuthorisationRef=authority_ref,
        reasonForChange=payload.reasonForChange,
        writtenDeliveryRef=event.event_ref,
        ownerAcknowledgementRef=event.event_ref if payload.ownerAcknowledged else None,
        reason=payload.reason,
    )
    result = create_regulated_estimate(episode_ref, estimate_payload, session, auth)
    result["delivery"] = {
        "communicationRef": communication.communication_ref,
        "evidenceEventRef": event.event_ref,
        "channel": communication.channel,
        "ownerRef": owner_ref,
        "ownerAcknowledged": payload.ownerAcknowledged,
    }
    return result
