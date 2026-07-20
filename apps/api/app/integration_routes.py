from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated
from app.control_plane_models import CriticalResultAcknowledgement, ServiceAvailability
from app.database import get_session
from app.evidence_service import create_evidence_event, json_text, parse_json
from app.integration_adapters import IntegrationAction, adapter_for
from app.integration_models import IntegrationConnection, IntegrationEntityLink, IntegrationEnvelope

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def connection_dict(row: IntegrationConnection) -> dict[str, Any]:
    return {
        "id": row.id,
        "connectionRef": row.connection_ref,
        "integrationType": row.integration_type,
        "vendor": row.vendor,
        "direction": row.direction,
        "status": row.status,
        "premisesRef": row.premises_ref,
        "endpointUrl": row.endpoint_url,
        "secretEnv": row.secret_env,
        "mappingProfile": parse_json(row.mapping_profile_json),
        "storePayload": row.store_payload,
        "accountableOwner": row.accountable_owner,
        "createdBy": row.created_by,
        "lastReceivedAt": row.last_received_at.isoformat() if row.last_received_at else None,
        "lastProcessedAt": row.last_processed_at.isoformat() if row.last_processed_at else None,
        "lastError": row.last_error,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def envelope_dict(row: IntegrationEnvelope) -> dict[str, Any]:
    return {
        "id": row.id,
        "envelopeRef": row.envelope_ref,
        "connectionRef": row.connection_ref,
        "messageType": row.message_type,
        "externalEventId": row.external_event_id,
        "dedupeKey": row.dedupe_key,
        "payloadHash": row.payload_hash,
        "payloadStored": bool(row.payload_json),
        "status": row.status,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "internalRecordType": row.internal_record_type,
        "internalRecordRef": row.internal_record_ref,
        "evidenceEventRef": row.evidence_event_ref,
        "error": row.error,
        "receivedAt": row.received_at.isoformat() if row.received_at else None,
        "processedAt": row.processed_at.isoformat() if row.processed_at else None,
    }


class ConnectionCreate(BaseModel):
    connectionRef: str | None = None
    integrationType: str
    vendor: str
    direction: str = "inbound"
    status: str = "draft"
    premisesRef: str = "default-premises"
    endpointUrl: str | None = None
    secretEnv: str
    mappingProfile: dict[str, Any] = PydanticField(default_factory=dict)
    storePayload: bool = False
    accountableOwner: str


class ConnectionUpdate(BaseModel):
    status: str | None = None
    endpointUrl: str | None = None
    secretEnv: str | None = None
    mappingProfile: dict[str, Any] | None = None
    storePayload: bool | None = None
    accountableOwner: str | None = None


def _verify_webhook(request_body: bytes, timestamp: str | None, signature: str | None, secret: str) -> None:
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="integration timestamp and signature are required")
    try:
        sent_at = datetime.fromtimestamp(int(timestamp), timezone.utc)
    except (TypeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=401, detail="integration timestamp is invalid") from exc
    if abs((utc_now() - sent_at).total_seconds()) > 300:
        raise HTTPException(status_code=401, detail="integration signature timestamp is outside the five-minute window")
    signed = timestamp.encode("utf-8") + b"." + request_body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix("sha256=").strip().lower()
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="integration signature is invalid")


def _normalised_message(payload: dict[str, Any]) -> tuple[str, str | None, str | None, str | None]:
    message_type = str(payload.get("event_type") or payload.get("eventType") or payload.get("type") or "unknown")
    event_id = payload.get("event_id") or payload.get("eventId") or payload.get("id")
    patient_case_id = payload.get("patient_case_id") or payload.get("patientCaseId")
    referral_episode_id = payload.get("referral_episode_id") or payload.get("referralEpisodeId")
    return message_type, str(event_id) if event_id else None, str(patient_case_id) if patient_case_id else None, str(referral_episode_id) if referral_episode_id else None


def _apply_action(
    session: Session,
    connection: IntegrationConnection,
    envelope: IntegrationEnvelope,
    action: IntegrationAction,
    message_type: str,
) -> tuple[str | None, str | None, str]:
    internal_type: str | None = None
    internal_ref: str | None = None

    if action.action_type == "service_status":
        data = action.state
        service_ref = str(data.get("service_ref") or data.get("serviceRef") or f"{connection.connection_ref}:{data.get('service_name') or data.get('serviceName') or 'service'}")
        service = session.exec(select(ServiceAvailability).where(ServiceAvailability.service_ref == service_ref)).first()
        if not service:
            service = ServiceAvailability(
                service_ref=service_ref,
                premises_ref=connection.premises_ref,
                department=str(data.get("department") or connection.integration_type),
                service_name=str(data.get("service_name") or data.get("serviceName") or connection.vendor),
            )
        service.declared_capability = str(data.get("declared_capability") or data.get("declaredCapability") or "available")
        service.operational_status = str(data.get("operational_status") or data.get("status") or "available").lower()
        service.accepting_referrals = bool(data.get("accepting_referrals", data.get("acceptingReferrals", True)))
        service.staffing_ready = bool(data.get("staffing_ready", data.get("staffingReady", True)))
        service.equipment_ready = bool(data.get("equipment_ready", data.get("equipmentReady", True)))
        service.consumables_ready = bool(data.get("consumables_ready", data.get("consumablesReady", True)))
        service.limiting_reason = data.get("limiting_reason") or data.get("limitingReason")
        service.updated_by = f"integration:{connection.vendor}"
        service.updated_at = utc_now()
        session.add(service)
        session.flush()
        internal_type = "service_availability"
        internal_ref = service.service_ref

    elif action.action_type == "critical_result":
        data = action.state
        result_ref = str(data.get("result_ref") or data.get("resultRef") or envelope.external_event_id or envelope.envelope_ref)
        existing = session.exec(select(CriticalResultAcknowledgement).where(CriticalResultAcknowledgement.result_ref == result_ref)).first()
        if not existing:
            result = CriticalResultAcknowledgement(
                result_ref=result_ref,
                patient_case_id=action.patient_case_id,
                referral_episode_id=action.referral_episode_id or f"external:{connection.connection_ref}:{result_ref}",
                result_type=str(data.get("result_type") or data.get("resultType") or message_type),
                severity=str(data.get("severity") or "red"),
                summary=str(data.get("summary") or data.get("interpretation") or action.action),
                status="awaiting_acknowledgement",
                assigned_to=str(data.get("assigned_to") or data.get("assignedTo") or "clinical duty owner"),
                assigned_role=str(data.get("assigned_role") or data.get("assignedRole") or "clinician"),
            )
            session.add(result)
            session.flush()
            internal_type = "critical_result"
            internal_ref = result.result_ref
        else:
            internal_type = "critical_result"
            internal_ref = existing.result_ref

    evidence, _ = create_evidence_event(
        session,
        event_type=f"integration_{connection.integration_type}_{message_type.replace('.', '_')}",
        action=action.action,
        patient_case_id=action.patient_case_id,
        referral_episode_id=action.referral_episode_id,
        actor_id=connection.connection_ref,
        actor_name=f"{connection.vendor} integration",
        actor_role="system_integration",
        actor_auth_source="hmac_verified_integration",
        previous_state=None,
        new_state=action.state,
        reason=f"verified {connection.integration_type} message received",
        evidence_links=[
            {"type": "integration_connection", "id": connection.connection_ref},
            {"type": "integration_envelope", "id": envelope.envelope_ref, "payloadHash": envelope.payload_hash},
        ],
        compliance_domain=action.compliance_domain,
        risk_level=action.risk_level,
        source_module="integration-gateway",
        source_system=connection.vendor,
        source_record_ref=envelope.external_event_id or envelope.envelope_ref,
        correlation_id=action.referral_episode_id or action.patient_case_id or envelope.envelope_ref,
        entity_type=internal_type or "external_event",
        entity_id=internal_ref or envelope.external_event_id or envelope.envelope_ref,
        idempotency_key=f"integration-event:{envelope.dedupe_key}:{action.action_type}",
    )
    return internal_type, internal_ref, evidence.event_ref


def _upsert_entity_link(session: Session, connection_ref: str, payload: dict[str, Any]) -> None:
    entity = payload.get("entity") or payload.get("external_entity") or payload.get("externalEntity")
    if not isinstance(entity, dict):
        return
    external_type = entity.get("type") or entity.get("external_type")
    external_id = entity.get("id") or entity.get("external_id")
    internal_type = entity.get("internal_type") or entity.get("internalType")
    internal_id = entity.get("internal_id") or entity.get("internalId")
    if not all([external_type, external_id, internal_type, internal_id]):
        return
    row = session.exec(
        select(IntegrationEntityLink)
        .where(IntegrationEntityLink.connection_ref == connection_ref)
        .where(IntegrationEntityLink.external_entity_type == str(external_type))
        .where(IntegrationEntityLink.external_entity_id == str(external_id))
    ).first()
    if not row:
        row = IntegrationEntityLink(
            connection_ref=connection_ref,
            external_entity_type=str(external_type),
            external_entity_id=str(external_id),
            internal_entity_type=str(internal_type),
            internal_entity_id=str(internal_id),
        )
    else:
        row.internal_entity_type = str(internal_type)
        row.internal_entity_id = str(internal_id)
        row.last_seen_at = utc_now()
    session.add(row)


@router.post("/connections")
def create_connection(
    payload: ConnectionCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    try:
        adapter_for(payload.integrationType)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connection_ref = payload.connectionRef or new_ref("integration")
    if session.exec(select(IntegrationConnection).where(IntegrationConnection.connection_ref == connection_ref)).first():
        raise HTTPException(status_code=409, detail="connection_ref already exists")
    row = IntegrationConnection(
        connection_ref=connection_ref,
        integration_type=payload.integrationType.lower().strip(),
        vendor=payload.vendor,
        direction=payload.direction,
        status=payload.status,
        premises_ref=payload.premisesRef,
        endpoint_url=payload.endpointUrl,
        secret_env=payload.secretEnv,
        mapping_profile_json=json_text(payload.mappingProfile),
        store_payload=payload.storePayload,
        accountable_owner=payload.accountableOwner,
        created_by=auth.actor_name,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"connection": connection_dict(row)}


@router.patch("/connections/{connection_id}")
def update_connection(connection_id: int, payload: ConnectionUpdate, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(IntegrationConnection, connection_id)
    if not row:
        raise HTTPException(status_code=404, detail="integration connection not found")
    if payload.status is not None:
        row.status = payload.status
    if payload.endpointUrl is not None:
        row.endpoint_url = payload.endpointUrl
    if payload.secretEnv is not None:
        row.secret_env = payload.secretEnv
    if payload.mappingProfile is not None:
        row.mapping_profile_json = json_text(payload.mappingProfile)
    if payload.storePayload is not None:
        row.store_payload = payload.storePayload
    if payload.accountableOwner is not None:
        row.accountable_owner = payload.accountableOwner
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"connection": connection_dict(row)}


@router.get("/connections")
def list_connections(session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = session.exec(select(IntegrationConnection).order_by(IntegrationConnection.integration_type, IntegrationConnection.vendor)).all()
    return {"connections": [connection_dict(row) for row in rows], "count": len(rows)}


@router.get("/envelopes")
def list_envelopes(connection_ref: str | None = None, status: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    query = select(IntegrationEnvelope).order_by(IntegrationEnvelope.received_at.desc())
    if connection_ref:
        query = query.where(IntegrationEnvelope.connection_ref == connection_ref)
    if status:
        query = query.where(IntegrationEnvelope.status == status)
    rows = session.exec(query.limit(500)).all()
    return {"envelopes": [envelope_dict(row) for row in rows], "count": len(rows)}


@router.post("/webhooks/{connection_ref}")
async def receive_webhook(connection_ref: str, request: Request, session: Session = Depends(get_session)) -> dict[str, Any]:
    connection = session.exec(select(IntegrationConnection).where(IntegrationConnection.connection_ref == connection_ref)).first()
    if not connection or connection.status != "active":
        raise HTTPException(status_code=404, detail="active integration connection not found")
    secret = os.getenv(connection.secret_env, "")
    if not secret:
        raise HTTPException(status_code=503, detail="integration signing secret is not configured")

    raw = await request.body()
    _verify_webhook(raw, request.headers.get("x-lucyworks-timestamp"), request.headers.get("x-lucyworks-signature"), secret)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="integration payload must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="integration payload must be a JSON object")

    message_type, external_event_id, patient_case_id, referral_episode_id = _normalised_message(payload)
    payload_hash = hashlib.sha256(raw).hexdigest()
    dedupe_key = f"{connection_ref}:{external_event_id or payload_hash}"
    existing = session.exec(select(IntegrationEnvelope).where(IntegrationEnvelope.dedupe_key == dedupe_key)).first()
    if existing:
        return {"envelope": envelope_dict(existing), "created": False}

    envelope = IntegrationEnvelope(
        envelope_ref=new_ref("envelope"),
        connection_ref=connection_ref,
        message_type=message_type,
        external_event_id=external_event_id,
        dedupe_key=dedupe_key,
        payload_hash=payload_hash,
        payload_json=json_text(payload) if connection.store_payload else None,
        patient_case_id=patient_case_id,
        referral_episode_id=referral_episode_id,
    )
    session.add(envelope)
    session.flush()

    try:
        actions = adapter_for(connection.integration_type).normalise(message_type, payload)
        evidence_refs: list[str] = []
        for action in actions:
            internal_type, internal_ref, evidence_ref = _apply_action(session, connection, envelope, action, message_type)
            envelope.internal_record_type = internal_type or envelope.internal_record_type
            envelope.internal_record_ref = internal_ref or envelope.internal_record_ref
            evidence_refs.append(evidence_ref)
        envelope.evidence_event_ref = evidence_refs[0] if evidence_refs else None
        envelope.status = "processed"
        envelope.processed_at = utc_now()
        connection.last_processed_at = envelope.processed_at
        connection.last_error = None
        _upsert_entity_link(session, connection_ref, payload)
    except Exception as exc:
        envelope.status = "failed"
        envelope.error = str(exc)[:1000]
        connection.last_error = envelope.error
        session.add(envelope)
        session.add(connection)
        session.commit()
        raise HTTPException(status_code=422, detail=f"integration message could not be processed: {envelope.error}") from exc

    connection.last_received_at = envelope.received_at
    connection.updated_at = utc_now()
    session.add(envelope)
    session.add(connection)
    session.commit()
    session.refresh(envelope)
    return {"envelope": envelope_dict(envelope), "created": True}


@router.get("/dashboard")
def integration_dashboard(session: Session = Depends(get_session)) -> dict[str, Any]:
    connections = session.exec(select(IntegrationConnection).order_by(IntegrationConnection.integration_type, IntegrationConnection.vendor)).all()
    envelopes = session.exec(select(IntegrationEnvelope).order_by(IntegrationEnvelope.received_at.desc()).limit(100)).all()
    return {
        "summary": {
            "connections": len(connections),
            "activeConnections": len([row for row in connections if row.status == "active"]),
            "failedConnections": len([row for row in connections if row.last_error]),
            "processedMessages": len([row for row in envelopes if row.status == "processed"]),
            "failedMessages": len([row for row in envelopes if row.status == "failed"]),
        },
        "connections": [connection_dict(row) for row in connections],
        "recentEnvelopes": [envelope_dict(row) for row in envelopes[:30]],
    }
