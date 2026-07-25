from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.auth import get_current_auth_context
from app.v7_models import DurableEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def event_dict(row: DurableEvent) -> dict[str, Any]:
    return {
        "eventRef": row.event_ref,
        "sequence": row.sequence,
        "eventType": row.event_type,
        "aggregateType": row.aggregate_type,
        "aggregateRef": row.aggregate_ref,
        "premisesRef": row.premises_ref,
        "payload": row.payload,
        "severity": row.severity,
        "actorSubject": row.actor_subject,
        "actorName": row.actor_name,
        "actorRole": row.actor_role,
        "correlationId": row.correlation_id,
        "causationRef": row.causation_ref,
        "createdAt": row.created_at.isoformat(),
    }


def _lock_sequence_allocator(session: Session) -> None:
    """Serialise sequence allocation for the current database transaction.

    PostgreSQL advisory transaction locks work across every API process and are
    released automatically on commit/rollback. SQLite serialises writers at the
    database layer and is used only for local development and tests.
    """

    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.exec(text("SELECT pg_advisory_xact_lock(73478101)"))


def publish_event(
    session: Session,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_ref: str,
    payload: dict[str, Any],
    premises_ref: str = "default-premises",
    severity: str = "info",
    correlation_id: str | None = None,
    causation_ref: str | None = None,
    idempotency_key: str | None = None,
) -> DurableEvent:
    if idempotency_key:
        existing = session.exec(select(DurableEvent).where(DurableEvent.idempotency_key == idempotency_key)).first()
        if existing:
            return existing
    _lock_sequence_allocator(session)
    # Check idempotency again after acquiring the allocator lock, since another
    # transaction may have committed the same event while this one was waiting.
    if idempotency_key:
        existing = session.exec(select(DurableEvent).where(DurableEvent.idempotency_key == idempotency_key)).first()
        if existing:
            return existing
    current = session.exec(select(func.max(DurableEvent.sequence))).one()
    sequence = int(current or 0) + 1
    auth = get_current_auth_context()
    row = DurableEvent(
        event_ref=f"event-{uuid4().hex}",
        sequence=sequence,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_ref=aggregate_ref,
        premises_ref=premises_ref,
        payload=payload,
        severity=severity,
        actor_subject=auth.subject if auth.verified else "system",
        actor_name=auth.actor_name if auth.verified else "system",
        actor_role=auth.role if auth.verified else "system",
        correlation_id=correlation_id,
        causation_ref=causation_ref,
        idempotency_key=idempotency_key,
    )
    session.add(row)
    session.flush()
    return row
