from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import event, select
from sqlalchemy.orm import Session as OrmSession

from app.integration_models import IntegrationEnvelope
from app.v7_models import IntegrationRetryJob


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@event.listens_for(OrmSession, "before_flush")
def enqueue_failed_integration_envelopes(session: OrmSession, _flush_context, _instances) -> None:
    """Create retry/dead-letter records in the integration transaction.

    SQLModel rows are mutable and may be unhashable, so session collections must
    never be converted to a set. Deduplication is performed by stable envelope
    reference instead.
    """

    pending_refs = {
        row.envelope_ref
        for row in session.new
        if isinstance(row, IntegrationRetryJob) and row.envelope_ref
    }
    candidates: list[IntegrationEnvelope] = []
    seen_refs: set[str] = set()
    for row in [*list(session.new), *list(session.dirty)]:
        if not isinstance(row, IntegrationEnvelope) or row.status != "failed" or not row.envelope_ref:
            continue
        if row.envelope_ref in seen_refs:
            continue
        seen_refs.add(row.envelope_ref)
        candidates.append(row)

    for envelope in candidates:
        if envelope.envelope_ref in pending_refs:
            continue
        existing = session.execute(
            select(IntegrationRetryJob).where(IntegrationRetryJob.envelope_ref == envelope.envelope_ref)
        ).scalar_one_or_none()
        if existing:
            continue
        retained = bool(envelope.payload_json)
        session.add(
            IntegrationRetryJob(
                job_ref=f"retry-{uuid4().hex}",
                envelope_ref=envelope.envelope_ref,
                connection_ref=envelope.connection_ref,
                status="queued" if retained else "dead_letter",
                next_attempt_at=utc_now(),
                dead_lettered_at=None if retained else utc_now(),
                last_error=envelope.error if retained else "payload not retained; source system must resend",
            )
        )
        pending_refs.add(envelope.envelope_ref)
