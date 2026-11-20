from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Session

from app.auth import AuthContext
from app.operating_context_v26_service import assert_payload_context, resolve_context
from app.v7_event_service import publish_event
from app.v7_models import DurableEvent


def event_name_is_fact(event_type: str) -> bool:
    # Command verbs are not facts. Fact names such as update_requested remain valid.
    command_verbs = {"create", "update", "delete", "set", "do", "request"}
    return event_type.rsplit(".", 1)[-1] not in command_verbs


class SubjectRef(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: str = Field(min_length=1, max_length=64)
    ref: str = Field(min_length=1, max_length=256)


class CanonicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}", min_length=1, max_length=256)
    event_type: str = Field(pattern=r"^[a-z0-9_]+\.[a-z0-9_]+$")
    schema_version: int = Field(default=1, ge=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organisation_ref: str = Field(min_length=1, max_length=256)
    site_ref: str = Field(min_length=1, max_length=256)
    premises_ref: str = Field(min_length=1, max_length=256)
    subjects: list[SubjectRef] = Field(min_length=1)
    source: str = Field(min_length=1, max_length=256)
    correlation_id: str = Field(min_length=1, max_length=256)
    causation_ref: str | None = Field(default=None, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def validate_fact_name(cls, value: str) -> str:
        if not event_name_is_fact(value):
            raise ValueError("event_type must name an observed fact, not a command")
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


def publish_canonical_event(
    session: Session,
    auth: AuthContext,
    event: CanonicalEvent,
) -> DurableEvent:
    if not auth.verified:
        raise HTTPException(status_code=401, detail="verified identity required to publish a canonical event")
    context = resolve_context(session, auth)
    assert_payload_context(context, {
        "organisationRef": event.organisation_ref,
        "siteRef": event.site_ref,
        "premisesRef": event.premises_ref,
    })
    primary_subject = event.subjects[0]
    envelope = {
        "eventId": event.event_id,
        "schemaVersion": event.schema_version,
        "occurredAt": event.occurred_at.isoformat(),
        "organisationRef": event.organisation_ref,
        "siteRef": event.site_ref,
        "premisesRef": event.premises_ref,
        "subjects": [subject.model_dump(mode="json") for subject in event.subjects],
        "source": event.source,
        "data": event.payload,
    }
    row = publish_event(
        session,
        event_type=event.event_type,
        aggregate_type=primary_subject.kind,
        aggregate_ref=primary_subject.ref,
        premises_ref=event.premises_ref,
        payload=envelope,
        correlation_id=event.correlation_id,
        causation_ref=event.causation_ref,
        idempotency_key=event.idempotency_key,
        actor=auth,
    )
    if (
        row.event_type != event.event_type
        or row.aggregate_type != primary_subject.kind
        or row.aggregate_ref != primary_subject.ref
        or row.payload != envelope
    ):
        raise HTTPException(status_code=409, detail={
            "code": "event_idempotency_conflict",
            "message": "idempotency key was already used for a different event",
        })
    return row
