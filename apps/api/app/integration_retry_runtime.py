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
    """Create the durable retry/dead-letter record in the same transaction.

    This applies to webhook handling and any future integration importer; it does
    not depend on an operator visiting the retry dashboard.
    """

    pending_refs = {
        row.envelope_ref
        for row in session.new
        if isinstance(row, IntegrationRetryJob)
    }
    candidates = [
        row
        for row in {*session.new, *session.dirty}
        if isinstance(row, IntegrationEnvelope) and row.status == "failed" and row.envelope_ref
    ]
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
