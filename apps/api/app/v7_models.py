from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthSession(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("session_ref", name="uq_authsession_ref"),
        UniqueConstraint("token_hash", name="uq_authsession_token_hash"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    session_ref: str = Field(index=True)
    token_hash: str = Field(index=True)
    csrf_hash: str
    subject: str = Field(index=True)
    actor_id: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    email: Optional[str] = None
    issuer: Optional[str] = None
    auth_source: str
    claims: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, index=True)
    last_seen_at: datetime = Field(default_factory=utc_now, index=True)
    expires_at: datetime = Field(index=True)
    idle_expires_at: datetime = Field(index=True)
    step_up_until: Optional[datetime] = Field(default=None, index=True)
    revoked_at: Optional[datetime] = Field(default=None, index=True)
    revoked_reason: Optional[str] = None


class DurableEvent(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("event_ref", name="uq_durableevent_ref"),
        UniqueConstraint("sequence", name="uq_durableevent_sequence"),
        UniqueConstraint("idempotency_key", name="uq_durableevent_idempotency"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    event_ref: str = Field(index=True)
    sequence: int = Field(index=True)
    event_type: str = Field(index=True)
    aggregate_type: str = Field(index=True)
    aggregate_ref: str = Field(index=True)
    premises_ref: str = Field(default="default-premises", index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    severity: str = Field(default="info", index=True)
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    correlation_id: Optional[str] = Field(default=None, index=True)
    causation_ref: Optional[str] = Field(default=None, index=True)
    idempotency_key: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    published_at: Optional[datetime] = Field(default=None, index=True)
    delivery_attempts: int = 0
    last_delivery_error: Optional[str] = None


class EventAcknowledgement(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("event_ref", name="uq_eventack_event_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    event_ref: str = Field(index=True)
    status: str = Field(default="unacknowledged", index=True)
    assigned_role: Optional[str] = Field(default=None, index=True)
    assigned_subject: Optional[str] = Field(default=None, index=True)
    acknowledged_by_subject: Optional[str] = Field(default=None, index=True)
    acknowledged_by_name: Optional[str] = None
    note: Optional[str] = None
    version: int = 1
    acknowledged_at: Optional[datetime] = Field(default=None, index=True)
    resolved_at: Optional[datetime] = Field(default=None, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class CanonicalShadowComparison(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("comparison_ref", name="uq_canonicalshadow_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    comparison_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    source_system: str = Field(index=True)
    source_record_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    block_ref: Optional[str] = Field(default=None, index=True)
    source_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    canonical_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    mismatch_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    validation_state: str = Field(default="pending", index=True)
    status: str = Field(default="open", index=True)
    version: int = 1
    reviewed_by_subject: Optional[str] = Field(default=None, index=True)
    reviewed_by_name: Optional[str] = None
    reviewed_by_role: Optional[str] = None
    review_note: Optional[str] = None
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class IntegrationRetryJob(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("job_ref", name="uq_integrationretry_ref"),
        UniqueConstraint("envelope_ref", name="uq_integrationretry_envelope"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    job_ref: str = Field(index=True)
    envelope_ref: str = Field(index=True)
    connection_ref: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    attempt_count: int = 0
    maximum_attempts: int = 8
    next_attempt_at: datetime = Field(default_factory=utc_now, index=True)
    locked_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    dead_lettered_at: Optional[datetime] = Field(default=None, index=True)
    acknowledgement_status: str = Field(default="not_sent", index=True)
    last_error: Optional[str] = None
    replayed_by_subject: Optional[str] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class LegacyWriteRetirement(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("route_key", name="uq_legacywrite_route_key"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    route_key: str = Field(index=True)
    replacement_path: str
    status: str = Field(default="blocked", index=True)
    reason: str
    activated_at: datetime = Field(default_factory=utc_now, index=True)
