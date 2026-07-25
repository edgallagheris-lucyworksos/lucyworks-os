from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth import AuthContext, SENIOR_ROLES, require_authenticated
from app.database import get_session
from app.evidence_service import create_evidence_event, parse_json
from app.integration_adapters import adapter_for
from app.integration_models import IntegrationConnection, IntegrationEnvelope
from app.integration_routes import _apply_action, _upsert_entity_link
from app.v7_event_service import publish_event
from app.v7_models import IntegrationRetryJob

router = APIRouter(prefix="/api/v7/integration-retries", tags=["integration-reliability"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def job_dict(row: IntegrationRetryJob) -> dict[str, Any]:
    return {
        "jobRef": row.job_ref,
        "envelopeRef": row.envelope_ref,
        "connectionRef": row.connection_ref,
        "status": row.status,
        "attemptCount": row.attempt_count,
        "maximumAttempts": row.maximum_attempts,
        "nextAttemptAt": row.next_attempt_at.isoformat(),
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "deadLetteredAt": row.dead_lettered_at.isoformat() if row.dead_lettered_at else None,
        "acknowledgementStatus": row.acknowledgement_status,
        "lastError": row.last_error,
        "version": row.version,
    }


def ensure_job(session: Session, envelope: IntegrationEnvelope) -> IntegrationRetryJob:
    existing = session.exec(select(IntegrationRetryJob).where(IntegrationRetryJob.envelope_ref == envelope.envelope_ref)).first()
    if existing:
        return existing
    row = IntegrationRetryJob(
        job_ref=f"retry-{uuid4().hex}",
        envelope_ref=envelope.envelope_ref,
        connection_ref=envelope.connection_ref,
        status="queued" if envelope.payload_json else "dead_letter",
        next_attempt_at=utc_now(),
        dead_lettered_at=None if envelope.payload_json else utc_now(),
        last_error=envelope.error if envelope.payload_json else "payload not retained; source system must resend",
    )
    session.add(row)
    session.flush()
    return row


def process_job(session: Session, job: IntegrationRetryJob) -> None:
    now = utc_now()
    envelope = session.exec(select(IntegrationEnvelope).where(IntegrationEnvelope.envelope_ref == job.envelope_ref)).first()
    connection = session.exec(select(IntegrationConnection).where(IntegrationConnection.connection_ref == job.connection_ref)).first()
    if not envelope or not connection:
        raise RuntimeError("integration envelope or connection no longer exists")
    payload = parse_json(envelope.payload_json)
    if not isinstance(payload, dict):
        raise RuntimeError("retained integration payload is unavailable")
    job.status = "processing"
    job.locked_at = now
    job.attempt_count += 1
    job.version += 1
    session.add(job)
    session.flush()
    try:
        actions = adapter_for(connection.integration_type).normalise(envelope.message_type, payload)
        evidence_refs: list[str] = []
        for action in actions:
            internal_type, internal_ref, evidence_ref = _apply_action(session, connection, envelope, action, envelope.message_type)
            envelope.internal_record_type = internal_type or envelope.internal_record_type
            envelope.internal_record_ref = internal_ref or envelope.internal_record_ref
            evidence_refs.append(evidence_ref)
        _upsert_entity_link(session, connection.connection_ref, payload)
        envelope.evidence_event_ref = evidence_refs[0] if evidence_refs else envelope.evidence_event_ref
        envelope.status = "processed"
        envelope.error = None
        envelope.processed_at = now
        connection.last_processed_at = now
        connection.last_error = None
        job.status = "completed"
        job.completed_at = now
        job.locked_at = None
        job.last_error = None
        job.acknowledgement_status = "ready"
        publish_event(
            session,
            event_type="integration_retry_completed",
            aggregate_type="integration_envelope",
            aggregate_ref=envelope.envelope_ref,
            premises_ref=connection.premises_ref,
            payload={"job": job_dict(job), "messageType": envelope.message_type},
            idempotency_key=f"integration-retry-complete:{job.job_ref}:attempt:{job.attempt_count}",
        )
    except Exception as exc:
        message = str(exc)[:1000]
        envelope.status = "failed"
        envelope.error = message
        connection.last_error = message
        job.last_error = message
        job.locked_at = None
        if job.attempt_count >= job.maximum_attempts:
            job.status = "dead_letter"
            job.dead_lettered_at = now
        else:
            job.status = "queued"
            delay_minutes = min(240, 2 ** max(0, job.attempt_count - 1))
            job.next_attempt_at = now + timedelta(minutes=delay_minutes)
        publish_event(
            session,
            event_type="integration_retry_failed",
            aggregate_type="integration_envelope",
            aggregate_ref=envelope.envelope_ref,
            premises_ref=connection.premises_ref,
            severity="error" if job.status == "dead_letter" else "warning",
            payload={"job": job_dict(job), "error": message},
            idempotency_key=f"integration-retry-fail:{job.job_ref}:attempt:{job.attempt_count}",
        )
    session.add(envelope)
    session.add(connection)
    session.add(job)


@router.post("/enqueue-failed")
def enqueue_failed(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior authority required")
    envelopes = session.exec(select(IntegrationEnvelope).where(IntegrationEnvelope.status == "failed")).all()
    jobs = [ensure_job(session, envelope) for envelope in envelopes]
    session.commit()
    return {"jobs": [job_dict(row) for row in jobs], "count": len(jobs)}


@router.get("/jobs")
def list_jobs(
    status: str | None = None,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(IntegrationRetryJob).order_by(IntegrationRetryJob.created_at.desc())
    if status:
        query = query.where(IntegrationRetryJob.status == status)
    rows = session.exec(query.limit(500)).all()
    return {"jobs": [job_dict(row) for row in rows], "count": len(rows)}


@router.post("/run-due")
def run_due(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior authority required")
    now = utc_now()
    jobs = session.exec(
        select(IntegrationRetryJob)
        .where(IntegrationRetryJob.status == "queued")
        .where(IntegrationRetryJob.next_attempt_at <= now)
        .order_by(IntegrationRetryJob.next_attempt_at)
        .limit(limit)
    ).all()
    for job in jobs:
        process_job(session, job)
    session.commit()
    return {"jobs": [job_dict(row) for row in jobs], "processed": len(jobs)}


@router.post("/jobs/{job_ref}/replay")
def replay_job(
    job_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior authority required")
    job = session.exec(select(IntegrationRetryJob).where(IntegrationRetryJob.job_ref == job_ref)).first()
    if not job:
        raise HTTPException(status_code=404, detail="retry job not found")
    if job.status not in {"dead_letter", "queued"}:
        raise HTTPException(status_code=409, detail="only queued or dead-letter jobs can be replayed")
    job.status = "queued"
    job.dead_lettered_at = None
    job.next_attempt_at = utc_now()
    job.replayed_by_subject = auth.subject
    job.version += 1
    session.add(job)
    evidence, _ = create_evidence_event(
        session,
        event_type="integration_dead_letter_replayed",
        action="replay_integration_message",
        reason="named operator requested controlled replay",
        new_state=job_dict(job),
        compliance_domain="integration_governance",
        risk_level="amber",
        source_module="integration-reliability-v7",
        source_record_ref=job.job_ref,
        entity_type="integration_retry_job",
        entity_id=job.job_ref,
        idempotency_key=f"integration-replay:{job.job_ref}:v{job.version}",
    )
    session.commit()
    return {"job": job_dict(job), "evidenceEventRef": evidence.event_ref}
