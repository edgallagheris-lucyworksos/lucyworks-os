from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpeechProviderV28(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("provider_ref", name="uq_speechproviderv28_ref"),
        UniqueConstraint("site_ref", "name", name="uq_speechproviderv28_site_name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    provider_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    name: str
    provider_type: str = Field(default="browser", index=True)
    endpoint_host: Optional[str] = None
    processing_region: str = Field(default="GB", index=True)
    language: str = "en-GB"
    supports_streaming: bool = True
    supports_diarization: bool = False
    supports_word_timestamps: bool = False
    supports_word_confidence: bool = False
    raw_audio_retention: bool = False
    secret_env: Optional[str] = None
    configuration: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", index=True)
    last_test_status: str = Field(default="not_tested", index=True)
    last_test_detail: Optional[str] = None
    last_test_at: Optional[datetime] = Field(default=None, index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    updated_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SpeechSessionV28(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("session_ref", name="uq_speechsessionv28_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    session_ref: str = Field(index=True)
    provider_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    capture_mode: str = Field(default="clinical_dictation", index=True)
    language: str = "en-GB"
    status: str = Field(default="active", index=True)
    transcript_text: str = ""
    segment_count: int = 0
    device_diagnostics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    quality_summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    notice_version: str = "v28-default"
    notice_acknowledged: bool = False
    raw_audio_retained: bool = False
    created_by_subject: str = Field(index=True)
    created_by_name: str
    created_by_role: str = Field(index=True)
    linked_capture_ref: Optional[str] = Field(default=None, index=True)
    started_at: datetime = Field(default_factory=utc_now, index=True)
    interrupted_at: Optional[datetime] = Field(default=None, index=True)
    resumed_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SpeechSegmentV28(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("segment_ref", name="uq_speechsegmentv28_ref"),
        UniqueConstraint("session_ref", "sequence", name="uq_speechsegmentv28_session_sequence"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    segment_ref: str = Field(index=True)
    session_ref: str = Field(index=True)
    sequence: int = Field(index=True)
    text: str
    confidence: Optional[float] = None
    started_ms: Optional[int] = None
    ended_ms: Optional[int] = None
    speaker_label: Optional[str] = Field(default=None, index=True)
    is_final: bool = True
    source: str = Field(default="browser", index=True)
    words: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    payload_hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class IntegrationConnectorV28(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("connector_ref", name="uq_integrationconnectorv28_ref"),
        UniqueConstraint("site_ref", "connector_type", "environment", name="uq_integrationconnectorv28_site_type_env"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    connector_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    connector_type: str = Field(index=True)
    vendor_name: str
    environment: str = Field(default="sandbox", index=True)
    endpoint_host: Optional[str] = None
    secret_env: Optional[str] = None
    mode: str = Field(default="disabled", index=True)
    status: str = Field(default="draft", index=True)
    stale_after_seconds: int = 900
    configuration: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    last_test_status: str = Field(default="not_tested", index=True)
    last_test_detail: Optional[str] = None
    last_test_at: Optional[datetime] = Field(default=None, index=True)
    last_event_at: Optional[datetime] = Field(default=None, index=True)
    last_success_at: Optional[datetime] = Field(default=None, index=True)
    failure_count: int = 0
    version: int = 1
    created_by_subject: str = Field(index=True)
    updated_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class IntegrationPromotionV28(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("promotion_ref", name="uq_integrationpromotionv28_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    promotion_ref: str = Field(index=True)
    connector_ref: str = Field(index=True)
    requested_mode: str = Field(index=True)
    status: str = Field(default="requested", index=True)
    reason: str
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    requested_by_subject: str = Field(index=True)
    requested_by_name: str
    requested_at: datetime = Field(default_factory=utc_now, index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = Field(default=None, index=True)
    rejected_reason: Optional[str] = None
    version: int = 1


class IntegrationEventV28(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("event_ref", name="uq_integrationeventv28_ref"),
        UniqueConstraint("connector_ref", "external_event_id", name="uq_integrationeventv28_connector_external"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    event_ref: str = Field(index=True)
    connector_ref: str = Field(index=True)
    external_event_id: str = Field(index=True)
    event_type: str = Field(index=True)
    direction: str = Field(default="inbound", index=True)
    status: str = Field(default="received", index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    payload_hash: str = Field(index=True)
    payload_summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    occurred_at: Optional[datetime] = Field(default=None, index=True)
    received_at: datetime = Field(default_factory=utc_now, index=True)
    processed_at: Optional[datetime] = Field(default=None, index=True)
    retry_count: int = 0
    failure_code: Optional[str] = Field(default=None, index=True)
    failure_detail: Optional[str] = None
    evidence_ref: Optional[str] = Field(default=None, index=True)
    replay_of_event_ref: Optional[str] = Field(default=None, index=True)


class ReconciliationItemV28(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("item_ref", name="uq_reconciliationitemv28_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    item_ref: str = Field(index=True)
    connector_ref: str = Field(index=True)
    event_ref: str = Field(index=True)
    entity_type: str = Field(index=True)
    external_ref: str = Field(index=True)
    candidate_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="open", index=True)
    severity: str = Field(default="amber", index=True)
    reason: str
    assigned_role: str = Field(default="ops_manager", index=True)
    resolution: Optional[str] = None
    resolved_ref: Optional[str] = Field(default=None, index=True)
    resolved_by_subject: Optional[str] = Field(default=None, index=True)
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
