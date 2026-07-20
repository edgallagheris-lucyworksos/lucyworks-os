from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlmodel import Session, select

from app.auth import get_current_auth_context
from app.evidence_approval_models import ApprovalTask
from app.evidence_event_models import EvidenceEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def parse_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def new_event_ref(prefix: str = "evidence") -> str:
    return f"{prefix}-{uuid4().hex}"


def _datetime_text(value: datetime | None) -> str | None:
    """Canonical UTC timestamp stable across SQLite/PostgreSQL round-trips."""

    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return f"{value.isoformat(timespec='microseconds')}Z"


def _normalise_risk(value: str | None) -> str:
    risk = str(value or "amber").lower().strip()
    return risk if risk in {"green", "amber", "red"} else "amber"


def _review_complete(status: str | None) -> bool:
    return str(status or "").lower() in {"accepted", "approved", "edited", "rejected"}


def approval_reason_for(event: EvidenceEvent) -> str | None:
    if event.supervisor_required:
        return "supervisor approval explicitly required"
    if event.supervisor_approval_status in {"required", "pending"}:
        return "supervisor approval status requires review"
    if event.risk_level == "red":
        return "red-risk evidence event"
    if event.override_reason:
        return "override requires named approval"
    if event.ai_system and not _review_complete(event.human_review_status):
        return "AI-linked evidence lacks completed human review"
    return None


def required_approval_role(event: EvidenceEvent) -> str:
    if event.ai_system or event.compliance_domain in {"clinical_governance", "consent", "medication", "diagnostics"}:
        return "clinical_director_or_senior_clinician"
    if event.compliance_domain in {"workforce", "operations", "service_availability", "premises"}:
        return "ops_manager_or_hospital_director"
    return "clinical_director_or_ops_manager"


def event_hash_payload(event: EvidenceEvent) -> dict[str, Any]:
    """Return only immutable, persisted fields used in the event hash."""

    return {
        "eventRef": event.event_ref,
        "eventType": event.event_type,
        "correlationId": event.correlation_id,
        "causationEventRef": event.causation_event_ref,
        "idempotencyKey": event.idempotency_key,
        "requestId": event.request_id,
        "entityType": event.entity_type,
        "entityId": event.entity_id,
        "patientCaseId": event.patient_case_id,
        "referralEpisodeId": event.referral_episode_id,
        "scheduleBlockId": event.schedule_block_id,
        "actorId": event.actor_id,
        "actorName": event.actor_name,
        "actorRole": event.actor_role,
        "actorAuthSource": event.actor_auth_source,
        "professionalRole": event.professional_role,
        "action": event.action,
        "previousState": parse_json(event.previous_state_json),
        "newState": parse_json(event.new_state_json),
        "reason": event.reason,
        "justification": event.justification,
        "evidenceLinks": parse_json(event.evidence_links_json),
        "alternativesDiscussed": parse_json(event.alternatives_discussed_json),
        "clientAuthorisation": parse_json(event.client_authorisation_json),
        "aiSystem": event.ai_system,
        "aiModel": event.ai_model,
        "aiPromptRef": event.ai_prompt_ref,
        "aiOutputRef": event.ai_output_ref,
        "aiConfidence": event.ai_confidence,
        "humanReviewer": event.human_reviewer,
        "humanReviewStatus": event.human_review_status,
        "humanReviewCompletedAt": _datetime_text(event.human_review_completed_at),
        "supervisorRequired": event.supervisor_required,
        "supervisorName": event.supervisor_name,
        "supervisorApprovalStatus": event.supervisor_approval_status,
        "overrideReason": event.override_reason,
        "complianceDomain": event.compliance_domain,
        "riskLevel": event.risk_level,
        "sourceModule": event.source_module,
        "sourceSystem": event.source_system,
        "sourceRecordRef": event.source_record_ref,
        "payloadSchemaVersion": event.payload_schema_version,
        "occurredAt": _datetime_text(event.occurred_at),
        "createdAt": _datetime_text(event.created_at),
    }


def calculate_event_hash(event: EvidenceEvent, previous_hash: str | None = None) -> str:
    material = f"{previous_hash or ''}|{canonical_json(event_hash_payload(event))}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _validate_event(event: EvidenceEvent) -> None:
    if not event.event_type.strip():
        raise ValueError("event_type is required")
    if not event.action.strip():
        raise ValueError("action is required")
    if event.override_reason and not (event.reason or event.justification):
        raise ValueError("override events require a reason or justification")
    if event.ai_system and event.human_review_status == "not_required":
        raise ValueError("AI-linked evidence must record a required, pending, accepted, edited or rejected human review state")
    if event.risk_level == "red":
        event.supervisor_required = True
        if event.supervisor_approval_status == "not_required":
            event.supervisor_approval_status = "pending"


def create_evidence_event(
    session: Session,
    *,
    event_type: str,
    action: str,
    patient_case_id: str | None = None,
    referral_episode_id: str | None = None,
    schedule_block_id: str | None = None,
    actor_id: str | None = None,
    actor_name: str = "system",
    actor_role: str = "system",
    actor_auth_source: str = "unverified",
    professional_role: str | None = None,
    previous_state: Any = None,
    new_state: Any = None,
    reason: str | None = None,
    justification: str | None = None,
    evidence_links: Any = None,
    alternatives_discussed: Any = None,
    client_authorisation: Any = None,
    ai_system: str | None = None,
    ai_model: str | None = None,
    ai_prompt_ref: str | None = None,
    ai_output_ref: str | None = None,
    ai_confidence: str | None = None,
    human_reviewer: str | None = None,
    human_review_status: str = "not_required",
    supervisor_required: bool = False,
    supervisor_name: str | None = None,
    supervisor_approval_status: str = "not_required",
    override_reason: str | None = None,
    compliance_domain: str = "operations",
    risk_level: str = "amber",
    source_module: str = "lucyworks",
    source_system: str = "lucyworks-os",
    source_record_ref: str | None = None,
    correlation_id: str | None = None,
    causation_event_ref: str | None = None,
    idempotency_key: str | None = None,
    request_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    occurred_at: datetime | None = None,
) -> tuple[EvidenceEvent, bool]:
    if idempotency_key:
        existing = session.exec(select(EvidenceEvent).where(EvidenceEvent.idempotency_key == idempotency_key)).first()
        if existing:
            return existing, False

    auth = get_current_auth_context()
    if auth.verified:
        actor_id = auth.actor_id
        actor_name = auth.actor_name
        actor_role = auth.role
        actor_auth_source = auth.auth_source
        professional_role = professional_role or auth.role
        if _review_complete(human_review_status) and not human_reviewer:
            human_reviewer = auth.actor_name
        if supervisor_approval_status in {"approved", "rejected"} and not supervisor_name:
            supervisor_name = auth.actor_name

    created_at = utc_now()
    event = EvidenceEvent(
        event_ref=new_event_ref(),
        event_type=event_type.strip(),
        correlation_id=correlation_id or referral_episode_id or patient_case_id,
        causation_event_ref=causation_event_ref,
        idempotency_key=idempotency_key,
        request_id=request_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        patient_case_id=patient_case_id,
        referral_episode_id=referral_episode_id,
        schedule_block_id=schedule_block_id,
        actor_id=actor_id,
        actor_name=actor_name or "system",
        actor_role=actor_role or "system",
        actor_auth_source=actor_auth_source or "unverified",
        professional_role=professional_role,
        action=action.strip(),
        previous_state_json=json_text(previous_state),
        new_state_json=json_text(new_state),
        reason=reason,
        justification=justification,
        evidence_links_json=json_text(evidence_links),
        alternatives_discussed_json=json_text(alternatives_discussed),
        client_authorisation_json=json_text(client_authorisation),
        ai_system=ai_system,
        ai_model=ai_model,
        ai_prompt_ref=ai_prompt_ref,
        ai_output_ref=ai_output_ref,
        ai_confidence=ai_confidence,
        human_reviewer=human_reviewer,
        human_review_status=human_review_status or "not_required",
        human_review_completed_at=created_at if _review_complete(human_review_status) else None,
        supervisor_required=supervisor_required,
        supervisor_name=supervisor_name,
        supervisor_approval_status=supervisor_approval_status or "not_required",
        override_reason=override_reason,
        compliance_domain=compliance_domain or "operations",
        risk_level=_normalise_risk(risk_level),
        source_module=source_module or "lucyworks",
        source_system=source_system or "lucyworks-os",
        source_record_ref=source_record_ref,
        payload_schema_version=2,
        immutable=True,
        occurred_at=occurred_at or created_at,
        created_at=created_at,
    )
    _validate_event(event)

    previous = session.exec(select(EvidenceEvent).order_by(EvidenceEvent.id.desc())).first()
    previous_hash = previous.event_hash if previous and previous.event_hash else None
    event.previous_event_hash = previous_hash
    event.event_hash = calculate_event_hash(event, previous_hash)
    session.add(event)
    session.flush()

    approval_reason = approval_reason_for(event)
    if approval_reason:
        task = ApprovalTask(
            evidence_event_ref=event.event_ref,
            patient_case_id=event.patient_case_id,
            referral_episode_id=event.referral_episode_id,
            status="pending",
            required_role=required_approval_role(event),
            reason=approval_reason,
            risk_level=event.risk_level,
            source_module=event.source_module,
            requested_by=event.actor_name,
        )
        session.add(task)

    return event, True


def verify_event_chain(session: Session) -> dict[str, Any]:
    rows = session.exec(select(EvidenceEvent).order_by(EvidenceEvent.id)).all()
    previous_hash: str | None = None
    checked = 0
    legacy_unhashed = 0
    failures: list[dict[str, Any]] = []

    for row in rows:
        if not row.event_hash:
            legacy_unhashed += 1
            continue
        checked += 1
        if row.previous_event_hash != previous_hash:
            failures.append({
                "eventRef": row.event_ref,
                "type": "previous_hash_mismatch",
                "expected": previous_hash,
                "actual": row.previous_event_hash,
            })
        recalculated = calculate_event_hash(row, row.previous_event_hash)
        if recalculated != row.event_hash:
            failures.append({
                "eventRef": row.event_ref,
                "type": "event_hash_mismatch",
                "expected": recalculated,
                "actual": row.event_hash,
            })
        previous_hash = row.event_hash

    return {
        "ok": not failures,
        "checked": checked,
        "legacyUnhashed": legacy_unhashed,
        "failures": failures,
        "headHash": previous_hash,
    }
