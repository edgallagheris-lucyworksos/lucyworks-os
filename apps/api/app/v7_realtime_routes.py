from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, SENIOR_ROLES, require_authenticated
from app.database import engine, get_session
from app.evidence_service import create_evidence_event
from app.v7_event_service import event_dict, publish_event
from app.v7_models import DurableEvent, EventAcknowledgement

router = APIRouter(prefix="/api/v7/events", tags=["durable-realtime"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def acknowledgement_dict(row: EventAcknowledgement | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "eventRef": row.event_ref,
        "status": row.status,
        "assignedRole": row.assigned_role,
        "assignedSubject": row.assigned_subject,
        "acknowledgedBySubject": row.acknowledged_by_subject,
        "acknowledgedByName": row.acknowledged_by_name,
        "note": row.note,
        "version": row.version,
        "acknowledgedAt": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
    }


class PublishPayload(BaseModel):
    event_type: str
    aggregate_type: str
    aggregate_ref: str
    payload: dict[str, Any] = Field(default_factory=dict)
    premises_ref: str = "default-premises"
    severity: str = "info"
    correlation_id: str | None = None
    causation_ref: str | None = None
    idempotency_key: str | None = None


class AcknowledgementPayload(BaseModel):
    expected_version: int = 0
    status: str
    note: str
    assigned_role: str | None = None
    assigned_subject: str | None = None


@router.get("")
def list_events(
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(DurableEvent).where(DurableEvent.sequence > after_sequence).order_by(DurableEvent.sequence).limit(limit)).all()
    refs = [row.event_ref for row in rows]
    acknowledgements = session.exec(select(EventAcknowledgement).where(EventAcknowledgement.event_ref.in_(refs))).all() if refs else []
    ack_by_ref = {row.event_ref: row for row in acknowledgements}
    return {
        "events": [{**event_dict(row), "acknowledgement": acknowledgement_dict(ack_by_ref.get(row.event_ref))} for row in rows],
        "nextSequence": rows[-1].sequence if rows else after_sequence,
        "hasMore": len(rows) == limit,
    }


@router.post("")
def publish(payload: PublishPayload, session: Session = Depends(get_session), _: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    row = publish_event(
        session,
        event_type=payload.event_type,
        aggregate_type=payload.aggregate_type,
        aggregate_ref=payload.aggregate_ref,
        payload=payload.payload,
        premises_ref=payload.premises_ref,
        severity=payload.severity,
        correlation_id=payload.correlation_id,
        causation_ref=payload.causation_ref,
        idempotency_key=payload.idempotency_key,
    )
    session.commit()
    session.refresh(row)
    return {"event": event_dict(row)}


@router.patch("/{event_ref}/acknowledgement")
def acknowledge_event(
    event_ref: str,
    payload: AcknowledgementPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    event = session.exec(select(DurableEvent).where(DurableEvent.event_ref == event_ref)).first()
    if not event:
        raise HTTPException(status_code=404, detail="durable event not found")
    row = session.exec(select(EventAcknowledgement).where(EventAcknowledgement.event_ref == event_ref)).first()
    current_version = row.version if row else 0
    if current_version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale acknowledgement", "current": acknowledgement_dict(row)})
    status = payload.status.lower().strip()
    if status not in {"acknowledged", "escalated", "resolved"}:
        raise HTTPException(status_code=400, detail="unsupported acknowledgement status")
    if status == "resolved" and auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior authority required to resolve an event")
    previous = acknowledgement_dict(row)
    if not row:
        row = EventAcknowledgement(event_ref=event_ref)
    row.status = status
    row.assigned_role = payload.assigned_role
    row.assigned_subject = payload.assigned_subject
    row.acknowledged_by_subject = auth.subject
    row.acknowledged_by_name = auth.actor_name
    row.note = payload.note
    row.acknowledged_at = row.acknowledged_at or utc_now()
    row.resolved_at = utc_now() if status == "resolved" else None
    row.version = current_version + 1
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    current = acknowledgement_dict(row)
    evidence, _ = create_evidence_event(
        session,
        event_type="durable_event_acknowledgement",
        action=status,
        previous_state=previous,
        new_state=current,
        reason=payload.note,
        compliance_domain="hospital_operations",
        risk_level="red" if event.severity in {"red", "error", "critical"} else "amber",
        source_module="durable-realtime-v7",
        source_record_ref=event_ref,
        correlation_id=event.correlation_id or event.aggregate_ref,
        causation_event_ref=event_ref,
        entity_type="event_acknowledgement",
        entity_id=event_ref,
        idempotency_key=f"event-ack:{event_ref}:v{row.version}",
    )
    publish_event(
        session,
        event_type="event_acknowledgement_changed",
        aggregate_type="durable_event",
        aggregate_ref=event_ref,
        premises_ref=event.premises_ref,
        payload={"acknowledgement": current, "evidenceEventRef": evidence.event_ref},
        severity="warning" if status == "escalated" else "info",
        correlation_id=event.correlation_id,
        causation_ref=event_ref,
        idempotency_key=f"event-ack-change:{event_ref}:v{row.version}",
    )
    session.commit()
    return {"acknowledgement": current, "evidenceEventRef": evidence.event_ref}


async def stream_events(request: Request, after_sequence: int):
    cursor = max(0, after_sequence)
    last_keepalive = utc_now()
    while True:
        if await request.is_disconnected():
            return
        with Session(engine) as session:
            rows = session.exec(select(DurableEvent).where(DurableEvent.sequence > cursor).order_by(DurableEvent.sequence).limit(250)).all()
        if rows:
            for row in rows:
                cursor = row.sequence
                yield f"id: {row.sequence}\n"
                yield f"event: {row.event_type}\n"
                yield f"data: {json.dumps(event_dict(row), default=str)}\n\n"
            last_keepalive = utc_now()
            continue
        if (utc_now() - last_keepalive).total_seconds() >= 15:
            yield f"event: keepalive\ndata: {json.dumps({'sequence': cursor, 'createdAt': utc_now().isoformat()})}\n\n"
            last_keepalive = utc_now()
        await asyncio.sleep(1)


@router.get("/stream")
def stream(request: Request, after_sequence: int = Query(default=0, ge=0), _: AuthContext = Depends(require_authenticated)) -> StreamingResponse:
    return StreamingResponse(stream_events(request, after_sequence), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
